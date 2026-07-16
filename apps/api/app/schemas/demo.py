from __future__ import annotations

from typing import Annotated

from pydantic import Field

from app.schemas.common import ApiModel


class DemoDataSummary(ApiModel):
    dataset_version: str
    synthetic: bool = True
    anchor_date: str
    records_created: Annotated[dict[str, int], Field(min_length=1)]
    scenario_labels: Annotated[list[str], Field(min_length=5)]
    attachment_labels: Annotated[list[str], Field(min_length=2)]
    conflict_count: int = Field(ge=2)
    budget_shortfall_count: int = Field(ge=1)


class DemoDataResetSummary(ApiModel):
    dataset_version: str
    records_removed: int = Field(ge=0)
    attachment_files_removed: int = Field(ge=0)
