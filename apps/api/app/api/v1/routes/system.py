from fastapi import APIRouter
from sqlmodel import select

from app.api.dependencies import SessionDependency
from app.core.config import get_settings
from app.models import SystemSetting
from app.schemas.system import SystemInfoResponse

router = APIRouter(tags=["system"])


@router.get("/system/info", response_model=SystemInfoResponse)
def system_info(session: SessionDependency) -> SystemInfoResponse:
    settings = get_settings()
    timezone_setting = session.exec(
        select(SystemSetting).where(SystemSetting.key == "user.timezone")
    ).first()
    timezone = timezone_setting.value if timezone_setting else settings.default_timezone

    return SystemInfoResponse(
        application="LocalLife OS",
        version=settings.app_version,
        environment=settings.env,
        storage="sqlite",
        timezone=timezone,
        telemetry_enabled=False,
        external_requests_enabled=False,
    )
