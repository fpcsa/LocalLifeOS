from __future__ import annotations

from datetime import UTC, timedelta
from uuid import UUID, uuid4

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    CommitmentEntityType,
    DomainEntityType,
    PreferredTimeOfDay,
    SchedulingPreview,
    Task,
    TaskStatus,
)
from app.models.common import utc_now
from app.repositories import CommitmentRepository, SchedulingPreviewRepository, TaskRepository
from app.schemas.scheduling import (
    CapacityReport,
    DeadlineRisk,
    DeadlineRiskLevel,
    SchedulingApplyRequest,
    SchedulingApplyResponse,
    SchedulingConflict,
    SchedulingConflictKind,
    SchedulingEntityReference,
    SchedulingExplanationResponse,
    SchedulingObjectiveBreakdown,
    SchedulingPreviewRequest,
    SchedulingPreviewResponse,
    SchedulingReason,
    SchedulingScopeInput,
    SchedulingSolverStatus,
    SuggestedTaskPlacement,
    UnscheduledReasonCode,
    UnscheduledTask,
)
from app.services.events import emit_timeline_event
from app.services.scheduling_capacity import (
    calculate_capacity,
    suggestion_minutes_by_local_date,
)
from app.services.scheduling_collectors import collect_scheduling_evidence
from app.services.scheduling_intervals import (
    build_availability_intervals,
    clip_interval,
    interval_minutes,
    subtract_intervals,
)
from app.services.scheduling_solver import PRIORITY_SCORE, prepare_solver_tasks, solve_schedule
from app.services.scheduling_types import (
    RawSolverResult,
    SchedulingEvidence,
    SolverPlacement,
    SolverTask,
    TimeInterval,
)
from app.services.workspace import get_current_workspace


def _active_required_minutes(evidence: SchedulingEvidence) -> int:
    return sum(
        task.estimated_duration_minutes or 0
        for task in evidence.selected_tasks
        if task.status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}
        and task.scheduled_start_at is None
    )


def _free_focus_windows(
    evidence: SchedulingEvidence,
    request: SchedulingScopeInput,
) -> tuple[list[TimeInterval], list[TimeInterval]]:
    availability = build_availability_intervals(
        request.planning_start_at,
        request.planning_end_at,
        evidence.timezone_name,
        request.policy,
    )
    busy = [TimeInterval(item.starts_at, item.ends_at) for item in evidence.all_busy]
    free = subtract_intervals(availability, busy)
    focus = [
        interval
        for interval in free
        if interval.duration_minutes >= request.policy.minimum_focus_block_minutes
    ]
    return availability, focus


def _absolute_placements(
    raw: RawSolverResult,
    tasks: list[SolverTask],
    request: SchedulingPreviewRequest,
) -> list[SuggestedTaskPlacement]:
    task_by_id = {item.source.task.id: item for item in tasks}
    origin = request.planning_start_at.astimezone(UTC)
    result: list[SuggestedTaskPlacement] = []
    for item in raw.placements:
        source = task_by_id[item.task_id].source
        task = source.task
        duration = source.duration_minutes
        if duration is None:
            continue
        result.append(
            SuggestedTaskPlacement(
                task_id=task.id,
                title=task.title,
                expected_revision=task.revision,
                starts_at=origin + timedelta(minutes=item.starts_minute),
                ends_at=origin + timedelta(minutes=item.ends_minute),
                duration_minutes=duration,
                priority=task.priority,
                deadline_at=source.deadline_at,
                preferred_time_of_day=source.preferred_time_of_day,
                preference_satisfied=item.preference_satisfied,
            )
        )
    return result


