from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    timestamp: datetime


class SystemInfoResponse(BaseModel):
    application: str
    version: str
    environment: str
    storage: Literal["sqlite"]
    timezone: str
    telemetry_enabled: Literal[False]
    external_requests_enabled: bool
    network_mode: Literal["loopback-only"]
    data_directory: Path
