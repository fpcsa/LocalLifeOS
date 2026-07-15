from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    AutomationActionType,
    AutomationExecution,
    AutomationExecutionStatus,
    AutomationRule,
    AutomationTriggerType,
    DomainEntityType,
    LocalNotification,
    Note,
    NotificationKind,
    PlannedTransaction,
    PlannedTransactionStatus,
    TagEntityLink,
    Task,
    TaskStatus,
)
from app.models.common import utc_now
from app.repositories.automation import (
    AutomationExecutionRepository,
    AutomationRuleRepository,
    NotificationRepository,
)
from app.repositories.finance_engine import PlannedTransactionRepository
from app.repositories.notes import NoteRepository
from app.repositories.tasks import TaskRepository
from app.schemas.automation import (
    AutomationAction,
    AutomationActionPreview,
    AutomationCondition,
    AutomationExecutionResponse,
    AutomationOperator,
    AutomationPreviewRequest,
    AutomationPreviewResponse,
    AutomationRuleCreateRequest,
    AutomationRuleResponse,
    AutomationRuleUpdateRequest,
    AutomationTrigger,
    NotificationResponse,
)
from app.schemas.common import DeletedResource
from app.services.domain_links import require_active_entity
from app.services.events import emit_timeline_event
from app.services.finance_validation import validate_transaction_relationships
from app.services.workspace import get_current_workspace
from app.utils.automation_schedule import next_scheduled_run

TRIGGER_FIELDS: dict[AutomationTriggerType, frozenset[str]] = {
    AutomationTriggerType.TRANSACTION_CREATED: frozenset(
        {
            "account_id",
            "amount_minor",
            "category_id",
            "currency_code",
            "payee",
            "transaction_type",
        }
    ),
    AutomationTriggerType.SUBSCRIPTION_AMOUNT_CHANGED: frozenset(
        {
            "currency_code",
            "delta_minor",
            "delta_percent",
            "name",
            "new_amount_minor",
            "old_amount_minor",
        }
    ),
    AutomationTriggerType.EVENT_CREATED: frozenset(
        {"category", "location", "status", "timezone", "title"}
    ),
    AutomationTriggerType.EVENT_APPROACHING: frozenset(
        {"category", "location", "minutes_until", "status", "timezone", "title"}
    ),
    AutomationTriggerType.TASK_OVERDUE: frozenset(
        {"overdue_days", "priority", "project_id", "status", "title"}
    ),
    AutomationTriggerType.COMMITMENT_WARNING_CREATED: frozenset(
        {"commitment_title", "severity", "warning_code"}
    ),
    AutomationTriggerType.RECURRING_SCHEDULE: frozenset({"scheduled_at"}),
}


def validate_rule_definition(trigger: AutomationTrigger, action: AutomationAction) -> None:
    allowed_fields = TRIGGER_FIELDS[trigger.type]
    unknown = sorted({condition.field for condition in trigger.conditions} - allowed_fields)
    if unknown:
        raise DomainValidationError(
            "automation_condition_field",
            "One or more condition fields are not available for this trigger.",
            {"fields": unknown, "trigger": trigger.type.value},
        )
    for condition in trigger.conditions:
        if condition.operator == AutomationOperator.IN and not isinstance(condition.value, list):
            raise DomainValidationError(
                "automation_condition_value", "The in operator requires a list value."
            )
        if condition.operator != AutomationOperator.IN and isinstance(condition.value, list):
            raise DomainValidationError(
                "automation_condition_value", "Only the in operator accepts a list value."
            )
    if action.type == AutomationActionType.ADD_TAG and action.tag_id is None:
        raise DomainValidationError("automation_action", "Add tag requires a tag.")


def _rule_response(session: Session, item: AutomationRule) -> AutomationRuleResponse:
    return AutomationRuleResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        name=item.name,
        description=item.description,
        enabled=item.enabled,
        trigger=AutomationTrigger.model_validate(item.trigger),
        action=AutomationAction.model_validate(item.action),
        last_run_at=item.last_run_at,
        next_run_at=item.next_run_at,
        execution_count=AutomationExecutionRepository(session).count_rule(item.id),
        revision=item.revision,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def list_automation_rules(session: Session) -> list[AutomationRuleResponse]:
    workspace = get_current_workspace(session)
    return [
        _rule_response(session, item)
        for item in AutomationRuleRepository(session).list_active(workspace.id)
    ]


def get_automation_rule(session: Session, rule_id: UUID) -> AutomationRuleResponse:
    workspace = get_current_workspace(session)
    item = AutomationRuleRepository(session).get_active(workspace.id, rule_id)
    if item is None:
        raise DomainNotFoundError("automation rule", rule_id)
    return _rule_response(session, item)


