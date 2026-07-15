from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Index
from sqlmodel import Field

from app.models.common import UTCDateTime, WorkspaceEntityBase


class SchedulingPreview(WorkspaceEntityBase, table=True):
    __tablename__ = "scheduling_previews"
    __table_args__ = (
        CheckConstraint(
            "length(source_fingerprint) = 64",
            name="ck_scheduling_previews_fingerprint_length",
        ),
        CheckConstraint(
            "horizon_end_at > horizon_start_at",
            name="ck_scheduling_previews_horizon",
        ),
        CheckConstraint("revision >= 1", name="ck_scheduling_previews_revision_positive"),
        Index(
            "ix_scheduling_previews_workspace_created",
            "workspace_id",
            "created_at",
        ),
    )

    commitment_id: UUID | None = Field(
        default=None,
        foreign_key="commitments.id",
        ondelete="SET NULL",
        index=True,
    )
    horizon_start_at: datetime = Field(sa_type=UTCDateTime)
    horizon_end_at: datetime = Field(sa_type=UTCDateTime)
    solver_status: str = Field(max_length=32)
    source_fingerprint: str = Field(min_length=64, max_length=64)
    source_snapshot: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    request_payload: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    result_payload: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    expires_at: datetime = Field(sa_type=UTCDateTime)
    applied_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