def _conflicts(
    evidence: SchedulingEvidence,
    placements: list[SuggestedTaskPlacement],
) -> list[SchedulingConflict]:
    result = [
        SchedulingConflict(
            kind=SchedulingConflictKind.CALENDAR_EVENT,
            hard=True,
            message="Calendar event and its buffers are a hard scheduling constraint.",
            starts_at=item.starts_at,
            ends_at=item.ends_at,
            entity=SchedulingEntityReference(
                entity_type="calendar_event",
                entity_id=item.entity_id,
            ),
        )
        for item in evidence.calendar_busy
    ]
    result.extend(
        SchedulingConflict(
            kind=SchedulingConflictKind.EXISTING_TASK,
            hard=True,
            message="An existing scheduled task is a hard scheduling constraint.",
            starts_at=item.starts_at,
            ends_at=item.ends_at,
            entity=SchedulingEntityReference(
                entity_type="task",
                entity_id=item.entity_id,
            ),
        )
        for item in evidence.task_busy
    )
    result.extend(
        SchedulingConflict(
            kind=SchedulingConflictKind.SOFT_PREFERENCE,
            hard=False,
            message=(
                "The task was scheduled outside its preferred time of day because the "
                "preference is soft."
            ),
            starts_at=item.starts_at,
            ends_at=item.ends_at,
            task_id=item.task_id,
            entity=SchedulingEntityReference(entity_type="task", entity_id=item.task_id),
        )
        for item in placements
        if item.preferred_time_of_day != PreferredTimeOfDay.ANY and not item.preference_satisfied
    )
    return result


def _reason(
    code: UnscheduledReasonCode,
    task: SolverTask,
    evidence: SchedulingEvidence,
    **details: object,
) -> SchedulingReason:
    messages = {
        UnscheduledReasonCode.ALREADY_SCHEDULED: "The task already has a manual schedule.",
        UnscheduledReasonCode.INACTIVE_TASK: "Completed or cancelled tasks are not rescheduled.",
        UnscheduledReasonCode.DURATION_MISSING: (
            "The task needs a positive estimated duration before it can be scheduled."
        ),
        UnscheduledReasonCode.OUTSIDE_HORIZON: (
            "The task's earliest start is outside the planning horizon."
        ),
        UnscheduledReasonCode.DEADLINE_BEFORE_EARLIEST_START: (
            "The effective deadline is not after the earliest start."
        ),
        UnscheduledReasonCode.DEPENDENCY_UNAVAILABLE: (
            "A required prerequisite is neither completed, scheduled, nor part of this preview."
        ),
        UnscheduledReasonCode.DEPENDENCY_ORDER_INFEASIBLE: (
            "Dependency order could not be satisfied by the selected placements."
        ),
        UnscheduledReasonCode.HARD_CALENDAR_CONFLICT: (
            "Calendar events or existing scheduled tasks remove otherwise eligible time."
        ),
        UnscheduledReasonCode.INSUFFICIENT_CONTIGUOUS_CAPACITY: (
            "No eligible focus-capable interval is long enough for this task."
        ),
        UnscheduledReasonCode.INSUFFICIENT_TOTAL_CAPACITY: (
            "The planning horizon has less remaining capacity than the required work."
        ),
        UnscheduledReasonCode.DAILY_WORKLOAD_LIMIT: (
            "No candidate day has enough workload headroom for this task."
        ),
        UnscheduledReasonCode.SOFT_OBJECTIVE_TRADEOFF: (
            "The bounded optimizer selected higher-value work within the available capacity."
        ),
        UnscheduledReasonCode.SOLVER_TIMEOUT: (
            "The solver time limit expired before a feasible placement was found for this task."
        ),
        UnscheduledReasonCode.MODEL_INVALID: "The solver rejected the scheduling model.",
    }
    references = [SchedulingEntityReference(entity_type="task", entity_id=task.source.task.id)]
    if code in {
        UnscheduledReasonCode.DEPENDENCY_UNAVAILABLE,
        UnscheduledReasonCode.DEPENDENCY_ORDER_INFEASIBLE,
    }:
        references.extend(
            SchedulingEntityReference(
                entity_type="task",
                entity_id=dependency.depends_on_task_id,
            )
            for dependency in task.source.dependencies
        )
    if code == UnscheduledReasonCode.HARD_CALENDAR_CONFLICT:
        references.extend(
            SchedulingEntityReference(entity_type=item.kind, entity_id=item.entity_id)
            for item in evidence.all_busy
            if item.starts_at < task.source.deadline_at
            and item.ends_at > task.source.earliest_start_at
        )
    unique = {(item.entity_type, item.entity_id): item for item in references}
    return SchedulingReason(
        code=code,
        message=messages[code],
        contributing_entities=list(unique.values()),
        details=dict(details),
    )


