from fastapi import APIRouter

from app.schemas.common import DataEnvelope
from app.schemas.resources import MetaEnumsResponse
from app.services.meta import get_enum_values

router = APIRouter(tags=["metadata"])


@router.get("/meta/enums", response_model=DataEnvelope[MetaEnumsResponse])
def read_enums() -> DataEnvelope[MetaEnumsResponse]:
    return DataEnvelope(data=MetaEnumsResponse(enums=get_enum_values()))
