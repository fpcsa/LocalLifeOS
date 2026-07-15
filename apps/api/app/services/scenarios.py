from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, col, select

from app.core.exceptions import (
    DomainConflictError,
    DomainNotFoundError,
    DomainValidationError,
    RevisionConflictError,
)
from app.db.transactions import transaction
from app.models import (
    CalendarEvent,
    Commitment,
    DomainEntityType,
    FinancialAccount,
    Goal,
    PlannedTransaction,
    Scenario,
    ScenarioChange,
    ScenarioOperation,
    ScenarioStatus,
    Task,
    Transaction,
)
from app.models.common import utc_now
from app.repositories import ScenarioChangeRepository, ScenarioRepository
from app.schemas.scenarios import (
    ScenarioAcceptRequest,
    ScenarioAcceptResponse,
    ScenarioChangeCreateRequest,
    ScenarioChangeResponse,
    ScenarioChangeUpdateRequest,
    ScenarioCompareResponse,
    ScenarioCreateRequest,
    ScenarioCurrencyProjection,
    ScenarioMetricDelta,
    ScenarioMetrics,
    ScenarioPlanField,
    ScenarioPlanStep,
    ScenarioPreviewResponse,
    ScenarioResponse,
    ScenarioUpdateRequest,
)
from app.services.events import emit_timeline_event
from app.services.workspace import get_current_workspace

EXPECTED_REVISION_KEY = "__expected_revision"

TARGET_MODELS: dict[
    DomainEntityType, type[Task | CalendarEvent | PlannedTransaction | Commitment | Goal]
] = {
    DomainEntityType.TASK: Task,
    DomainEntityType.CALENDAR_EVENT: CalendarEvent,
    DomainEntityType.PLANNED_TRANSACTION: PlannedTransaction,
    DomainEntityType.COMMITMENT: Commitment,
    DomainEntityType.GOAL: Goal,
}

ALLOWED_FIELDS: dict[DomainEntityType, frozenset[str]] = {
    DomainEntityType.TASK: frozenset(
        {
            "title",
            "description_markdown",
            "status",
            "priority",
            "estimated_duration_minutes",
            "actual_duration_minutes",
            "earliest_start_at",
            "due_at",
            "preferred_time_of_day",
            "scheduled_start_at",
            "scheduled_end_at",
        }
    ),
    DomainEntityType.CALENDAR_EVENT: frozenset(
        {
            "title",
            "description_markdown",
            "location",
            "category",
            "status",
            "all_day",
            "starts_at",
            "ends_at",
            "all_day_start",
            "all_day_end",
            "timezone",
            "preparation_buffer_minutes",
            "travel_buffer_minutes",
            "recovery_buffer_minutes",
        }
    ),
    DomainEntityType.PLANNED_TRANSACTION: frozenset(
        {
            "account_id",
            "transfer_account_id",
            "category_id",
            "transaction_type",
            "amount_minor",
            "currency_code",
            "planned_for",
            "payee",
            "note",
            "status",
            "is_committed",
        }
    ),
    DomainEntityType.COMMITMENT: frozenset(
        {
            "title",
            "description_markdown",
            "status",
            "category",
            "target_start_at",
            "target_end_at",
            "decision_deadline_at",
            "time_capacity_requirement_minutes",
            "planned_cost_minor",
            "financial_buffer_requirement_minor",
            "currency_code",
        }
    ),
    DomainEntityType.GOAL: frozenset(
        {
            "title",
            "description_markdown",
            "status",
            "progress_basis_points",
            "target_at",
        }
    ),
}

COMMITMENT_FIELD_MAP = {
    "target_start_at": "starts_at",
    "target_end_at": "ends_at",
    "time_capacity_requirement_minutes": "estimated_duration_minutes",
}