def _unscheduled_tasks(
    tasks: list[SolverTask],
    raw: RawSolverResult,
    evidence: SchedulingEvidence,
    availability: list[TimeInterval],
    focus_windows: list[TimeInterval],
    capacity: CapacityReport,
) -> list[UnscheduledTask]:
    selected = raw.selected_task_ids
    task_by_id = {item.source.task.id: item for item in tasks}
    required = sum(item.source.duration_minutes or 0 for item in tasks)
    result: list[UnscheduledTask] = []
    for task in tasks:
        source = task.source
        if source.task.id in selected:
            continue
        codes = [UnscheduledReasonCode(code) for code in task.precluded_reason_codes]
        if not codes and raw.status == SchedulingSolverStatus.UNKNOWN.value:
            codes.append(UnscheduledReasonCode.SOLVER_TIMEOUT)
        elif not codes and raw.status == SchedulingSolverStatus.MODEL_INVALID.value:
            codes.append(UnscheduledReasonCode.MODEL_INVALID)
        if not codes and not task.windows:
            eligible_for_task = [
                clipped
                for interval in availability
                if (
                    clipped := clip_interval(
                        interval,
                        source.earliest_start_at,
                        source.deadline_at,
                    )
                )
                is not None
            ]
            hard_busy_removed_eligible_time = any(
                busy.starts_at < eligible.ends_at and busy.ends_at > eligible.starts_at
                for busy in evidence.all_busy
                for eligible in eligible_for_task
            )
            if hard_busy_removed_eligible_time:
                codes.append(UnscheduledReasonCode.HARD_CALENDAR_CONFLICT)
            codes.append(UnscheduledReasonCode.INSUFFICIENT_CONTIGUOUS_CAPACITY)
        if not codes:
            dependency_unscheduled = any(
                dependency.depends_on_task_id in task_by_id
                and dependency.depends_on_task_id not in selected
                for dependency in source.dependencies
            )
            if dependency_unscheduled:
                codes.append(UnscheduledReasonCode.DEPENDENCY_ORDER_INFEASIBLE)
            duration = source.duration_minutes or 0
            candidate_days = {window.local_date_ordinal for window in task.windows}
            if candidate_days and all(
                day.remaining_capacity_minutes < duration
                for day in capacity.days
                if day.local_date.toordinal() in candidate_days
            ):
                codes.append(UnscheduledReasonCode.DAILY_WORKLOAD_LIMIT)
            if required > capacity.available_focus_minutes:
                codes.append(UnscheduledReasonCode.INSUFFICIENT_TOTAL_CAPACITY)
            if not codes:
                codes.append(UnscheduledReasonCode.SOFT_OBJECTIVE_TRADEOFF)
        unique_codes = list(dict.fromkeys(codes))
        result.append(
            UnscheduledTask(
                task_id=source.task.id,
                title=source.task.title,
                duration_minutes=source.duration_minutes,
                priority=source.task.priority,
                deadline_at=source.deadline_at,
                reasons=[
                    _reason(
                        code,
                        task,
                        evidence,
                        available_focus_minutes=interval_minutes(focus_windows),
                        required_minutes=source.duration_minutes,
                    )
                    for code in unique_codes
                ],
            )
        )
    return result


