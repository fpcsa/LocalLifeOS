from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import SessionDependency
from app.schemas.common import CurrencyCode, DataEnvelope
from app.schemas.finance import (
    CashFlowReportResponse,
    CommittedBalanceReportResponse,
    SpendingByCategoryReportResponse,
)
from app.services.finance_reports import (
    cash_flow_report,
    committed_balance_report,
    spending_by_category_report,
)

router = APIRouter(prefix="/finance/reports", tags=["finance-reports"])


@router.get("/cash-flow", response_model=DataEnvelope[CashFlowReportResponse])
def read_cash_flow_report(
    session: SessionDependency,
    start_date: date,
    months: Annotated[int, Query(ge=1, le=60)] = 12,
    currency: CurrencyCode | None = None,
) -> DataEnvelope[CashFlowReportResponse]:
    return DataEnvelope(
        data=cash_flow_report(
            session,
            start_date=start_date,
            months=months,
            currency=currency,
        )
    )


@router.get(
    "/spending-by-category",
    response_model=DataEnvelope[SpendingByCategoryReportResponse],
)
def read_spending_by_category_report(
    session: SessionDependency,
    start_date: date,
    end_date: date,
    currency: CurrencyCode | None = None,
) -> DataEnvelope[SpendingByCategoryReportResponse]:
    return DataEnvelope(
        data=spending_by_category_report(
            session,
            start_date=start_date,
            end_date=end_date,
            currency=currency,
        )
    )


@router.get(
    "/committed-balance",
    response_model=DataEnvelope[CommittedBalanceReportResponse],
)
def read_committed_balance_report(
    session: SessionDependency,
    as_of: date,
    end_date: date,
    currency: CurrencyCode | None = None,
) -> DataEnvelope[CommittedBalanceReportResponse]:
    return DataEnvelope(
        data=committed_balance_report(
            session,
            as_of=as_of,
            end_date=end_date,
            currency=currency,
        )
    )
