from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import PlannedTransactionStatus, TransactionType
from app.schemas.common import (
    AwareDateTime,
    CurrencyCode,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
)
from app.schemas.finance import (
    FinanceRevisionRequest,
    FulfillPlannedTransactionRequest,
    PlannedFulfillmentResponse,
    PlannedTransactionCreateRequest,
    PlannedTransactionResponse,
    PlannedTransactionUpdateRequest,
    TransactionCreateRequest,
    TransactionResponse,
    TransactionUpdateRequest,
    TransferCreateRequest,
)
from app.services.finance_transactions import (
    cancel_planned_transaction,
    create_finance_transaction,
    create_planned_transaction,
    create_transfer,
    delete_finance_transaction,
    delete_planned_transaction,
    fulfill_planned_transaction,
    get_planned_transaction,
    get_transaction,
    list_planned_transactions,
    list_transactions,
    update_finance_transaction,
    update_planned_transaction,
)

router = APIRouter(prefix="/finance", tags=["finance"])


def _transaction_envelope(
    items: list[TransactionResponse],
    total: int,
    page: int,
    page_size: int,
) -> ListEnvelope[TransactionResponse]:
    return ListEnvelope(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/transactions/planned", response_model=ListEnvelope[PlannedTransactionResponse])
def read_planned_transactions(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    account_id: UUID | None = None,
    planned_status: Annotated[PlannedTransactionStatus | None, Query(alias="status")] = None,
    currency: CurrencyCode | None = None,
    start: AwareDateTime | None = None,
    end: AwareDateTime | None = None,
) -> ListEnvelope[PlannedTransactionResponse]:
    items, total = list_planned_transactions(
        session,
        page=page,
        page_size=page_size,
        account_id=account_id,
        status=planned_status,
        currency=currency,
        start=start,
        end=end,
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
    "/transactions/planned",
    response_model=DataEnvelope[PlannedTransactionResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_planned_transaction(
    create_data: PlannedTransactionCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[PlannedTransactionResponse]:
    return DataEnvelope(data=create_planned_transaction(session, create_data))


@router.get(
    "/transactions/planned/{planned_id}",
    response_model=DataEnvelope[PlannedTransactionResponse],
)
def read_planned_transaction(
    planned_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[PlannedTransactionResponse]:
    return DataEnvelope(data=get_planned_transaction(session, planned_id))


@router.patch(
    "/transactions/planned/{planned_id}",
    response_model=DataEnvelope[PlannedTransactionResponse],
)
def patch_planned_transaction(
    planned_id: UUID,
    update_data: PlannedTransactionUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[PlannedTransactionResponse]:
    return DataEnvelope(data=update_planned_transaction(session, planned_id, update_data))


@router.post(
    "/transactions/planned/{planned_id}/cancel",
    response_model=DataEnvelope[PlannedTransactionResponse],
)
def post_planned_cancel(
    planned_id: UUID,
    request: FinanceRevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[PlannedTransactionResponse]:
    return DataEnvelope(data=cancel_planned_transaction(session, planned_id, request.revision))


@router.post(
    "/transactions/planned/{planned_id}/fulfill",
    response_model=DataEnvelope[PlannedFulfillmentResponse],
)
def post_planned_fulfillment(
    planned_id: UUID,
    request: FulfillPlannedTransactionRequest,
    session: SessionDependency,
) -> DataEnvelope[PlannedFulfillmentResponse]:
    planned, actual = fulfill_planned_transaction(session, planned_id, request)
    return DataEnvelope(data=PlannedFulfillmentResponse(planned=planned, actual=actual))


@router.delete(
    "/transactions/planned/{planned_id}",
    response_model=DataEnvelope[DeletedResource],
)
def remove_planned_transaction(
    planned_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_planned_transaction(session, planned_id, revision))


@router.get("/transactions", response_model=ListEnvelope[TransactionResponse])
def read_transactions(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=255)] = None,
    account_id: UUID | None = None,
    category_id: UUID | None = None,
    transaction_type: Annotated[TransactionType | None, Query(alias="type")] = None,
    currency: CurrencyCode | None = None,
    start: AwareDateTime | None = None,
    end: AwareDateTime | None = None,
    order: Literal["asc", "desc"] = "desc",
) -> ListEnvelope[TransactionResponse]:
    items, total = list_transactions(
        session,
        page=page,
        page_size=page_size,
        query=query,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        currency=currency,
        start=start,
        end=end,
        order=order,
    )
    return _transaction_envelope(items, total, page, page_size)


@router.post(
    "/transactions",
    response_model=DataEnvelope[TransactionResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_transaction(
    create_data: TransactionCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[TransactionResponse]:
    return DataEnvelope(data=create_finance_transaction(session, create_data))


@router.get("/transactions/{transaction_id}", response_model=DataEnvelope[TransactionResponse])
def read_transaction(
    transaction_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[TransactionResponse]:
    return DataEnvelope(data=get_transaction(session, transaction_id))


@router.patch("/transactions/{transaction_id}", response_model=DataEnvelope[TransactionResponse])
def patch_transaction(
    transaction_id: UUID,
    update_data: TransactionUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[TransactionResponse]:
    return DataEnvelope(data=update_finance_transaction(session, transaction_id, update_data))


@router.delete("/transactions/{transaction_id}", response_model=DataEnvelope[DeletedResource])
def remove_transaction(
    transaction_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_finance_transaction(session, transaction_id, revision))


@router.get("/transfers", response_model=ListEnvelope[TransactionResponse])
def read_transfers(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListEnvelope[TransactionResponse]:
    items, total = list_transactions(
        session,
        page=page,
        page_size=page_size,
        query=None,
        account_id=None,
        category_id=None,
        transaction_type=TransactionType.TRANSFER,
        currency=None,
        start=None,
        end=None,
        order="desc",
    )
    return _transaction_envelope(items, total, page, page_size)


@router.post(
    "/transfers",
    response_model=DataEnvelope[TransactionResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_transfer(
    create_data: TransferCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[TransactionResponse]:
    return DataEnvelope(data=create_transfer(session, create_data))