def _deadline_risks(
    tasks: list[SolverTask],
    placements: list[SuggestedTaskPlacement],
    request: SchedulingPreviewRequest,
    evidence: SchedulingEvidence,
) -> list[DeadlineRisk]:
    placement_by_id = {item.task_id: item for item in placements}
    result: list[DeadlineRisk] = []
    for solver_task in tasks:
        task = solver_task.source.task
        explicit_candidates = [item for item in [task.due_at] if item is not None]
        if evidence.commitment is not None and evidence.commitment.ends_at is not None:
            explicit_candidates.append(evidence.commitment.ends_at)
        explicit_deadline = min(explicit_candidates) if explicit_candidates else None
        placement = placement_by_id.get(task.id)
        if explicit_deadline is None:
            result.append(
                DeadlineRisk(
                    task_id=task.id,
                    deadline_at=None,
                    level=DeadlineRiskLevel.NOT_APPLICABLE,
                    scheduled_end_at=placement.ends_at if placement else None,
                    slack_minutes=None,
                    explanation="The task has no task or commitment deadline.",
                )
            )
            continue
        if placement is None:
            missed = explicit_deadline <= request.planning_start_at
            result.append(
                DeadlineRisk(
                    task_id=task.id,
                    deadline_at=explicit_deadline,
                    level=DeadlineRiskLevel.MISSED if missed else DeadlineRiskLevel.UNSCHEDULED,
                    scheduled_end_at=None,
                    slack_minutes=None,
                    explanation=(
                        "The deadline has passed without a placement."
                        if missed
                        else "The task remains unscheduled before its deadline."
                    ),
                )
            )
            continue
        slack = int((explicit_deadline - placement.ends_at).total_seconds() // 60)
        level = (
            DeadlineRiskLevel.MISSED
            if slack < 0
            else DeadlineRiskLevel.AT_RISK
            if slack < placement.duration_minutes
            else DeadlineRiskLevel.ON_TRACK
        )
        result.append(
            DeadlineRisk(
                task_id=task.id,
                deadline_at=explicit_deadline,
                level=level,
                scheduled_end_at=placement.ends_at,
                slack_minutes=slack,
                explanation=(
                    "Placement ends after the deadline."
                    if slack < 0
                    else "Placement leaves less slack than one task duration."
                    if level == DeadlineRiskLevel.AT_RISK
                    else "Placement ends with at least one task duration of slack."
                ),
            )
        )
    return result


def _objective_breakdown(
    raw: RawSolverResult,
    tasks: list[SolverTask],
    request: SchedulingPreviewRequest,
) -> SchedulingObjectiveBreakdown:
    task_by_id = {item.source.task.id: item for item in tasks}
    raw_by_id: dict[UUID, SolverPlacement] = {item.task_id: item for item in raw.placements}
    weights = request.policy.objective_weights
    scheduled_reward = len(raw.placements) * weights.scheduled_task
    priority_reward = sum(
        PRIORITY_SCORE[task_by_id[item.task_id].source.task.priority] * weights.priority
        for item in raw.placements
    )
    preference_reward = sum(
        weights.preferred_time
        for item in raw.placements
        if task_by_id[item.task_id].source.preferred_time_of_day != PreferredTimeOfDay.ANY
        and item.preference_satisfied
    )
    earlier_penalty = sum(item.starts_minute * weights.earlier_start for item in raw.placements)
    fragmentation_penalty = sum(
        max(
            0,
            item.selected_window.duration_minutes
            - (task_by_id[item.task_id].source.duration_minutes or 0),
        )
        * weights.fragmentation
        for item in raw_by_id.values()
    )
    total = (
        scheduled_reward
        + priority_reward
        + preference_reward
        - earlier_penalty
        - fragmentation_penalty
    )
    return SchedulingObjectiveBreakdown(
        scheduled_task_reward=scheduled_reward,
        priority_reward=priority_reward,
        preferred_time_reward=preference_reward,
        earlier_start_penalty=earlier_penalty,
        fragmentation_penalty=fragmentation_penalty,
        total=total,
        best_bound=raw.best_bound,
    )


def create_scheduling_preview(
    session: Session,
    request: SchedulingPreviewRequest,
) -> SchedulingPreviewResponse:
    evidence = collect_scheduling_evidence(
        session,
        request,
        task_ids=request.task_ids,
        commitment_id=request.commitment_id,
    )
    availability, focus_windows = _free_focus_windows(evidence, request)
    required_minutes = _active_required_minutes(evidence)
    initial_capacity = calculate_capacity(
        evidence,
        planning_start_at=request.planning_start_at,
        planning_end_at=request.planning_end_at,
        policy=request.policy,
        availability=availability,
        required_task_minutes=required_minutes,
        commitment_id=request.commitment_id,
    )
    solver_tasks = prepare_solver_tasks(evidence, request, focus_windows)
    raw = solve_schedule(evidence, request, solver_tasks, initial_capacity)
    placements = _absolute_placements(raw, solver_tasks, request)
    suggestions = suggestion_minutes_by_local_date(
        [(item.starts_at, item.duration_minutes) for item in placements],
        evidence.timezone_name,
    )
    capacity = calculate_capacity(
        evidence,
        planning_start_at=request.planning_start_at,
        planning_end_at=request.planning_end_at,
        policy=request.policy,
        availability=availability,
        required_task_minutes=required_minutes,
        suggested_by_local_date=suggestions,
        commitment_id=request.commitment_id,
    )
    unscheduled = _unscheduled_tasks(
        solver_tasks,
        raw,
        evidence,
        availability,
        focus_windows,
        initial_capacity,
    )
    created_at = utc_now()
    expires_at = created_at + timedelta(minutes=get_settings().scheduling_preview_ttl_minutes)
    preview_id = uuid4()
    solver_status = SchedulingSolverStatus(raw.status)
    assumptions = [
        "CP-SAT uses integer UTC minutes over a maximum 30-day horizon.",
        (
            "One deterministic solver worker and random seed zero are used with a "
            f"{request.solver_time_limit_seconds:g}-second wall-time limit."
        ),
        "Optimal and best-known feasible schedules are both returned; solver status is explicit.",
        (
            "Calendar events, their buffers, all-day occurrences, and existing tasks "
            "are hard constraints."
        ),
        "Task time-of-day preferences are soft and may be violated with an explanation.",
        "Finish-to-start and start-to-start dependency order is enforced for selected tasks.",
        "Every requested task appears either as a placement or with one or more reasons.",
        "Preview persistence does not modify task or calendar records.",
    ]
    response = SchedulingPreviewResponse(
        preview_id=preview_id,
        created_at=created_at,
        expires_at=expires_at,
        commitment_id=request.commitment_id,
        timezone=evidence.timezone_name,
        planning_start_at=request.planning_start_at,
        planning_end_at=request.planning_end_at,
        solver_status=solver_status,
        optimality_proven=raw.optimality_proven,
        solve_duration_ms=raw.solve_duration_ms,
        source_fingerprint=evidence.source_fingerprint,
        placements=placements,
        unscheduled_tasks=unscheduled,
        conflicts=_conflicts(evidence, placements),
        capacity=capacity,
        deadline_risks=_deadline_risks(solver_tasks, placements, request, evidence),
        assumptions=assumptions,
        objective=_objective_breakdown(raw, solver_tasks, request),
    )
    preview = SchedulingPreview(
        id=preview_id,
        created_at=created_at,
        updated_at=created_at,
        workspace_id=evidence.workspace_id,
        commitment_id=request.commitment_id,
        horizon_start_at=request.planning_start_at,
        horizon_end_at=request.planning_end_at,
        solver_status=solver_status.value,
        source_fingerprint=evidence.source_fingerprint,
        source_snapshot=evidence.source_snapshot,
        request_payload=request.model_dump(mode="json"),
        result_payload=response.model_dump(mode="json"),
        expires_at=expires_at,
    )
    with transaction(session):
        SchedulingPreviewRepository(session).add(preview)
    return response


def get_scheduling_explanations(
    session: Session,
    preview_id: UUID,
) -> SchedulingExplanationResponse:
    workspace = get_current_workspace(session)
    preview = SchedulingPreviewRepository(session).get(workspace.id, preview_id)
    if preview is None:
        raise DomainNotFoundError("scheduling_preview", preview_id)
    response = SchedulingPreviewResponse.model_validate(preview.result_payload)
    return SchedulingExplanationResponse(
        preview_id=response.preview_id,
        solver_status=response.solver_status,
        optimality_proven=response.optimality_proven,
        unscheduled_tasks=response.unscheduled_tasks,
        conflicts=response.conflicts,
        deadline_risks=response.deadline_risks,
        assumptions=response.assumptions,
        objective=response.objective,
    )


def apply_scheduling_preview(
    session: Session,
    request: SchedulingApplyRequest,
) -> SchedulingApplyResponse:
    workspace = get_current_workspace(session)
    repository = SchedulingPreviewRepository(session)
    preview = repository.get(workspace.id, request.preview_id)
    if preview is None:
        raise DomainNotFoundError("scheduling_preview", request.preview_id)
    if preview.applied_at is not None:
        raise DomainConflictError(
            "scheduling_preview_already_applied",
            "The scheduling preview has already been applied.",
        )
    now = utc_now()
    if preview.expires_at < now:
        raise DomainConflictError(
            "scheduling_preview_expired",
            "The scheduling preview has expired; create a new preview.",
        )
    stored_request = SchedulingPreviewRequest.model_validate(preview.request_payload)
    current_evidence = collect_scheduling_evidence(
        session,
        stored_request,
        task_ids=stored_request.task_ids,
        commitment_id=stored_request.commitment_id,
    )
    if current_evidence.source_fingerprint != preview.source_fingerprint:
        raise DomainConflictError(
            "stale_scheduling_preview",
            "Tasks, dependencies, calendar constraints, preferences, or commitment changed.",
            {
                "preview_fingerprint": preview.source_fingerprint,
                "current_fingerprint": current_evidence.source_fingerprint,
            },
        )
    stored_result = SchedulingPreviewResponse.model_validate(preview.result_payload)
    placement_by_id = {item.task_id: item for item in stored_result.placements}
    selected_ids = set(request.task_ids or placement_by_id)
    unknown = sorted(selected_ids - placement_by_id.keys(), key=str)
    if unknown:
        raise DomainValidationError(
            "invalid_schedule_selection",
            "Every selected task must have a placement in the preview.",
            {"task_ids": [str(item) for item in unknown]},
        )
    placements = [placement_by_id[item] for item in sorted(selected_ids, key=str)]
    if not placements:
        raise DomainConflictError(
            "scheduling_preview_has_no_placements",
            "The preview has no placements to apply.",
        )
    preview_revision = preview.revision
    applied_at = utc_now()
    task_repository = TaskRepository(session)
    with transaction(session):
        for placement in placements:
            task = task_repository.update(
                workspace.id,
                placement.task_id,
                placement.expected_revision,
                {
                    "scheduled_start_at": placement.starts_at,
                    "scheduled_end_at": placement.ends_at,
                },
            )
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TASK,
                entity_id=task.id,
                action="task_schedule_applied",
                title=f"Schedule applied: {task.title}",
                payload={
                    "preview_id": str(preview.id),
                    "scheduled_start_at": placement.starts_at.isoformat(),
                    "scheduled_end_at": placement.ends_at.isoformat(),
                },
            )
        repository.mark_applied(
            workspace.id,
            preview.id,
            preview_revision,
            applied_at,
        )
    return SchedulingApplyResponse(
        preview_id=preview.id,
        applied_at=applied_at,
        placements=placements,
    )