def _scenario_response(scenario: Scenario, change_count: int) -> ScenarioResponse:
    return ScenarioResponse(
        id=scenario.id,
        workspace_id=scenario.workspace_id,
        name=scenario.name,
        description_markdown=scenario.description_markdown,
        status=scenario.status,
        base_revision=scenario.base_revision,
        change_count=change_count,
        revision=scenario.revision,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


def _public_patch(change: ScenarioChange) -> dict[str, Any]:
    return {key: value for key, value in change.changes.items() if key != EXPECTED_REVISION_KEY}


def _expected_revision(change: ScenarioChange) -> int | None:
    raw = change.changes.get(EXPECTED_REVISION_KEY)
    return int(raw) if isinstance(raw, int) else None


def _change_response(change: ScenarioChange) -> ScenarioChangeResponse:
    return ScenarioChangeResponse(
        id=change.id,
        scenario_id=change.scenario_id,
        entity_type=change.entity_type,
        entity_id=change.entity_id,
        operation=change.operation,
        changes=_public_patch(change),
        expected_revision=_expected_revision(change),
        revision=change.revision,
        created_at=change.created_at,
        updated_at=change.updated_at,
    )


def _require_draft(session: Session, scenario_id: UUID) -> Scenario:
    workspace = get_current_workspace(session)
    scenario = ScenarioRepository(session).get_active(workspace.id, scenario_id)
    if scenario is None:
        raise DomainNotFoundError("scenario", scenario_id)
    if scenario.status != ScenarioStatus.DRAFT:
        raise DomainConflictError(
            "scenario_not_editable",
            "Only draft scenarios can be edited.",
        )
    return scenario


def _target(
    session: Session,
    workspace_id: UUID,
    entity_type: DomainEntityType,
    entity_id: UUID,
) -> Task | CalendarEvent | PlannedTransaction | Commitment | Goal | None:
    model = TARGET_MODELS.get(entity_type)
    if model is None:
        raise DomainValidationError(
            "unsupported_scenario_entity",
            f"Scenario changes do not support {entity_type.value}.",
        )
    target = session.get(model, entity_id)
    if target is None or target.workspace_id != workspace_id or target.deleted_at is not None:
        return None
    return cast(Task | CalendarEvent | PlannedTransaction | Commitment | Goal, target)


def _mapped_patch(entity_type: DomainEntityType, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = ALLOWED_FIELDS[entity_type]
    unknown = sorted(set(patch) - allowed)
    if unknown:
        raise DomainValidationError(
            "unsupported_scenario_fields",
            "One or more fields are not supported by this scenario entity type.",
            {"fields": unknown, "entity_type": entity_type.value},
        )
    if entity_type == DomainEntityType.COMMITMENT:
        return {COMMITMENT_FIELD_MAP.get(key, key): value for key, value in patch.items()}
    return dict(patch)


def _validate_prospective(
    entity_type: DomainEntityType,
    current: Task | CalendarEvent | PlannedTransaction | Commitment | Goal | None,
    patch: dict[str, Any],
    *,
    workspace_id: UUID,
    entity_id: UUID,
) -> dict[str, Any]:
    model = TARGET_MODELS[entity_type]
    mapped = _mapped_patch(entity_type, patch)
    seed = (
        current.model_dump()
        if current is not None
        else {"workspace_id": workspace_id, "id": entity_id}
    )
    seed.update(mapped)
    try:
        prospective = model.model_validate(seed)
    except ValueError as exc:
        raise DomainValidationError(
            "invalid_scenario_change",
            "The proposed fields do not form a valid record.",
            {"reason": str(exc)},
        ) from exc
    if isinstance(prospective, Task):
        if (prospective.scheduled_start_at is None) != (prospective.scheduled_end_at is None):
            raise DomainValidationError(
                "invalid_scenario_change",
                "Task schedule start and end must both be set or both be empty.",
            )
        if (
            prospective.scheduled_start_at is not None
            and prospective.scheduled_end_at is not None
            and prospective.scheduled_end_at <= prospective.scheduled_start_at
        ):
            raise DomainValidationError(
                "invalid_scenario_change", "Task schedule end must be after its start."
            )
    if isinstance(prospective, CalendarEvent):
        if prospective.all_day:
            valid = (
                prospective.all_day_start is not None
                and prospective.all_day_end is not None
                and prospective.all_day_end > prospective.all_day_start
                and prospective.starts_at is None
                and prospective.ends_at is None
            )
        else:
            valid = (
                prospective.starts_at is not None
                and prospective.ends_at is not None
                and prospective.ends_at > prospective.starts_at
                and prospective.all_day_start is None
                and prospective.all_day_end is None
            )
        if not valid:
            raise DomainValidationError(
                "invalid_scenario_change", "Calendar event timing is not valid."
            )
    if isinstance(prospective, Commitment):
        if (
            prospective.starts_at is not None
            and prospective.ends_at is not None
            and prospective.ends_at <= prospective.starts_at
        ):
            raise DomainValidationError(
                "invalid_scenario_change", "Commitment target end must follow its start."
            )
        has_money = (
            prospective.planned_cost_minor is not None
            or prospective.financial_buffer_requirement_minor is not None
        )
        if has_money != (prospective.currency_code is not None):
            raise DomainValidationError(
                "invalid_scenario_change", "Commitment money fields require a currency."
            )
    dump = prospective.model_dump()
    return {key: dump[key] for key in mapped}


def list_scenarios(session: Session) -> list[ScenarioResponse]:
    workspace = get_current_workspace(session)
    repository = ScenarioRepository(session)
    scenarios = repository.list_active(workspace.id)
    counts = repository.change_counts([item.id for item in scenarios])
    return [_scenario_response(item, counts.get(item.id, 0)) for item in scenarios]


def create_scenario(session: Session, request: ScenarioCreateRequest) -> ScenarioResponse:
    workspace = get_current_workspace(session)
    scenario = Scenario(
        workspace_id=workspace.id,
        name=request.name,
        description_markdown=request.description_markdown,
        base_revision=workspace.revision,
    )
    with transaction(session):
        ScenarioRepository(session).add(scenario)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.SCENARIO,
            entity_id=scenario.id,
            action="scenario_created",
            title=f"Scenario created: {scenario.name}",
        )
    return _scenario_response(scenario, 0)


def get_scenario(session: Session, scenario_id: UUID) -> ScenarioResponse:
    workspace = get_current_workspace(session)
    repository = ScenarioRepository(session)
    scenario = repository.get_active(workspace.id, scenario_id)
    if scenario is None:
        raise DomainNotFoundError("scenario", scenario_id)
    count = repository.change_counts([scenario.id]).get(scenario.id, 0)
    return _scenario_response(scenario, count)


def update_scenario(
    session: Session, scenario_id: UUID, request: ScenarioUpdateRequest
) -> ScenarioResponse:
    scenario = _require_draft(session, scenario_id)
    if scenario.revision != request.revision:
        raise RevisionConflictError("scenario", request.revision, scenario.revision)
    values = request.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one scenario field is required.")
    with transaction(session):
        for key, value in values.items():
            setattr(scenario, key, value)
        scenario.revision += 1
        scenario.updated_at = utc_now()
        session.add(scenario)
    return get_scenario(session, scenario.id)


def discard_scenario(session: Session, scenario_id: UUID, revision: int) -> ScenarioResponse:
    scenario = _require_draft(session, scenario_id)
    if scenario.revision != revision:
        raise RevisionConflictError("scenario", revision, scenario.revision)
    with transaction(session):
        scenario.status = ScenarioStatus.DISCARDED
        scenario.revision += 1
        scenario.updated_at = utc_now()
        session.add(scenario)
        emit_timeline_event(
            session,
            workspace_id=scenario.workspace_id,
            entity_type=DomainEntityType.SCENARIO,
            entity_id=scenario.id,
            action="scenario_discarded",
            title=f"Scenario discarded: {scenario.name}",
        )
    return get_scenario(session, scenario.id)


def list_scenario_changes(session: Session, scenario_id: UUID) -> list[ScenarioChangeResponse]:
    get_scenario(session, scenario_id)
    return [
        _change_response(item)
        for item in ScenarioChangeRepository(session).list_for_scenario(scenario_id)
    ]


def add_scenario_change(
    session: Session,
    scenario_id: UUID,
    request: ScenarioChangeCreateRequest,
) -> ScenarioChangeResponse:
    scenario = _require_draft(session, scenario_id)
    repository = ScenarioChangeRepository(session)
    if repository.get_for_entity(scenario_id, request.entity_type, request.entity_id) is not None:
        raise DomainConflictError(
            "duplicate_scenario_change",
            "This scenario already contains a change for that record.",
        )
    current = _target(session, scenario.workspace_id, request.entity_type, request.entity_id)
    if request.operation == ScenarioOperation.CREATE and current is not None:
        raise DomainConflictError(
            "scenario_target_exists", "The proposed new record already exists."
        )
    if request.operation != ScenarioOperation.CREATE and current is None:
        raise DomainNotFoundError(request.entity_type.value, request.entity_id)
    public_patch = dict(request.changes)
    if request.operation != ScenarioOperation.DELETE:
        _validate_prospective(
            request.entity_type,
            current,
            public_patch,
            workspace_id=scenario.workspace_id,
            entity_id=request.entity_id,
        )
    stored = jsonable_encoder(public_patch)
    if current is not None:
        stored[EXPECTED_REVISION_KEY] = current.revision
    with transaction(session):
        change = repository.add(
            ScenarioChange(
                workspace_id=scenario.workspace_id,
                scenario_id=scenario.id,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                operation=request.operation,
                changes=stored,
            )
        )
        scenario.revision += 1
        scenario.updated_at = utc_now()
        session.add(scenario)
    return _change_response(change)


def update_scenario_change(
    session: Session,
    scenario_id: UUID,
    change_id: UUID,
    request: ScenarioChangeUpdateRequest,
) -> ScenarioChangeResponse:
    scenario = _require_draft(session, scenario_id)
    repository = ScenarioChangeRepository(session)
    change = repository.get(change_id)
    if change is None or change.scenario_id != scenario.id:
        raise DomainNotFoundError("scenario_change", change_id)
    if change.operation == ScenarioOperation.DELETE:
        raise DomainValidationError(
            "scenario_delete_has_no_fields", "Delete changes do not contain editable fields."
        )
    if change.revision != request.revision:
        raise RevisionConflictError("scenario_change", request.revision, change.revision)
    current = _target(session, scenario.workspace_id, change.entity_type, change.entity_id)
    _validate_prospective(
        change.entity_type,
        current,
        request.changes,
        workspace_id=scenario.workspace_id,
        entity_id=change.entity_id,
    )
    stored = jsonable_encoder(request.changes)
    expected = _expected_revision(change)
    if expected is not None:
        stored[EXPECTED_REVISION_KEY] = expected
    with transaction(session):
        change.changes = stored
        change.revision += 1
        change.updated_at = utc_now()
        scenario.revision += 1
        scenario.updated_at = utc_now()
        session.add(change)
        session.add(scenario)
    return _change_response(change)


def delete_scenario_change(session: Session, scenario_id: UUID, change_id: UUID) -> UUID:
    scenario = _require_draft(session, scenario_id)
    repository = ScenarioChangeRepository(session)
    change = repository.get(change_id)
    if change is None or change.scenario_id != scenario.id:
        raise DomainNotFoundError("scenario_change", change_id)
    with transaction(session):
        repository.delete(change)
        scenario.revision += 1
        scenario.updated_at = utc_now()
        session.add(scenario)
    return change_id


def preview_overlay(
    primary_record: dict[str, Any] | None,
    change: ScenarioChange,
) -> dict[str, Any] | None:
    """Return a detached preview; never mutate the primary record or database row."""
    if change.operation == ScenarioOperation.DELETE:
        return None
    patch = _public_patch(change)
    if change.operation == ScenarioOperation.CREATE:
        return deepcopy(patch)
    if primary_record is None:
        raise DomainValidationError(
            "scenario_primary_missing", "An update overlay requires an existing primary record."
        )
    preview = deepcopy(primary_record)
    preview.update(deepcopy(patch))
    return preview


def _json_record(record: Any) -> dict[str, Any]:
    encoded = jsonable_encoder(record.model_dump())
    return cast(dict[str, Any], encoded)


def _snapshot(session: Session, workspace_id: UUID) -> dict[DomainEntityType, list[dict[str, Any]]]:
    snapshot: dict[DomainEntityType, list[dict[str, Any]]] = {}
    for entity_type, model in TARGET_MODELS.items():
        snapshot[entity_type] = [
            _json_record(item)
            for item in session.exec(
                select(model).where(
                    col(model.workspace_id) == workspace_id,
                    col(model.deleted_at).is_(None),
                )
            ).all()
        ]
    snapshot[DomainEntityType.FINANCIAL_ACCOUNT] = [
        _json_record(item)
        for item in session.exec(
            select(FinancialAccount).where(
                col(FinancialAccount.workspace_id) == workspace_id,
                col(FinancialAccount.deleted_at).is_(None),
            )
        ).all()
    ]
    snapshot[DomainEntityType.TRANSACTION] = [
        _json_record(item)
        for item in session.exec(
            select(Transaction).where(
                col(Transaction.workspace_id) == workspace_id,
                col(Transaction.deleted_at).is_(None),
            )
        ).all()
    ]
    return snapshot


def _apply_snapshot_changes(
    snapshot: dict[DomainEntityType, list[dict[str, Any]]],
    changes: list[ScenarioChange],
) -> dict[DomainEntityType, list[dict[str, Any]]]:
    projected = deepcopy(snapshot)
    for change in changes:
        records = projected[change.entity_type]
        index = next(
            (
                position
                for position, item in enumerate(records)
                if item["id"] == str(change.entity_id)
            ),
            None,
        )
        patch = _public_patch(change)
        if change.entity_type == DomainEntityType.COMMITMENT:
            patch = _mapped_patch(change.entity_type, patch)
        if change.operation == ScenarioOperation.CREATE:
            records.append({"id": str(change.entity_id), **deepcopy(patch)})
        elif change.operation == ScenarioOperation.UPDATE and index is not None:
            records[index].update(deepcopy(patch))
        elif change.operation == ScenarioOperation.DELETE and index is not None:
            records.pop(index)
    return projected


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _metrics(snapshot: dict[DomainEntityType, list[dict[str, Any]]]) -> ScenarioMetrics:
    accounts = snapshot[DomainEntityType.FINANCIAL_ACCOUNT]
    transactions = snapshot[DomainEntityType.TRANSACTION]
    planned = snapshot[DomainEntityType.PLANNED_TRANSACTION]
    balances: dict[str, int] = defaultdict(int)
    buffers: dict[str, int] = defaultdict(int)
    account_currency: dict[str, str] = {}
    for account in accounts:
        currency = str(account["currency_code"])
        account_currency[str(account["id"])] = currency
        balances[currency] += int(account.get("opening_balance_minor") or 0)
        buffers[currency] += int(account.get("financial_buffer_minor") or 0)
    for item in transactions:
        currency = str(item["currency_code"])
        kind = str(item["transaction_type"])
        amount = int(item["amount_minor"])
        if kind == "income":
            balances[currency] += amount
        elif kind == "expense":
            balances[currency] -= amount
    running = dict(balances)
    lowest = dict(balances)
    cash_flow: dict[str, int] = defaultdict(int)
    active_plans = [item for item in planned if str(item.get("status", "planned")) == "planned"]
    active_plans.sort(key=lambda item: str(item.get("planned_for", "")))
    for item in active_plans:
        currency = str(
            item.get("currency_code") or account_currency.get(str(item.get("account_id")), "EUR")
        )
        kind = str(item.get("transaction_type"))
        amount = int(item.get("amount_minor") or 0)
        delta = amount if kind == "income" else -amount if kind == "expense" else 0
        cash_flow[currency] += delta
        running[currency] = running.get(currency, 0) + delta
        lowest[currency] = min(lowest.get(currency, running[currency]), running[currency])
    commitments = snapshot[DomainEntityType.COMMITMENT]
    commitment_requirements: dict[str, int] = defaultdict(int)
    for item in commitments:
        if str(item.get("status")) not in {"planned", "active"}:
            continue
        requirement_currency = item.get("currency_code")
        if requirement_currency:
            commitment_requirements[str(requirement_currency)] += int(
                item.get("financial_buffer_requirement_minor") or 0
            )
    currencies = sorted(set(balances) | set(cash_flow) | set(commitment_requirements))
    currency_rows = [
        ScenarioCurrencyProjection(
            currency=currency,
            projected_cash_flow_minor=cash_flow.get(currency, 0),
            lowest_balance_minor=lowest.get(currency, balances.get(currency, 0)),
            financial_buffer_violations=int(
                lowest.get(currency, balances.get(currency, 0))
                < buffers.get(currency, 0) + commitment_requirements.get(currency, 0)
            ),
        )
        for currency in currencies
    ]
    tasks = snapshot[DomainEntityType.TASK]
    active_tasks = [
        item for item in tasks if str(item.get("status")) not in {"completed", "cancelled"}
    ]
    task_time = sum(int(item.get("estimated_duration_minutes") or 0) for item in active_tasks)
    commitment_time = sum(
        int(item.get("estimated_duration_minutes") or 0)
        for item in commitments
        if str(item.get("status")) in {"planned", "active"}
    )
    unscheduled = sum(
        1
        for item in active_tasks
        if item.get("estimated_duration_minutes") is not None
        and item.get("scheduled_start_at") is None
    )
    events = [
        item
        for item in snapshot[DomainEntityType.CALENDAR_EVENT]
        if str(item.get("status")) != "cancelled" and not item.get("all_day")
    ]
    conflicts = 0
    for index, first in enumerate(events):
        first_start = _parse_datetime(first.get("starts_at"))
        first_end = _parse_datetime(first.get("ends_at"))
        if first_start is None or first_end is None:
            continue
        first_start -= timedelta(
            minutes=int(first.get("preparation_buffer_minutes") or 0)
            + int(first.get("travel_buffer_minutes") or 0)
        )
        first_end += timedelta(minutes=int(first.get("recovery_buffer_minutes") or 0))
        for second in events[index + 1 :]:
            second_start = _parse_datetime(second.get("starts_at"))
            second_end = _parse_datetime(second.get("ends_at"))
            if second_start is None or second_end is None:
                continue
            second_start -= timedelta(
                minutes=int(second.get("preparation_buffer_minutes") or 0)
                + int(second.get("travel_buffer_minutes") or 0)
            )
            second_end += timedelta(minutes=int(second.get("recovery_buffer_minutes") or 0))
            conflicts += int(first_start < second_end and second_start < first_end)
    goals = [
        item
        for item in snapshot[DomainEntityType.GOAL]
        if str(item.get("status")) not in {"cancelled"}
    ]
    goal_progress = (
        sum(int(item.get("progress_basis_points") or 0) for item in goals) // len(goals)
        if goals
        else 0
    )
    statuses = Counter(str(item.get("status", "draft")) for item in commitments)
    return ScenarioMetrics(
        currencies=currency_rows,
        time_required_minutes=task_time + commitment_time,
        schedule_conflicts=conflicts,
        goal_progress_basis_points=goal_progress,
        unscheduled_tasks=unscheduled,
        commitment_status=dict(sorted(statuses.items())),
    )


def _differences(baseline: ScenarioMetrics, projected: ScenarioMetrics) -> ScenarioMetricDelta:
    base_currency = {item.currency: item for item in baseline.currencies}
    projected_currency = {item.currency: item for item in projected.currencies}
    currencies = sorted(set(base_currency) | set(projected_currency))
    return ScenarioMetricDelta(
        projected_cash_flow_minor={
            currency: projected_currency.get(
                currency,
                ScenarioCurrencyProjection(
                    currency=currency,
                    projected_cash_flow_minor=0,
                    lowest_balance_minor=0,
                    financial_buffer_violations=0,
                ),
            ).projected_cash_flow_minor
            - base_currency.get(
                currency,
                ScenarioCurrencyProjection(
                    currency=currency,
                    projected_cash_flow_minor=0,
                    lowest_balance_minor=0,
                    financial_buffer_violations=0,
                ),
            ).projected_cash_flow_minor
            for currency in currencies
        },
        lowest_balance_minor={
            currency: projected_currency.get(
                currency,
                ScenarioCurrencyProjection(
                    currency=currency,
                    projected_cash_flow_minor=0,
                    lowest_balance_minor=0,
                    financial_buffer_violations=0,
                ),
            ).lowest_balance_minor
            - base_currency.get(
                currency,
                ScenarioCurrencyProjection(
                    currency=currency,
                    projected_cash_flow_minor=0,
                    lowest_balance_minor=0,
                    financial_buffer_violations=0,
                ),
            ).lowest_balance_minor
            for currency in currencies
        },
        financial_buffer_violations=sum(
            item.financial_buffer_violations for item in projected.currencies
        )
        - sum(item.financial_buffer_violations for item in baseline.currencies),
        time_required_minutes=projected.time_required_minutes - baseline.time_required_minutes,
        schedule_conflicts=projected.schedule_conflicts - baseline.schedule_conflicts,
        goal_progress_basis_points=projected.goal_progress_basis_points
        - baseline.goal_progress_basis_points,
        unscheduled_tasks=projected.unscheduled_tasks - baseline.unscheduled_tasks,
        commitment_status={
            status: projected.commitment_status.get(status, 0)
            - baseline.commitment_status.get(status, 0)
            for status in sorted(set(baseline.commitment_status) | set(projected.commitment_status))
        },
    )


def _stale_reasons(
    session: Session, scenario: Scenario, changes: list[ScenarioChange]
) -> list[str]:
    reasons: list[str] = []
    for change in changes:
        current = _target(session, scenario.workspace_id, change.entity_type, change.entity_id)
        expected = _expected_revision(change)
        if change.operation == ScenarioOperation.CREATE:
            if current is not None:
                reasons.append(f"{change.entity_type.value} {change.entity_id} now exists")
        elif current is None:
            reasons.append(f"{change.entity_type.value} {change.entity_id} was removed")
        elif expected is None or current.revision != expected:
            reasons.append(
                f"{change.entity_type.value} {change.entity_id} changed from revision "
                f"{expected or 'unknown'} to {current.revision}"
            )
    return reasons


def _plan(
    session: Session, scenario: Scenario, changes: list[ScenarioChange]
) -> list[ScenarioPlanStep]:
    steps: list[ScenarioPlanStep] = []
    for change in changes:
        current = _target(session, scenario.workspace_id, change.entity_type, change.entity_id)
        patch = _public_patch(change)
        before = _json_record(current) if current is not None else {}
        fields = [
            ScenarioPlanField(
                field=field,
                before=before.get(COMMITMENT_FIELD_MAP.get(field, field)),
                after=value if change.operation != ScenarioOperation.DELETE else None,
            )
            for field, value in sorted(patch.items())
        ]
        if change.operation == ScenarioOperation.DELETE:
            fields = [ScenarioPlanField(field="record", before="Existing record", after=None)]
        title = str(
            before.get("title")
            or before.get("payee")
            or patch.get("title")
            or patch.get("payee")
            or f"{change.entity_type.value} record"
        )
        steps.append(
            ScenarioPlanStep(
                change_id=change.id,
                operation=change.operation,
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                title=title,
                expected_revision=_expected_revision(change),
                fields=fields,
            )
        )
    return steps


def preview_scenario(session: Session, scenario_id: UUID) -> ScenarioPreviewResponse:
    scenario_response = get_scenario(session, scenario_id)
    workspace = get_current_workspace(session)
    scenario = ScenarioRepository(session).get_active(workspace.id, scenario_id)
    assert scenario is not None
    changes = ScenarioChangeRepository(session).list_for_scenario(scenario_id)
    snapshot = _snapshot(session, workspace.id)
    projected_snapshot = _apply_snapshot_changes(snapshot, changes)
    baseline = _metrics(snapshot)
    projected = _metrics(projected_snapshot)
    stale_reasons = _stale_reasons(session, scenario, changes)
    steps = _plan(session, scenario, changes)
    fingerprint_payload = {
        "scenario_id": str(scenario.id),
        "scenario_revision": scenario.revision,
        "steps": jsonable_encoder(steps),
        "baseline": jsonable_encoder(baseline),
        "projected": jsonable_encoder(projected),
        "stale_reasons": stale_reasons,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ScenarioPreviewResponse(
        scenario=scenario_response,
        changes=[_change_response(item) for item in changes],
        baseline=baseline,
        projected=projected,
        differences=_differences(baseline, projected),
        exact_change_plan=steps,
        stale=bool(stale_reasons),
        stale_reasons=stale_reasons,
        preview_fingerprint=fingerprint,
        assumptions=[
            "Money remains separated by currency; no exchange-rate conversion is performed.",
            "Projected cash flow includes current one-off planned transactions.",
            "Time required combines active task estimates and explicit commitment requirements.",
            "Calendar conflicts include preparation, travel, and recovery buffers.",
            "Preview is deterministic and does not modify primary records.",
        ],
        calculated_at=datetime.now(UTC),
    )


def compare_scenarios(session: Session, scenario_ids: list[UUID]) -> ScenarioCompareResponse:
    return ScenarioCompareResponse(
        previews=[preview_scenario(session, scenario_id) for scenario_id in scenario_ids]
    )


def _apply_change(session: Session, scenario: Scenario, change: ScenarioChange) -> None:
    current = _target(session, scenario.workspace_id, change.entity_type, change.entity_id)
    patch = _public_patch(change)
    if change.operation == ScenarioOperation.CREATE:
        values = _validate_prospective(
            change.entity_type,
            None,
            patch,
            workspace_id=scenario.workspace_id,
            entity_id=change.entity_id,
        )
        model = TARGET_MODELS[change.entity_type]
        record = model.model_validate(
            {"id": change.entity_id, "workspace_id": scenario.workspace_id, **values}
        )
        session.add(record)
        title = str(
            getattr(record, "title", None)
            or getattr(record, "payee", None)
            or change.entity_type.value
        )
    else:
        assert current is not None
        title = str(
            getattr(current, "title", None)
            or getattr(current, "payee", None)
            or change.entity_type.value
        )
        if change.operation == ScenarioOperation.DELETE:
            current.deleted_at = utc_now()
        else:
            values = _validate_prospective(
                change.entity_type,
                current,
                patch,
                workspace_id=scenario.workspace_id,
                entity_id=change.entity_id,
            )
            for key, value in values.items():
                setattr(current, key, value)
        current.revision += 1
        current.updated_at = utc_now()
        session.add(current)
    emit_timeline_event(
        session,
        workspace_id=scenario.workspace_id,
        entity_type=change.entity_type,
        entity_id=change.entity_id,
        action=f"scenario_{change.operation.value}_applied",
        title=f"Scenario applied to {title}",
        payload={"scenario_id": str(scenario.id), "fields": sorted(patch)},
    )


def accept_scenario(
    session: Session, scenario_id: UUID, request: ScenarioAcceptRequest
) -> ScenarioAcceptResponse:
    scenario = _require_draft(session, scenario_id)
    if scenario.revision != request.revision:
        raise RevisionConflictError("scenario", request.revision, scenario.revision)
    preview = preview_scenario(session, scenario_id)
    if preview.stale:
        raise DomainConflictError(
            "scenario_stale",
            "The scenario cannot be accepted because source records changed.",
            {"reasons": preview.stale_reasons},
        )
    if preview.preview_fingerprint != request.preview_fingerprint:
        raise DomainConflictError(
            "scenario_preview_changed",
            "The scenario preview changed. Review the exact change plan again before accepting.",
        )
    changes = ScenarioChangeRepository(session).list_for_scenario(scenario.id)
    accepted_at = utc_now()
    with transaction(session):
        for change in changes:
            _apply_change(session, scenario, change)
        scenario.status = ScenarioStatus.ACCEPTED
        scenario.revision += 1
        scenario.updated_at = accepted_at
        session.add(scenario)
        emit_timeline_event(
            session,
            workspace_id=scenario.workspace_id,
            entity_type=DomainEntityType.SCENARIO,
            entity_id=scenario.id,
            action="scenario_accepted",
            title=f"Scenario accepted: {scenario.name}",
            payload={"applied_change_count": len(changes)},
        )
    return ScenarioAcceptResponse(
        scenario=get_scenario(session, scenario.id),
        applied_steps=preview.exact_change_plan,
        accepted_at=accepted_at,
    )
