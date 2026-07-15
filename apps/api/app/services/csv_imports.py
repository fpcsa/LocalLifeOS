from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pandas as pd
from dateutil import parser as date_parser
from fastapi import UploadFile
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    AutomationTriggerType,
    CategoryKind,
    CsvMappingProfile,
    DomainEntityType,
    FinancialAccount,
    ImportBatch,
    ImportBatchStatus,
    ImportKind,
    ImportRow,
    ImportRowStatus,
    Transaction,
    TransactionCategory,
    TransactionType,
)
from app.models.common import normalize_currency_code, utc_now
from app.repositories.finance_engine import FinanceTransactionRepository
from app.repositories.imports import (
    CsvMappingProfileRepository,
    ImportBatchRepository,
    ImportRowRepository,
)
from app.schemas.imports import (
    CsvMappingRequest,
    ImportApplyRequest,
    ImportBatchResponse,
    ImportPreviewResponse,
)
from app.services.automation import dispatch_automation_event
from app.services.events import emit_timeline_event
from app.services.finance_validation import validate_transaction_relationships
from app.services.import_files import read_import_upload, store_import_file
from app.services.imports import batch_response, preview_response
from app.services.workspace import get_current_workspace, get_preferences

DELIMITERS = [",", ";", "\t", "|"]
ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
THREE_DECIMAL_CURRENCIES = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}


def detect_csv_encoding(data: bytes) -> tuple[str, str]:
    if b"\x00" in data:
        raise DomainValidationError("binary_csv", "The CSV contains binary null bytes.")
    candidates = ["utf-8-sig", "utf-8", "cp1252"]
    for encoding in candidates:
        try:
            return encoding, data.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    raise DomainValidationError(
        "csv_encoding", "Use UTF-8 or a Windows-1252 compatible bank export."
    )


def detect_csv_delimiter(text: str) -> str:
    sample = text[:32_768]
    try:
        detected = csv.Sniffer().sniff(sample, delimiters="".join(DELIMITERS)).delimiter
    except csv.Error as exc:
        raise DomainValidationError(
            "csv_delimiter", "The CSV delimiter could not be detected safely."
        ) from exc
    if detected not in DELIMITERS:
        raise DomainValidationError("csv_delimiter", "The CSV uses an unsupported delimiter.")
    return detected


def preview_csv_import(session: Session, upload: UploadFile) -> ImportPreviewResponse:
    workspace = get_current_workspace(session)
    data, filename, source_fingerprint = read_import_upload(upload, extension=".csv")
    repository = ImportBatchRepository(session)
    existing = repository.find_source(workspace.id, ImportKind.BANK_CSV, source_fingerprint)
    if existing is not None:
        return preview_response(session, existing)
    encoding, text = detect_csv_encoding(data)
    delimiter = detect_csv_delimiter(text)
    try:
        frame = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="error",
            nrows=get_settings().max_import_rows + 1,
        )
    except (pd.errors.ParserError, UnicodeError, ValueError) as exc:
        raise DomainValidationError("invalid_csv", "The bank CSV could not be parsed.") from exc
    if len(frame.index) > get_settings().max_import_rows:
        raise DomainValidationError(
            "csv_row_limit",
            f"CSV imports cannot exceed {get_settings().max_import_rows} data rows.",
        )
    columns = [str(value).strip() for value in frame.columns]
    if not columns or len(columns) != len(set(columns)) or any(not value for value in columns):
        raise DomainValidationError(
            "csv_headers", "CSV headers must be present, non-empty, and unique."
        )
    frame.columns = columns
    batch = ImportBatch(
        workspace_id=workspace.id,
        kind=ImportKind.BANK_CSV,
        status=ImportBatchStatus.PREVIEWED,
        original_filename=filename,
        stored_path="pending",
        source_fingerprint=source_fingerprint,
        detected_encoding=encoding,
        detected_delimiter=delimiter,
        total_rows=len(frame.index),
        new_count=len(frame.index),
        summary={"columns": columns, "mapped": False},
    )
    batch.stored_path = store_import_file(batch.id, filename, data)
    rows = [
        ImportRow(
            workspace_id=workspace.id,
            batch_id=batch.id,
            row_number=index + 1,
            status=ImportRowStatus.NEW,
            included=True,
            raw_data={key: str(value) for key, value in record.items()},
            normalized_data={},
            issues=[],
        )
        for index, record in enumerate(frame.to_dict(orient="records"))
    ]
    with transaction(session):
        repository.add(batch)
        row_repository = ImportRowRepository(session)
        for row in rows:
            row_repository.add(row)
    return preview_response(session, batch)


