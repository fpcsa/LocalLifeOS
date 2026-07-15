from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import BudgetPeriod, GoalStatus
from app.schemas.common import (
    CurrencyCode,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
)
from app.schemas.finance import (
    BudgetConsumptionResponse,
    BudgetCreateRequest,
    BudgetResponse,
    BudgetUpdateRequest,
    SavingsGoalContributionRequest,
    SavingsGoalCreateRequest,
    SavingsGoalResponse,
    SavingsGoalUpdateRequest,
)
from app.services.finance_budgets import (
    create_budget,
    delete_budget,
    get_budget,
    list_budgets,
    update_budget,
)
from app.services.finance_reports import budget_consumption_report
from app.services.goals import (
    contribute_to_savings_goal,
    create_savings_goal,
    delete_savings_goal,
    get_savings_goal,
    list_savings_goals,
    update_savings_goal,
)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/budgets", response_model=ListEnvelope[BudgetResponse])
def read_budgets(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    period: BudgetPeriod | None = None,
    currency: CurrencyCode | None = None,
) -> ListEnvelope[BudgetResponse]:
    items, total = list_budgets(
        session,
        page=page,
        page_size=page_size,
        period=period,
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
    "/budgets",
    response_model=DataEnvelope[BudgetResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_budget(
    create_data: BudgetCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[BudgetResponse]:
    return DataEnvelope(data=create_budget(session, create_data))


@router.get(
    "/budgets/{budget_id}/consumption",
    response_model=DataEnvelope[BudgetConsumptionResponse],
)
def read_budget_consumption(
    budget_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[BudgetConsumptionResponse]:
    return DataEnvelope(data=budget_consumption_report(session, budget_id))


@router.get("/budgets/{budget_id}", response_model=DataEnvelope[BudgetResponse])
def read_budget(budget_id: UUID, session: SessionDependency) -> DataEnvelope[BudgetResponse]:
    return DataEnvelope(data=get_budget(session, budget_id))


@router.patch("/budgets/{budget_id}", response_model=DataEnvelope[BudgetResponse])
def patch_budget(
    budget_id: UUID,
    update_data: BudgetUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[BudgetResponse]:
    return DataEnvelope(data=update_budget(session, budget_id, update_data))


@router.delete("/budgets/{budget_id}", response_model=DataEnvelope[DeletedResource])
def remove_budget(
    budget_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_budget(session, budget_id, revision))


@router.get("/savings-goals", response_model=ListEnvelope[SavingsGoalResponse])
def read_savings_goals(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    goal_status: Annotated[GoalStatus | None, Query(alias="status")] = None,
    currency: CurrencyCode | None = None,
) -> ListEnvelope[SavingsGoalResponse]:
    items, total = list_savings_goals(
        session,
        page=page,
        page_size=page_size,
        status=goal_status,
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
    "/savings-goals",
    response_model=DataEnvelope[SavingsGoalResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_savings_goal(
    create_data: SavingsGoalCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[SavingsGoalResponse]:
    return DataEnvelope(data=create_savings_goal(session, create_data))


@router.get("/savings-goals/{goal_id}", response_model=DataEnvelope[SavingsGoalResponse])
def read_savings_goal(
    goal_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[SavingsGoalResponse]:
    return DataEnvelope(data=get_savings_goal(session, goal_id))


@router.patch("/savings-goals/{goal_id}", response_model=DataEnvelope[SavingsGoalResponse])
def patch_savings_goal(
    goal_id: UUID,
    update_data: SavingsGoalUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[SavingsGoalResponse]:
    return DataEnvelope(data=update_savings_goal(session, goal_id, update_data))


@router.post(
    "/savings-goals/{goal_id}/contributions",
    response_model=DataEnvelope[SavingsGoalResponse],
)
def post_savings_goal_contribution(
    goal_id: UUID,
    request: SavingsGoalContributionRequest,
    session: SessionDependency,
) -> DataEnvelope[SavingsGoalResponse]:
    return DataEnvelope(data=contribute_to_savings_goal(session, goal_id, request))


@router.delete("/savings-goals/{goal_id}", response_model=DataEnvelope[DeletedResource])
def remove_savings_goal(
    goal_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_savings_goal(session, goal_id, revision))
