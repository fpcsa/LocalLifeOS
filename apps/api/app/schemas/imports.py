from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models import ImportBatchStatus, ImportKind, ImportRowStatus
from app.schemas.common import ApiModel, CurrencyCode


class ImportIssue(ApiModel):
    code: str
    message: str
    field: str | None = None


class ImportBatchResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    kind: ImportKind
    status: ImportBatchStatus
    original_filename: str
    source_fingerprint: str
    detected_encoding: str | None
    detected_delimiter: str | None
    mapping_profile_id: UUID | None
    total_rows: int
    new_count: int
    changed_count: int
    duplicate_count: int
    invalid_count: int
    imported_count: int
    summary: dict[str, object]
    applied_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ImportRowResponse(ApiModel):
    id: UUID
    batch_id: UUID
    row_number: int
    status: ImportRowStatus
    included: bool
    fingerprint: str | None
    raw_data: dict[str, object]
    normalized_data: dict[str, object]
    issues: list[ImportIssue]
    duplicate_kind: str | None
    duplicate_target_id: UUID | None
    target_id: UUID | None
    revision: int


class ImportPreviewResponse(ApiModel):
    batch: ImportBatchResponse
    columns: list[str] = Field(default_factory=list)
    rows: list[ImportRowResponse]


class ImportApplyRequest(ApiModel):
    included_row_ids: list[UUID] | None = Field(default=None, max_length=10_000)

    @field_validator("included_row_ids")
    @classmethod
    def unique_rows(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("included_row_ids cannot contain duplicates")
        return value


class ImportRowSelectionRequest(ApiModel):
    revision: int = Field(ge=1)
    included: bool


class CsvColumnMapping(ApiModel):
    date: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=255)
    amount: str | None = Field(default=None, min_length=1, max_length=255)
    debit: str | None = Field(default=None, min_length=1, max_length=255)
    credit: str | None = Field(default=None, min_length=1, max_length=255)
    currency: str | None = Field(default=None, min_length=1, max_length=255)
    account: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=255)
    external_id: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_amount_shape(self) -> Self:
        if self.amount is None and self.debit is None and self.credit is None:
            raise ValueError("map amount or at least one debit/credit column")
        if self.amount is not None and (self.debit is not None or self.credit is not None):
            raise ValueError("map either amount or debit/credit columns, not both")
        return self


class CsvMappingRequest(ApiModel):
    columns: CsvColumnMapping
    date_format: str | None = Field(default=None, max_length=80)
    decimal_separator: str = Field(default=".", pattern=r"^[.,]$")
    amount_positive_is_income: bool = True
    default_currency: CurrencyCode | None = None
    default_account_id: UUID | None = None
    default_category_id: UUID | None = None
    profile_name: str | None = Field(default=None, min_length=1, max_length=160)
    save_profile: bool = False

    @model_validator(mode="after")
    def validate_defaults(self) -> Self:
        if self.columns.account is None and self.default_account_id is None:
            raise ValueError("map an account column or choose a default account")
        if self.columns.currency is None and self.default_currency is None:
            raise ValueError("map a currency column or choose a default currency")
        if self.save_profile and self.profile_name is None:
            raise ValueError("profile_name is required when save_profile is true")
        return self


class CsvMappingProfileCreateRequest(CsvMappingRequest):
    name: str = Field(min_length=1, max_length=160)
    save_profile: bool = False
    profile_name: str | None = None
    delimiter: str | None = Field(default=None, max_length=1)
    encoding: str | None = Field(default=None, max_length=40)


class CsvMappingProfileUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    columns: CsvColumnMapping | None = None
    date_format: str | None = Field(default=None, max_length=80)
    decimal_separator: str | None = Field(default=None, pattern=r"^[.,]$")
    amount_positive_is_income: bool | None = None
    default_currency: CurrencyCode | None = None
    default_account_id: UUID | None = None
    default_category_id: UUID | None = None
    delimiter: str | None = Field(default=None, max_length=1)
    encoding: str | None = Field(default=None, max_length=40)


class CsvMappingProfileResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    columns: dict[str, str | None]
    date_format: str | None
    decimal_separator: str
    amount_positive_is_income: bool
    default_currency: str | None
    default_account_id: UUID | None
    default_category_id: UUID | None
    delimiter: str | None
    encoding: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class CalendarExportRequest(ApiModel):
    event_ids: list[UUID] | None = Field(default=None, max_length=10_000)