def _minor_digits(currency: str) -> int:
    if currency in ZERO_DECIMAL_CURRENCIES:
        return 0
    if currency in THREE_DECIMAL_CURRENCIES:
        return 3
    return 2


def _decimal_value(value: str, separator: str) -> Decimal:
    candidate = value.strip().replace("\u00a0", "").replace(" ", "")
    if not candidate:
        return Decimal(0)
    negative_parentheses = candidate.startswith("(") and candidate.endswith(")")
    if negative_parentheses:
        candidate = candidate[1:-1]
    if separator == ",":
        candidate = candidate.replace(".", "").replace(",", ".")
    else:
        candidate = candidate.replace(",", "")
    try:
        parsed = Decimal(candidate)
    except InvalidOperation as exc:
        raise ValueError(f"{value!r} is not a valid amount") from exc
    return -parsed if negative_parentheses else parsed


def _parse_amount(
    raw: dict[str, str], request: CsvMappingRequest, currency: str
) -> tuple[TransactionType, int]:
    columns = request.columns
    if columns.amount is not None:
        signed = _decimal_value(raw.get(columns.amount, ""), request.decimal_separator)
        if signed == 0:
            raise ValueError("amount cannot be zero")
        positive_income = request.amount_positive_is_income
        transaction_type = (
            TransactionType.INCOME if (signed > 0) == positive_income else TransactionType.EXPENSE
        )
        magnitude = abs(signed)
    else:
        debit = _decimal_value(raw.get(columns.debit or "", ""), request.decimal_separator)
        credit = _decimal_value(raw.get(columns.credit or "", ""), request.decimal_separator)
        debit = abs(debit)
        credit = abs(credit)
        if (debit > 0) == (credit > 0):
            raise ValueError("exactly one debit or credit value is required")
        transaction_type = TransactionType.EXPENSE if debit > 0 else TransactionType.INCOME
        magnitude = debit if debit > 0 else credit
    factor = Decimal(10) ** _minor_digits(currency)
    minor = int((magnitude * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if minor <= 0:
        raise ValueError("amount is below the currency's smallest unit")
    return transaction_type, minor


def _resolve_account(
    value: str | None,
    default_id: UUID | None,
    accounts_by_id: dict[UUID, FinancialAccount],
    accounts_by_name: dict[str, FinancialAccount],
) -> FinancialAccount:
    if value:
        try:
            account = accounts_by_id.get(UUID(value))
        except ValueError:
            account = accounts_by_name.get(value.strip().casefold())
    else:
        account = accounts_by_id.get(default_id) if default_id else None
    if account is None:
        raise ValueError("account could not be matched")
    return account


def _resolve_category(
    value: str | None,
    default_id: UUID | None,
    transaction_type: TransactionType,
    categories_by_id: dict[UUID, TransactionCategory],
    categories_by_name: dict[tuple[str, CategoryKind], TransactionCategory],
) -> TransactionCategory | None:
    expected_kind = (
        CategoryKind.INCOME if transaction_type == TransactionType.INCOME else CategoryKind.EXPENSE
    )
    if value:
        try:
            category = categories_by_id.get(UUID(value))
        except ValueError:
            category = categories_by_name.get((value.strip().casefold(), expected_kind))
    else:
        category = categories_by_id.get(default_id) if default_id else None
    if category is not None and category.kind != expected_kind:
        raise ValueError(f"category must be {expected_kind.value}")
    return category


def _parse_date(value: str, date_format: str | None, timezone: str) -> datetime:
    if not value.strip():
        raise ValueError("date is required")
    try:
        parsed = (
            datetime.strptime(value.strip(), date_format)
            if date_format
            else date_parser.parse(value.strip(), dayfirst=False, yearfirst=False)
        )
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{value!r} is not a valid date") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed.astimezone(UTC)


def _fingerprint(normalized: dict[str, Any]) -> str:
    external_id = normalized.get("external_id")
    payload = (
        {"external_id": external_id}
        if external_id
        else {
            key: normalized[key]
            for key in (
                "account_id",
                "transaction_type",
                "amount_minor",
                "currency_code",
                "occurred_at",
                "description",
            )
        }
    )
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _find_duplicate(
    session: Session, workspace_id: UUID, normalized: dict[str, Any], fingerprint: str
) -> tuple[str | None, UUID | None]:
    identity_filters = [col(Transaction.import_fingerprint) == fingerprint]
    if normalized.get("external_id"):
        identity_filters.append(col(Transaction.external_id) == normalized["external_id"])
    exact = session.exec(
        select(Transaction).where(
            col(Transaction.workspace_id) == workspace_id,
            col(Transaction.deleted_at).is_(None),
            or_(*identity_filters),
        )
    ).first()
    if exact is not None:
        return "exact", exact.id
    probable = session.exec(
        select(Transaction).where(
            col(Transaction.workspace_id) == workspace_id,
            col(Transaction.deleted_at).is_(None),
            col(Transaction.account_id) == UUID(normalized["account_id"]),
            col(Transaction.transaction_type) == TransactionType(normalized["transaction_type"]),
            col(Transaction.amount_minor) == int(normalized["amount_minor"]),
            col(Transaction.currency_code) == normalized["currency_code"],
            col(Transaction.occurred_at) == datetime.fromisoformat(normalized["occurred_at"]),
        )
    ).first()
    return ("probable", probable.id) if probable is not None else (None, None)


def _issue(message: str, field: str | None = None) -> dict[str, Any]:
    return {"code": "invalid_row", "message": message, "field": field}


def map_csv_import(
    session: Session, batch_id: UUID, request: CsvMappingRequest
) -> ImportPreviewResponse:
    workspace = get_current_workspace(session)
    batch = ImportBatchRepository(session).get_workspace(workspace.id, batch_id)
    if batch is None or batch.kind != ImportKind.BANK_CSV:
        raise DomainNotFoundError("bank CSV import batch", batch_id)
    if batch.applied_at is not None:
        raise DomainConflictError("import_already_applied", "Applied imports cannot be remapped.")
    columns = set(str(value) for value in batch.summary.get("columns", []))
    mapped_columns = [value for value in request.columns.model_dump().values() if value]
    unknown = sorted(set(mapped_columns) - columns)
    if unknown:
        raise DomainValidationError(
            "csv_mapping_columns",
            "Mapped columns are not present in the CSV.",
            {"columns": unknown},
        )
    accounts = list(
        session.exec(
            select(FinancialAccount).where(
                col(FinancialAccount.workspace_id) == workspace.id,
                col(FinancialAccount.deleted_at).is_(None),
            )
        ).all()
    )
    categories = list(
        session.exec(
            select(TransactionCategory).where(
                col(TransactionCategory.workspace_id) == workspace.id,
                col(TransactionCategory.deleted_at).is_(None),
            )
        ).all()
    )
    accounts_by_id = {item.id: item for item in accounts}
    accounts_by_name = {item.name.casefold(): item for item in accounts}
    categories_by_id = {item.id: item for item in categories}
    categories_by_name = {(item.name.casefold(), item.kind): item for item in categories}
    preferences = get_preferences(session)
    rows = ImportRowRepository(session).list_batch(workspace.id, batch.id)
    for row in rows:
        raw = {str(key): str(value) for key, value in row.raw_data.items()}
        try:
            currency = normalize_currency_code(
                raw.get(request.columns.currency, "")
                if request.columns.currency
                else request.default_currency or ""
            )
            account_value = (
                raw.get(request.columns.account, "") if request.columns.account else None
            )
            account = _resolve_account(
                account_value,
                request.default_account_id,
                accounts_by_id,
                accounts_by_name,
            )
            if account.currency_code != currency:
                raise ValueError("row currency does not match the selected account")
            transaction_type, amount_minor = _parse_amount(raw, request, currency)
            category_value = (
                raw.get(request.columns.category, "") if request.columns.category else None
            )
            category = _resolve_category(
                category_value,
                request.default_category_id,
                transaction_type,
                categories_by_id,
                categories_by_name,
            )
            occurred_at = _parse_date(
                raw.get(request.columns.date, ""), request.date_format, preferences.timezone
            )
            description = raw.get(request.columns.description, "").strip()
            if not description:
                raise ValueError("description is required")
            external_id = (
                raw.get(request.columns.external_id, "").strip()
                if request.columns.external_id
                else ""
            )
            normalized: dict[str, Any] = {
                "account_id": str(account.id),
                "category_id": str(category.id) if category else None,
                "transaction_type": transaction_type.value,
                "amount_minor": amount_minor,
                "currency_code": currency,
                "occurred_at": occurred_at.isoformat(),
                "description": description,
                "external_id": external_id or None,
            }
            fingerprint = _fingerprint(normalized)
            duplicate_kind, duplicate_target_id = _find_duplicate(
                session, workspace.id, normalized, fingerprint
            )
            row.status = ImportRowStatus.DUPLICATE if duplicate_kind else ImportRowStatus.NEW
            row.included = duplicate_kind is None
            row.fingerprint = fingerprint
            row.normalized_data = normalized
            row.issues = (
                [
                    {
                        "code": f"{duplicate_kind}_duplicate",
                        "message": (
                            "An identical imported transaction already exists."
                            if duplicate_kind == "exact"
                            else (
                                "A transaction with the same account, amount, and time "
                                "already exists."
                            )
                        ),
                        "field": None,
                    }
                ]
                if duplicate_kind
                else []
            )
            row.duplicate_kind = duplicate_kind
            row.duplicate_target_id = duplicate_target_id
        except (KeyError, TypeError, ValueError) as exc:
            row.status = ImportRowStatus.INVALID
            row.included = False
            row.fingerprint = None
            row.normalized_data = {}
            row.issues = [_issue(str(exc))]
            row.duplicate_kind = None
            row.duplicate_target_id = None
        row.revision += 1

    profile_id: UUID | None = None
    with transaction(session):
        for row in rows:
            session.add(row)
        if request.save_profile and request.profile_name:
            profile_repository = CsvMappingProfileRepository(session)
            if profile_repository.find_name(workspace.id, request.profile_name) is not None:
                raise DomainConflictError(
                    "mapping_profile_name", "A mapping profile already uses this name."
                )
            profile = profile_repository.add(
                CsvMappingProfile(
                    workspace_id=workspace.id,
                    name=request.profile_name,
                    columns=request.columns.model_dump(),
                    date_format=request.date_format,
                    decimal_separator=request.decimal_separator,
                    amount_positive_is_income=request.amount_positive_is_income,
                    default_currency=request.default_currency,
                    default_account_id=request.default_account_id,
                    default_category_id=request.default_category_id,
                    delimiter=batch.detected_delimiter,
                    encoding=batch.detected_encoding,
                )
            )
            profile_id = profile.id
        batch.mapping_profile_id = profile_id
        batch.new_count = sum(row.status == ImportRowStatus.NEW for row in rows)
        batch.changed_count = 0
        batch.duplicate_count = sum(row.status == ImportRowStatus.DUPLICATE for row in rows)
        batch.invalid_count = sum(row.status == ImportRowStatus.INVALID for row in rows)
        batch.summary = {**batch.summary, "mapped": True, "mapping": request.columns.model_dump()}
        batch.revision += 1
        session.add(batch)
    return preview_response(session, batch)


def apply_csv_import(
    session: Session, batch_id: UUID, request: ImportApplyRequest
) -> ImportBatchResponse:
    workspace = get_current_workspace(session)
    batch = ImportBatchRepository(session).get_workspace(workspace.id, batch_id)
    if batch is None or batch.kind != ImportKind.BANK_CSV:
        raise DomainNotFoundError("bank CSV import batch", batch_id)
    if batch.applied_at is not None:
        return batch_response(batch)
    if not batch.summary.get("mapped"):
        raise DomainConflictError("csv_not_mapped", "Map the CSV columns before applying it.")
    rows = ImportRowRepository(session).list_batch(workspace.id, batch.id)
    selected = set(request.included_row_ids) if request.included_row_ids is not None else None
    transaction_repository = FinanceTransactionRepository(session)
    imported = 0
    imported_transactions: list[Transaction] = []
    with transaction(session):
        for row in rows:
            include = row.included if selected is None else row.id in selected
            eligible = row.status == ImportRowStatus.NEW or (
                row.status == ImportRowStatus.DUPLICATE and row.duplicate_kind == "probable"
            )
            if not include or not eligible:
                if eligible:
                    row.status = ImportRowStatus.EXCLUDED
                    row.revision += 1
                    session.add(row)
                continue
            normalized = row.normalized_data
            fingerprint = str(row.fingerprint)
            if transaction_repository.fingerprint_exists(workspace.id, fingerprint):
                raise DomainConflictError(
                    "csv_import_stale", "A selected transaction was imported after preview."
                )
            account_id = UUID(str(normalized["account_id"]))
            category_id = (
                UUID(str(normalized["category_id"])) if normalized.get("category_id") else None
            )
            transaction_type = TransactionType(str(normalized["transaction_type"]))
            validate_transaction_relationships(
                session,
                workspace.id,
                account_id=account_id,
                transfer_account_id=None,
                category_id=category_id,
                transaction_type=transaction_type,
                currency_code=str(normalized["currency_code"]),
            )
            item = transaction_repository.add(
                Transaction(
                    workspace_id=workspace.id,
                    account_id=account_id,
                    category_id=category_id,
                    transaction_type=transaction_type,
                    amount_minor=int(normalized["amount_minor"]),
                    currency_code=str(normalized["currency_code"]),
                    occurred_at=datetime.fromisoformat(str(normalized["occurred_at"])),
                    payee=str(normalized["description"]),
                    external_id=(
                        str(normalized["external_id"]) if normalized.get("external_id") else None
                    ),
                    import_fingerprint=fingerprint,
                )
            )
            row.status = ImportRowStatus.IMPORTED
            row.target_id = item.id
            row.revision += 1
            session.add(row)
            imported += 1
            imported_transactions.append(item)
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TRANSACTION,
                entity_id=item.id,
                action="transaction_csv_imported",
                title=f"Bank import: {item.payee}",
                payload={"import_batch_id": str(batch.id)},
            )
        batch.status = ImportBatchStatus.APPLIED
        batch.imported_count = imported
        batch.applied_at = utc_now()
        batch.revision += 1
        session.add(batch)
    for item in imported_transactions:
        dispatch_automation_event(
            session,
            AutomationTriggerType.TRANSACTION_CREATED,
            context={
                "entity_type": DomainEntityType.TRANSACTION.value,
                "entity_id": str(item.id),
                "account_id": str(item.account_id),
                "category_id": str(item.category_id) if item.category_id else None,
                "transaction_type": item.transaction_type.value,
                "amount_minor": item.amount_minor,
                "currency_code": item.currency_code,
                "payee": item.payee,
            },
            source_key=f"transaction:{item.id}",
        )
    return batch_response(batch)