def create_automation_rule(
    session: Session, request: AutomationRuleCreateRequest
) -> AutomationRuleResponse:
    validate_rule_definition(request.trigger, request.action)
    workspace = get_current_workspace(session)
    now = utc_now()
    next_run_at = next_scheduled_run(request.trigger, now=now)
    with transaction(session):
        item = AutomationRuleRepository(session).add(
            AutomationRule(
                workspace_id=workspace.id,
                name=request.name,
                description=request.description,
                enabled=request.enabled,
                trigger=request.trigger.model_dump(mode="json"),
                action=request.action.model_dump(mode="json"),
                next_run_at=next_run_at,
            )
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.AUTOMATION_RULE,
            entity_id=item.id,
            action="automation_rule_created",
            title=f"Automation rule created: {item.name}",
        )
    _request_scheduler_sync()
    return _rule_response(session, item)


def update_automation_rule(
    session: Session, rule_id: UUID, request: AutomationRuleUpdateRequest
) -> AutomationRuleResponse:
    workspace = get_current_workspace(session)
    repository = AutomationRuleRepository(session)
    current = repository.get_active(workspace.id, rule_id)
    if current is None:
        raise DomainNotFoundError("automation rule", rule_id)
    trigger = request.trigger or AutomationTrigger.model_validate(current.trigger)
    action = request.action or AutomationAction.model_validate(current.action)
    validate_rule_definition(trigger, action)
    values = request.model_dump(exclude={"revision", "trigger", "action"}, exclude_unset=True)
    if request.trigger is not None:
        values["trigger"] = request.trigger.model_dump(mode="json")
    if request.action is not None:
        values["action"] = request.action.model_dump(mode="json")
    enabled = values.get("enabled", current.enabled)
    values["next_run_at"] = next_scheduled_run(trigger, now=utc_now()) if enabled else None
    with transaction(session):
        item = repository.update(workspace.id, rule_id, request.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.AUTOMATION_RULE,
            entity_id=item.id,
            action="automation_rule_updated",
            title=f"Automation rule updated: {item.name}",
            payload={"fields": sorted(request.model_fields_set - {"revision"})},
        )
    _request_scheduler_sync()
    return _rule_response(session, item)


