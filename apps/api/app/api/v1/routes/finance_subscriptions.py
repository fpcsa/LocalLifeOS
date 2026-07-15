from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import SubscriptionStatus
from app.schemas.common import (
    CurrencyCode,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
)
from app.schemas.finance import (
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)
from app.services.subscriptions import (
    create_subscription,
    delete_subscription,
    get_subscription,
    list_subscriptions,
    update_subscription,
)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/subscriptions", response_model=ListEnvelope[SubscriptionResponse])
def read_subscriptions(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    subscription_status: Annotated[SubscriptionStatus | None, Query(alias="status")] = None,
    currency: CurrencyCode | None = None,
) -> ListEnvelope[SubscriptionResponse]:
    items, total = list_subscriptions(
        session,
        page=page,
        page_size=page_size,
        status=subscription_status,
        currency=currency,
    )
    return ListEnvelope(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post(
    "/subscriptions",
    response_model=DataEnvelope[SubscriptionResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_subscription(
    create_data: SubscriptionCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[SubscriptionResponse]:
    return DataEnvelope(data=create_subscription(session, create_data))


@router.get("/subscriptions/{subscription_id}", response_model=DataEnvelope[SubscriptionResponse])
def read_subscription(
    subscription_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[SubscriptionResponse]:
    return DataEnvelope(data=get_subscription(session, subscription_id))


@router.patch("/subscriptions/{subscription_id}", response_model=DataEnvelope[SubscriptionResponse])
def patch_subscription(
    subscription_id: UUID,
    update_data: SubscriptionUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[SubscriptionResponse]:
    return DataEnvelope(data=update_subscription(session, subscription_id, update_data))


@router.delete("/subscriptions/{subscription_id}", response_model=DataEnvelope[DeletedResource])
def remove_subscription(
    subscription_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_subscription(session, subscription_id, revision))
