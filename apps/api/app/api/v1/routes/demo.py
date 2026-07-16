from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.schemas.common import DataEnvelope
from app.schemas.demo import DemoDataResetSummary, DemoDataSummary
from app.services.demo_data import load_demo_data, reset_demo_data

router = APIRouter(prefix="/demo", tags=["demo data"])


@router.post("/load", response_model=DataEnvelope[DemoDataSummary])
def post_demo_load(session: SessionDependency) -> DataEnvelope[DemoDataSummary]:
    """Load or deterministically refresh the reserved synthetic judge dataset."""
    return DataEnvelope(data=load_demo_data(session))


@router.post("/reset", response_model=DataEnvelope[DemoDataResetSummary])
def post_demo_reset(session: SessionDependency) -> DataEnvelope[DemoDataResetSummary]:
    """Remove only records and files that use LocalLife's reserved demo identifiers."""
    return DataEnvelope(data=reset_demo_data(session))