def _commitment_task_ids(session: Session, commitment_id: UUID) -> list[UUID]:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    commitment = repository.get_active(workspace.id, commitment_id)
    if commitment is None:
        raise DomainNotFoundError("commitment", commitment_id)
    return sorted(
        {
            link.entity_id
            for link in repository.links_for([commitment_id]).get(commitment_id, [])
            if link.entity_type == CommitmentEntityType.TASK
        },
        key=str,
    )


def preview_task_schedule(
    session: Session,
    task_id: UUID,
    request: SchedulingScopeInput,
) -> SchedulingPreviewResponse:
    payload = SchedulingPreviewRequest(
        **request.model_dump(),
        task_ids=[task_id],
    )
    return create_scheduling_preview(session, payload)


def preview_commitment_schedule(
    session: Session,
    commitment_id: UUID,
    request: SchedulingScopeInput,
) -> SchedulingPreviewResponse:
    task_ids = _commitment_task_ids(session, commitment_id)
    if not task_ids:
        raise DomainValidationError(
            "commitment_has_no_tasks",
            "The commitment has no linked tasks to schedule.",
        )
    payload = SchedulingPreviewRequest(
        **request.model_dump(),
        task_ids=task_ids,
        commitment_id=commitment_id,
    )
    return create_scheduling_preview(session, payload)


def get_capacity_report(
    session: Session,
    request: SchedulingScopeInput,
    *,
    commitment_id: UUID | None,
) -> CapacityReport:
    workspace = get_current_workspace(session)
    if commitment_id is not None:
        task_ids = _commitment_task_ids(session, commitment_id)
    else:
        task_ids = list(
            session.exec(
                select(Task.id)
                .where(
                    col(Task.workspace_id) == workspace.id,
                    col(Task.deleted_at).is_(None),
                    col(Task.status).in_((TaskStatus.TODO, TaskStatus.IN_PROGRESS)),
                    col(Task.scheduled_start_at).is_(None),
                )
                .order_by(col(Task.id))
                .limit(100)
            ).all()
        )
    evidence = collect_scheduling_evidence(
        session,
        request,
        task_ids=task_ids,
        commitment_id=commitment_id,
    )
    availability, _ = _free_focus_windows(evidence, request)
    return calculate_capacity(
        evidence,
        planning_start_at=request.planning_start_at,
        planning_end_at=request.planning_end_at,
        policy=request.policy,
        availability=availability,
        required_task_minutes=_active_required_minutes(evidence),
        commitment_id=commitment_id,
    )
