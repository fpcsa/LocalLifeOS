from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import CategoryKind, FinancialAccountType
from app.schemas.common import (
    CurrencyCode,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
)
from app.schemas.finance import (
    AccountLedgerResponse,
    FinancialAccountCreateRequest,
    FinancialAccountResponse,
    FinancialAccountUpdateRequest,
    TransactionCategoryCreateRequest,
    TransactionCategoryResponse,
    TransactionCategoryUpdateRequest,
)
from app.services.finance_accounts import (
    create_account,
    delete_account,
    get_account,
    get_account_ledger,
    list_accounts,
    update_account,
)
from app.services.finance_categories import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/accounts", response_model=ListEnvelope[FinancialAccountResponse])
def read_accounts(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    currency: CurrencyCode | None = None,
    account_type: FinancialAccountType | None = None,
    order: Literal["asc", "desc"] = "asc",
) -> ListEnvelope[FinancialAccountResponse]:
    items, total = list_accounts(
        session,
        page=page,
        page_size=page_size,
        query=query,
        currency=currency,
        account_type=account_type,
        order=order,
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
    "/accounts",
    response_model=DataEnvelope[FinancialAccountResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_account(
    create_data: FinancialAccountCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[FinancialAccountResponse]:
    return DataEnvelope(data=create_account(session, create_data))


@router.get("/accounts/{account_id}/ledger", response_model=DataEnvelope[AccountLedgerResponse])
def read_account_ledger(
    account_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[AccountLedgerResponse]:
    return DataEnvelope(data=get_account_ledger(session, account_id))


@router.get("/accounts/{account_id}", response_model=DataEnvelope[FinancialAccountResponse])
def read_account(
    account_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[FinancialAccountResponse]:
    return DataEnvelope(data=get_account(session, account_id))


@router.patch("/accounts/{account_id}", response_model=DataEnvelope[FinancialAccountResponse])
def patch_account(
    account_id: UUID,
    update_data: FinancialAccountUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[FinancialAccountResponse]:
    return DataEnvelope(data=update_account(session, account_id, update_data))


@router.delete("/accounts/{account_id}", response_model=DataEnvelope[DeletedResource])
def remove_account(
    account_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_account(session, account_id, revision))


@router.get("/categories", response_model=ListEnvelope[TransactionCategoryResponse])
def read_categories(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=120)] = None,
    kind: CategoryKind | None = None,
    order: Literal["asc", "desc"] = "asc",
) -> ListEnvelope[TransactionCategoryResponse]:
    items, total = list_categories(
        session,
        page=page,
        page_size=page_size,
        query=query,
        kind=kind,
        order=order,
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
    "/categories",
    response_model=DataEnvelope[TransactionCategoryResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_category(
    create_data: TransactionCategoryCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[TransactionCategoryResponse]:
    return DataEnvelope(data=create_category(session, create_data))


@router.get("/categories/{category_id}", response_model=DataEnvelope[TransactionCategoryResponse])
def read_category(
    category_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[TransactionCategoryResponse]:
    return DataEnvelope(data=get_category(session, category_id))


@router.patch("/categories/{category_id}", response_model=DataEnvelope[TransactionCategoryResponse])
def patch_category(
    category_id: UUID,
    update_data: TransactionCategoryUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[TransactionCategoryResponse]:
    return DataEnvelope(data=update_category(session, category_id, update_data))


@router.delete("/categories/{category_id}", response_model=DataEnvelope[DeletedResource])
def remove_category(
    category_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_category(session, category_id, revision))
