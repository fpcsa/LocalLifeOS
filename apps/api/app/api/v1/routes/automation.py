from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import AutomationExecutionStatus
from app.schemas.automation import (
    AutomationExecutionResponse,
    AutomationPreviewRequest,
    AutomationPreviewResponse,
    AutomationRuleCreateRequest,
    AutomationRuleResponse,
    AutomationRuleUpdateRequest,
    NotificationResponse,
    SchedulerStatusResponse,
)
from app.schemas.common import DataEnvelope, DeletedResource, ListEnvelope, PaginationMeta
from app.services.automation import (
    create_automation_rule,
    delete_automation_rule,
    get_automation_rule,
    list_automation_executions,
    list_automation_rules,
    list_notifications,
    preview_automation_rule,
    update_automation_rule,
)
from app.services.automation_scheduler import scheduler_status

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/rules", response_model=DataEnvelope[list[AutomationRuleResponse]])
def list_rules(session: SessionDependency) -> DataEnvelope[list[AutomationRuleResponse]]:
    return DataEnvelope(data=list_automation_rules(session))


@router.post(
    "/rules",
    response_model=DataEnvelope[AutomationRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    request: AutomationRuleCreateRequest, session: SessionDependency
) -> DataEnvelope[AutomationRuleResponse]:
    return DataEnvelope(data=create_automation_rule(session, request))


@router.get("/rules/{rule_id}", response_model=DataEnvelope[AutomationRuleResponse])
def get_rule(rule_id: UUID, session: SessionDependency) -> DataEnvelope[AutomationRuleResponse]:
    return DataEnvelope(data=get_automation_rule(session, rule_id))


@router.patch("/rules/{rule_id}", response_model=DataEnvelope[AutomationRuleResponse])
def update_rule(
    rule_id: UUID,
    request: AutomationRuleUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[AutomationRuleResponse]:
    return DataEnvelope(data=update_automation_rule(session, rule_id, request))


@router.delete("/rules/{rule_id}", response_model=DataEnvelope[DeletedResource])
def delete_rule(
    rule_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_automation_rule(session, rule_id, revision))


@router.post("/rules/{rule_id}/preview", response_model=DataEnvelope[AutomationPreviewResponse])
def preview_rule(
    rule_id: UUID,
    request: AutomationPreviewRequest,
    session: SessionDependency,
) -> DataEnvelope[AutomationPreviewResponse]:
    return DataEnvelope(data=preview_automation_rule(session, rule_id, request))


@router.post("/rules/{rule_id}/test", response_model=DataEnvelope[AutomationPreviewResponse])
def test_rule(
    rule_id: UUID,
    request: AutomationPreviewRequest,
    session: SessionDependency,
) -> DataEnvelope[AutomationPreviewResponse]:
    """Evaluate a rule without running the configured action or writing data."""
    return DataEnvelope(data=preview_automation_rule(session, rule_id, request))


@router.get("/executions", response_model=ListEnvelope[AutomationExecutionResponse])
def list_executions(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    rule_id: UUID | None = None,
    execution_status: Annotated[AutomationExecutionStatus | None, Query(alias="status")] = None,
) -> ListEnvelope[AutomationExecutionResponse]:
    items, total = list_automation_executions(
        session,
        page=page,
        page_size=page_size,
        rule_id=rule_id,
        status=execution_status,
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


@router.get("/notifications", response_model=DataEnvelope[list[NotificationResponse]])
def notifications(session: SessionDependency) -> DataEnvelope[list[NotificationResponse]]:
    return DataEnvelope(data=list_notifications(session))


@router.get("/scheduler", response_model=DataEnvelope[SchedulerStatusResponse])
def get_scheduler_status() -> DataEnvelope[SchedulerStatusResponse]:
    return DataEnvelope(data=scheduler_status())