def delete_automation_rule(session: Session, rule_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    with transaction(session):
        item = AutomationRuleRepository(session).soft_delete(workspace.id, rule_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.AUTOMATION_RULE,
            entity_id=item.id,
            action="automation_rule_deleted",
            title=f"Automation rule deleted: {item.name}",
        )
    _request_scheduler_sync()
    return DeletedResource(id=rule_id)


def _request_scheduler_sync() -> None:
    from app.services.automation_scheduler import request_scheduler_sync

    request_scheduler_sync()


def _compare(actual: Any, condition: AutomationCondition) -> bool:
    expected = condition.value
    operator = condition.operator
    if operator == AutomationOperator.EQUALS:
        return bool(actual == expected)
    if operator == AutomationOperator.NOT_EQUALS:
        return bool(actual != expected)
    if operator == AutomationOperator.CONTAINS:
        return str(expected).casefold() in str(actual or "").casefold()
    if operator == AutomationOperator.IN:
        return actual in expected if isinstance(expected, list) else False
    try:
        left = float(actual)
        right = float(expected)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if operator == AutomationOperator.GREATER_THAN:
        return left > right
    if operator == AutomationOperator.GREATER_THAN_OR_EQUAL:
        return left >= right
    if operator == AutomationOperator.LESS_THAN:
        return left < right
    if operator == AutomationOperator.LESS_THAN_OR_EQUAL:
        return left <= right
    return False


def match_trigger(trigger: AutomationTrigger, context: dict[str, Any]) -> tuple[bool, list[str]]:
    results: list[str] = []
    matched = True
    for condition in trigger.conditions:
        result = _compare(context.get(condition.field), condition)
        matched = matched and result
        results.append(
            f"{condition.field} {condition.operator.value} {condition.value!r}: "
            f"{'matched' if result else 'did not match'}"
        )
    return matched, results


def _action_preview(action: AutomationAction, context: dict[str, Any]) -> AutomationActionPreview:
    descriptions = {
        AutomationActionType.CREATE_TASK: f"Create task “{action.title}”",
        AutomationActionType.CREATE_NOTE: f"Create note “{action.title}”",
        AutomationActionType.CREATE_PLANNED_TRANSACTION: (
            f"Create a {action.amount_minor} {action.currency_code} planned transaction"
        ),
        AutomationActionType.ADD_TAG: f"Add tag {action.tag_id} to the triggering record",
        AutomationActionType.CREATE_NOTIFICATION: f"Create notification “{action.title}”",
        AutomationActionType.REQUEST_LOCAL_BACKUP_REMINDER: (
            f"Create local backup reminder “{action.title}”"
        ),
    }
    payload = action.model_dump(mode="json", exclude_none=True)
    if "entity_id" in context:
        payload["trigger_entity_id"] = context["entity_id"]
    return AutomationActionPreview(
        type=action.type,
        description=descriptions[action.type],
        payload=payload,
    )


def preview_automation_rule(
    session: Session, rule_id: UUID, request: AutomationPreviewRequest
) -> AutomationPreviewResponse:
    rule = get_automation_rule(session, rule_id)
    matched, condition_results = match_trigger(rule.trigger, request.context)
    return AutomationPreviewResponse(
        rule_id=rule.id,
        matched=matched,
        condition_results=condition_results,
        action=_action_preview(rule.action, request.context) if matched else None,
        writes_performed=False,
    )


def _execute_action(
    session: Session,
    workspace_id: UUID,
    rule: AutomationRule,
    action: AutomationAction,
    context: dict[str, Any],
) -> dict[str, Any]:
    now = utc_now()
    if action.type == AutomationActionType.CREATE_TASK:
        task = TaskRepository(session).add(
            Task(
                workspace_id=workspace_id,
                title=str(action.title),
                description_markdown=action.body,
                status=TaskStatus.TODO,
                priority=action.priority,
                due_at=(now + timedelta(days=action.due_in_days))
                if action.due_in_days is not None
                else None,
            )
        )
        result = {"entity_type": DomainEntityType.TASK.value, "entity_id": str(task.id)}
    elif action.type == AutomationActionType.CREATE_NOTE:
        note = NoteRepository(session).add(
            Note(
                workspace_id=workspace_id,
                title=str(action.title),
                markdown=action.body or "",
            )
        )
        result = {"entity_type": DomainEntityType.NOTE.value, "entity_id": str(note.id)}
    elif action.type == AutomationActionType.CREATE_PLANNED_TRANSACTION:
        if (
            action.account_id is None
            or action.transaction_type is None
            or action.amount_minor is None
            or action.currency_code is None
        ):
            raise DomainValidationError(
                "automation_action", "Planned transaction details are missing."
            )
        validate_transaction_relationships(
            session,
            workspace_id,
            account_id=action.account_id,
            transfer_account_id=None,
            category_id=action.category_id,
            transaction_type=action.transaction_type,
            currency_code=action.currency_code,
        )
        item = PlannedTransactionRepository(session).add(
            PlannedTransaction(
                workspace_id=workspace_id,
                account_id=action.account_id,
                category_id=action.category_id,
                transaction_type=action.transaction_type,
                amount_minor=action.amount_minor,
                currency_code=action.currency_code,
                planned_for=now + timedelta(days=action.days_from_trigger),
                payee=action.title,
                note=action.body,
                status=PlannedTransactionStatus.PLANNED,
                is_committed=False,
            )
        )
        result = {
            "entity_type": DomainEntityType.PLANNED_TRANSACTION.value,
            "entity_id": str(item.id),
        }
    elif action.type == AutomationActionType.ADD_TAG:
        if action.tag_id is None:
            raise DomainValidationError("automation_action", "Tag is missing.")
        if action.target_entity_type is not None and action.target_entity_id is not None:
            entity_type = action.target_entity_type
            entity_id = action.target_entity_id
        else:
            try:
                entity_type = DomainEntityType(str(context["entity_type"]))
                entity_id = UUID(str(context["entity_id"]))
            except (KeyError, ValueError) as exc:
                raise DomainValidationError(
                    "automation_target", "The trigger does not identify a taggable record."
                ) from exc
        if entity_type == DomainEntityType.PLANNED_TRANSACTION:
            raise DomainValidationError(
                "automation_target", "Planned transactions cannot currently receive generic tags."
            )
        require_active_entity(session, workspace_id, DomainEntityType.TAG, action.tag_id)
        require_active_entity(session, workspace_id, entity_type, entity_id)
        existing = session.exec(
            select(TagEntityLink).where(
                col(TagEntityLink.workspace_id) == workspace_id,
                col(TagEntityLink.tag_id) == action.tag_id,
                col(TagEntityLink.entity_type) == entity_type,
                col(TagEntityLink.entity_id) == entity_id,
            )
        ).first()
        if existing is None:
            session.add(
                TagEntityLink(
                    workspace_id=workspace_id,
                    tag_id=action.tag_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )
        result = {"entity_type": entity_type.value, "entity_id": str(entity_id)}
    else:
        kind = (
            NotificationKind.BACKUP_REMINDER
            if action.type == AutomationActionType.REQUEST_LOCAL_BACKUP_REMINDER
            else NotificationKind.INFORMATION
        )
        notification = NotificationRepository(session).add(
            LocalNotification(
                workspace_id=workspace_id,
                source_rule_id=rule.id,
                kind=kind,
                title=str(action.title),
                message=action.body,
            )
        )
        result = {"entity_type": "notification", "entity_id": str(notification.id)}
    emit_timeline_event(
        session,
        workspace_id=workspace_id,
        entity_type=DomainEntityType.AUTOMATION_RULE,
        entity_id=rule.id,
        action="automation_action_executed",
        title=f"Automation ran: {rule.name}",
        payload={"action_type": action.type.value, **result},
    )
    return result


def _execution_response(item: AutomationExecution) -> AutomationExecutionResponse:
    return AutomationExecutionResponse.model_validate(item)


def execute_automation_rule(
    session: Session,
    rule: AutomationRule,
    *,
    context: dict[str, Any],
    source_key: str,
) -> AutomationExecutionResponse:
    trigger = AutomationTrigger.model_validate(rule.trigger)
    action = AutomationAction.model_validate(rule.action)
    idempotency_key = hashlib.sha256(
        f"{rule.id}:{trigger.type.value}:{source_key}".encode()
    ).hexdigest()
    execution_repository = AutomationExecutionRepository(session)
    existing = execution_repository.find_key(rule.id, idempotency_key)
    if existing is not None:
        return _execution_response(existing)
    matched, condition_results = match_trigger(trigger, context)
    status = AutomationExecutionStatus.SKIPPED
    action_result: dict[str, Any] = {"condition_results": condition_results}
    try:
        with transaction(session):
            if matched:
                action_result.update(
                    _execute_action(session, rule.workspace_id, rule, action, context)
                )
                status = AutomationExecutionStatus.SUCCEEDED
            execution = execution_repository.add(
                AutomationExecution(
                    workspace_id=rule.workspace_id,
                    rule_id=rule.id,
                    trigger_type=trigger.type,
                    action_type=action.type,
                    status=status,
                    source_key=source_key,
                    idempotency_key=idempotency_key,
                    trigger_context=json.loads(json.dumps(context, default=str)),
                    action_result=action_result,
                    completed_at=utc_now(),
                )
            )
            rule.last_run_at = utc_now()
            session.add(rule)
        return _execution_response(execution)
    except IntegrityError:
        session.rollback()
        existing = execution_repository.find_key(rule.id, idempotency_key)
        if existing is None:
            raise
        return _execution_response(existing)
    except Exception as exc:
        session.rollback()
        with transaction(session):
            failed = execution_repository.add(
                AutomationExecution(
                    workspace_id=rule.workspace_id,
                    rule_id=rule.id,
                    trigger_type=trigger.type,
                    action_type=action.type,
                    status=AutomationExecutionStatus.FAILED,
                    source_key=source_key,
                    idempotency_key=idempotency_key,
                    trigger_context=json.loads(json.dumps(context, default=str)),
                    action_result={"condition_results": condition_results},
                    error=str(exc),
                    completed_at=utc_now(),
                )
            )
        return _execution_response(failed)


def dispatch_automation_event(
    session: Session,
    trigger_type: AutomationTriggerType,
    *,
    context: dict[str, Any],
    source_key: str,
) -> list[AutomationExecutionResponse]:
    workspace = get_current_workspace(session)
    rules = AutomationRuleRepository(session).list_enabled_trigger(workspace.id, trigger_type)
    return [
        execute_automation_rule(session, rule, context=context, source_key=source_key)
        for rule in rules
    ]


def list_automation_executions(
    session: Session,
    *,
    page: int,
    page_size: int,
    rule_id: UUID | None,
    status: AutomationExecutionStatus | None,
) -> tuple[list[AutomationExecutionResponse], int]:
    workspace = get_current_workspace(session)
    result = AutomationExecutionRepository(session).list_page(
        workspace.id, page=page, page_size=page_size, rule_id=rule_id, status=status
    )
    return [_execution_response(item) for item in result.items], result.total


def list_notifications(session: Session) -> list[NotificationResponse]:
    workspace = get_current_workspace(session)
    return [
        NotificationResponse.model_validate(item)
        for item in NotificationRepository(session).list_unread(workspace.id)
    ]
