from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models.common import normalize_currency_code


def validate_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include a timezone offset")
    return value


def validate_timezone_name(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("timezone must be a valid IANA timezone name") from exc
    return value


CurrencyCode = Annotated[
    str,
    StringConstraints(min_length=3, max_length=3, to_upper=True),
    AfterValidator(normalize_currency_code),
]
AwareDateTime = Annotated[datetime, AfterValidator(validate_aware_datetime)]
TimezoneName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
    AfterValidator(validate_timezone_name),
]


class ApiModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class MoneyAmount(ApiModel):
    amount_minor: int
    currency_code: CurrencyCode


class PaginationMeta(ApiModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class DataEnvelope[DataT](ApiModel):
    data: DataT


class ListEnvelope[DataT](ApiModel):
    data: list[DataT]
    meta: PaginationMeta


class DeletedResource(ApiModel):
    id: UUID
    deleted: bool = True
