from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import RecurringTransactionStatus
from app.schemas.common import (
    CurrencyCode,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
)
from app.schemas.finance import (
    FinanceRevisionRequest,
    PlannedTransactionResponse,
    RecurringGenerationRequest,
    RecurringTransactionCreateRequest,
    RecurringTransactionResponse,
    RecurringTransactionUpdateRequest,
)
from app.services.finance_recurring import (
    create_recurring_transaction,
    delete_recurring_transaction,
    generate_recurring_occurrences,
    get_recurring_transaction,
    list_recurring_transactions,
    set_recurring_status,
    update_recurring_transaction,
)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/recurring", response_model=ListEnvelope[RecurringTransactionResponse])
def read_recurring_transactions(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    recurring_status: Annotated[RecurringTransactionStatus | None, Query(alias="status")] = None,
    currency: CurrencyCode | None = None,
) -> ListEnvelope[RecurringTransactionResponse]:
    items, total = list_recurring_transactions(
        session,
        page=page,
        page_size=page_size,
        status=recurring_status,
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
    "/recurring",
    response_model=DataEnvelope[RecurringTransactionResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_recurring_transaction(
    create_data: RecurringTransactionCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[RecurringTransactionResponse]:
    return DataEnvelope(data=create_recurring_transaction(session, create_data))


@router.get("/recurring/{rule_id}", response_model=DataEnvelope[RecurringTransactionResponse])
def read_recurring_transaction(
    rule_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[RecurringTransactionResponse]:
    return DataEnvelope(data=get_recurring_transaction(session, rule_id))


@router.patch("/recurring/{rule_id}", response_model=DataEnvelope[RecurringTransactionResponse])
def patch_recurring_transaction(
    rule_id: UUID,
    update_data: RecurringTransactionUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[RecurringTransactionResponse]:
    return DataEnvelope(data=update_recurring_transaction(session, rule_id, update_data))


@router.post(
    "/recurring/{rule_id}/generate",
    response_model=DataEnvelope[list[PlannedTransactionResponse]],
)
def post_recurring_generation(
    rule_id: UUID,
    request: RecurringGenerationRequest,
    session: SessionDependency,
) -> DataEnvelope[list[PlannedTransactionResponse]]:
    return DataEnvelope(data=generate_recurring_occurrences(session, rule_id, request))


@router.post(
    "/recurring/{rule_id}/pause",
    response_model=DataEnvelope[RecurringTransactionResponse],
)
def post_recurring_pause(
    rule_id: UUID,
    request: FinanceRevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[RecurringTransactionResponse]:
    return DataEnvelope(
        data=set_recurring_status(
            session, rule_id, request.revision, RecurringTransactionStatus.PAUSED
        )
    )


@router.post(
    "/recurring/{rule_id}/resume",
    response_model=DataEnvelope[RecurringTransactionResponse],
)
def post_recurring_resume(
    rule_id: UUID,
    request: FinanceRevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[RecurringTransactionResponse]:
    return DataEnvelope(
        data=set_recurring_status(
            session, rule_id, request.revision, RecurringTransactionStatus.ACTIVE
        )
    )


@router.post(
    "/recurring/{rule_id}/end",
    response_model=DataEnvelope[RecurringTransactionResponse],
)
def post_recurring_end(
    rule_id: UUID,
    request: FinanceRevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[RecurringTransactionResponse]:
    return DataEnvelope(
        data=set_recurring_status(
            session, rule_id, request.revision, RecurringTransactionStatus.ENDED
        )
    )


@router.delete("/recurring/{rule_id}", response_model=DataEnvelope[DeletedResource])
def remove_recurring_transaction(
    rule_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_recurring_transaction(session, rule_id, revision))
