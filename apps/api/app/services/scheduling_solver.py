from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from time import perf_counter
from uuid import UUID

from ortools.sat.python import cp_model

from app.models import PreferredTimeOfDay, TaskDependencyType, TaskPriority, TaskStatus
from app.schemas.scheduling import (
    CapacityReport,
    SchedulingPreviewRequest,
    SchedulingSolverStatus,
    UnscheduledReasonCode,
)
from app.services.scheduling_intervals import (
    ceil_minutes,
    clip_interval,
    floor_minutes,
    local_day_intervals,
    local_wall_to_utc,
)
from app.services.scheduling_types import (
    RawSolverResult,
    SchedulingEvidence,
    SolverPlacement,
    SolverTask,
    SolverWindow,
    TaskSchedulingInput,
    TimeInterval,
)

PRIORITY_SCORE = {
    TaskPriority.LOW: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.HIGH: 4,
    TaskPriority.URGENT: 8,
}
PREFERENCE_BANDS = {
    PreferredTimeOfDay.MORNING: (time(hour=8), time(hour=12)),
    PreferredTimeOfDay.AFTERNOON: (time(hour=12), time(hour=17)),
    PreferredTimeOfDay.EVENING: (time(hour=17), time(hour=21)),
}


@dataclass
class _TaskVariables:
    task: SolverTask
    present: cp_model.IntVar
    starts: cp_model.IntVar
    ends: cp_model.IntVar
    interval: cp_model.IntervalVar
    selectors: list[cp_model.IntVar]
    preference_met: list[cp_model.IntVar]
    active_start: cp_model.IntVar


def _effective_deadline(
    evidence: SchedulingEvidence,
    task_due: datetime | None,
    request_end: datetime,
) -> datetime:
    candidates = [request_end]
    if task_due is not None:
        candidates.append(task_due)
    if evidence.commitment is not None and evidence.commitment.ends_at is not None:
        candidates.append(evidence.commitment.ends_at)
    return min(candidates)


def _task_windows(
    source: TaskSchedulingInput,
    free_windows: list[TimeInterval],
    evidence: SchedulingEvidence,
    request: SchedulingPreviewRequest,
) -> tuple[SolverWindow, ...]:
    duration = source.duration_minutes
    if duration is None or duration <= 0:
        return ()
    origin = request.planning_start_at.astimezone(UTC)
    day_bounds = local_day_intervals(
        request.planning_start_at,
        request.planning_end_at,
        evidence.timezone_name,
    )
    windows: list[SolverWindow] = []
    for free in free_windows:
        task_free = clip_interval(free, source.earliest_start_at, source.deadline_at)
        if task_free is None or task_free.duration_minutes < duration:
            continue
        hard_start = ceil_minutes(task_free.starts_at, origin)
        hard_end = floor_minutes(task_free.ends_at, origin)
        for local_date, day_interval in day_bounds:
            lower = max(hard_start, ceil_minutes(day_interval.starts_at, origin))
            local_day_last_start = ceil_minutes(day_interval.ends_at, origin) - 1
            latest = min(hard_end - duration, local_day_last_start)
            if latest < lower:
                continue
            preference_start: int | None = None
            preference_end: int | None = None
            band = PREFERENCE_BANDS.get(source.preferred_time_of_day)
            if band is not None:
                band_start = ceil_minutes(
                    local_wall_to_utc(local_date, band[0], evidence.timezone_name),
                    origin,
                )
                band_end = floor_minutes(
                    local_wall_to_utc(local_date, band[1], evidence.timezone_name),
                    origin,
                )
                preference_start = max(lower, band_start)
                preference_end = min(hard_end, band_end)
                if preference_end - preference_start < duration:
                    preference_start = preference_end = None
            windows.append(
                SolverWindow(
                    starts_minute=lower,
                    latest_start_minute=latest,
                    ends_minute=hard_end,
                    local_date_ordinal=local_date.toordinal(),
                    preference_starts_minute=preference_start,
                    preference_ends_minute=preference_end,
                )
            )
    return tuple(
        sorted(
            windows,
            key=lambda item: (
                item.starts_minute,
                item.latest_start_minute,
                item.ends_minute,
                item.local_date_ordinal,
            ),
        )
    )


def prepare_solver_tasks(
    evidence: SchedulingEvidence,
    request: SchedulingPreviewRequest,
    free_windows: list[TimeInterval],
) -> list[SolverTask]:
    selected_ids = {task.id for task in evidence.selected_tasks}
    result: list[SolverTask] = []
    for task in evidence.selected_tasks:
        reasons: list[str] = []
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            reasons.append(UnscheduledReasonCode.INACTIVE_TASK.value)
        if task.scheduled_start_at is not None or task.scheduled_end_at is not None:
            reasons.append(UnscheduledReasonCode.ALREADY_SCHEDULED.value)
        if task.estimated_duration_minutes is None or task.estimated_duration_minutes <= 0:
            reasons.append(UnscheduledReasonCode.DURATION_MISSING.value)
        earliest = max(
            request.planning_start_at,
            task.earliest_start_at or request.planning_start_at,
        ).astimezone(UTC)
        deadline = _effective_deadline(
            evidence,
            task.due_at,
            request.planning_end_at,
        ).astimezone(UTC)
        if earliest >= request.planning_end_at:
            reasons.append(UnscheduledReasonCode.OUTSIDE_HORIZON.value)
        if deadline <= earliest:
            reasons.append(UnscheduledReasonCode.DEADLINE_BEFORE_EARLIEST_START.value)
        for dependency in evidence.dependencies.get(task.id, []):
            target = evidence.dependency_targets.get(dependency.id)
            if target is None:
                reasons.append(UnscheduledReasonCode.DEPENDENCY_UNAVAILABLE.value)
                continue
            if target.id in selected_ids:
                continue
            if dependency.dependency_type == TaskDependencyType.FINISH_TO_START:
                available = (
                    target.status == TaskStatus.COMPLETED or target.scheduled_end_at is not None
                )
            else:
                available = (
                    target.status != TaskStatus.TODO or target.scheduled_start_at is not None
                )
            if not available:
                reasons.append(UnscheduledReasonCode.DEPENDENCY_UNAVAILABLE.value)
        source = TaskSchedulingInput(
            task=task,
            duration_minutes=task.estimated_duration_minutes,
            earliest_start_at=earliest,
            deadline_at=deadline,
            preferred_time_of_day=task.preferred_time_of_day,
            dependencies=tuple(evidence.dependencies.get(task.id, [])),
        )
        windows = () if reasons else _task_windows(source, free_windows, evidence, request)
        result.append(
            SolverTask(
                source=source,
                windows=windows,
                precluded_reason_codes=tuple(dict.fromkeys(reasons)),
            )
        )
    return result


def _status_name(status: cp_model.CpSolverStatus) -> SchedulingSolverStatus:
    return {
        cp_model.OPTIMAL: SchedulingSolverStatus.OPTIMAL,
        cp_model.FEASIBLE: SchedulingSolverStatus.FEASIBLE,
        cp_model.INFEASIBLE: SchedulingSolverStatus.INFEASIBLE,
        cp_model.MODEL_INVALID: SchedulingSolverStatus.MODEL_INVALID,
        cp_model.UNKNOWN: SchedulingSolverStatus.UNKNOWN,
    }[status]


def solve_schedule(
    evidence: SchedulingEvidence,
    request: SchedulingPreviewRequest,
    tasks: list[SolverTask],
    capacity: CapacityReport,
) -> RawSolverResult:
    solvable = [task for task in tasks if task.windows and not task.precluded_reason_codes]
    if not solvable:
        return RawSolverResult(
            status=SchedulingSolverStatus.NOT_RUN.value,
            optimality_proven=False,
            solve_duration_ms=0,
        )

    origin = request.planning_start_at.astimezone(UTC)
    horizon_minutes = max(1, floor_minutes(request.planning_end_at.astimezone(UTC), origin))
    model = cp_model.CpModel()
    variables: dict[UUID, _TaskVariables] = {}
    intervals: list[cp_model.IntervalVar] = []
    objective_terms: list[cp_model.LinearExpr] = []
    weights = request.policy.objective_weights

    for solver_task in solvable:
        task = solver_task.source.task
        duration = solver_task.source.duration_minutes
        if duration is None:
            continue
        present = model.new_bool_var(f"present_{task.id}")
        starts = model.new_int_var(0, horizon_minutes, f"start_{task.id}")
        ends = model.new_int_var(0, horizon_minutes, f"end_{task.id}")
        model.add(ends == starts + duration)
        interval = model.new_optional_interval_var(
            starts,
            duration,
            ends,
            present,
            f"interval_{task.id}",
        )
        selectors: list[cp_model.IntVar] = []
        preference_met: list[cp_model.IntVar] = []
        for index, window in enumerate(solver_task.windows):
            selector = model.new_bool_var(f"window_{task.id}_{index}")
            selectors.append(selector)
            model.add(starts >= window.starts_minute).only_enforce_if(selector)
            model.add(starts <= window.latest_start_minute).only_enforce_if(selector)
            model.add(ends <= window.ends_minute).only_enforce_if(selector)
            leftover = max(0, window.duration_minutes - duration)
            objective_terms.append(-weights.fragmentation * leftover * selector)
            if (
                window.preference_starts_minute is not None
                and window.preference_ends_minute is not None
            ):
                preference = model.new_bool_var(f"preference_{task.id}_{index}")
                preference_met.append(preference)
                model.add(preference <= selector)
                model.add(starts >= window.preference_starts_minute).only_enforce_if(preference)
                model.add(ends <= window.preference_ends_minute).only_enforce_if(preference)
                objective_terms.append(weights.preferred_time * preference)
        model.add(sum(selectors) == present)
        active_start = model.new_int_var(0, horizon_minutes, f"active_start_{task.id}")
        model.add(active_start == starts).only_enforce_if(present)
        model.add(active_start == 0).only_enforce_if(present.negated())
        objective_terms.extend(
            [
                weights.scheduled_task * present,
                weights.priority * PRIORITY_SCORE[task.priority] * present,
                -weights.earlier_start * active_start,
            ]
        )
        variables[task.id] = _TaskVariables(
            task=solver_task,
            present=present,
            starts=starts,
            ends=ends,
            interval=interval,
            selectors=selectors,
            preference_met=preference_met,
            active_start=active_start,
        )
        intervals.append(interval)

    model.add_no_overlap(intervals)

    for solver_task in solvable:
        dependent = variables.get(solver_task.source.task.id)
        if dependent is None:
            continue
        for dependency in solver_task.source.dependencies:
            target = evidence.dependency_targets.get(dependency.id)
            if target is None:
                model.add(dependent.present == 0)
                continue
            prerequisite = variables.get(target.id)
            if prerequisite is not None:
                model.add(dependent.present <= prerequisite.present)
                if dependency.dependency_type == TaskDependencyType.FINISH_TO_START:
                    model.add(dependent.starts >= prerequisite.ends).only_enforce_if(
                        dependent.present
                    )
                else:
                    model.add(dependent.starts >= prerequisite.starts).only_enforce_if(
                        dependent.present
                    )
            elif dependency.dependency_type == TaskDependencyType.FINISH_TO_START:
                if target.status != TaskStatus.COMPLETED and target.scheduled_end_at is not None:
                    model.add(
                        dependent.starts
                        >= ceil_minutes(target.scheduled_end_at.astimezone(UTC), origin)
                    ).only_enforce_if(dependent.present)
                elif target.status != TaskStatus.COMPLETED:
                    model.add(dependent.present == 0)
            elif target.status == TaskStatus.TODO:
                if target.scheduled_start_at is not None:
                    model.add(
                        dependent.starts
                        >= ceil_minutes(target.scheduled_start_at.astimezone(UTC), origin)
                    ).only_enforce_if(dependent.present)
                else:
                    model.add(dependent.present == 0)

    capacity_by_ordinal = {
        day.local_date.toordinal(): day.remaining_capacity_minutes for day in capacity.days
    }
    for ordinal, available in capacity_by_ordinal.items():
        workload_terms: list[cp_model.LinearExpr] = []
        for task_vars in variables.values():
            duration = task_vars.task.source.duration_minutes
            if duration is None:
                continue
            for selector, window in zip(
                task_vars.selectors,
                task_vars.task.windows,
                strict=True,
            ):
                if window.local_date_ordinal == ordinal:
                    workload_terms.append(duration * selector)
        if workload_terms:
            model.add(sum(workload_terms) <= available)

    model.maximize(sum(objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = request.solver_time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    started = perf_counter()
    status = solver.solve(model)
    duration_ms = int((perf_counter() - started) * 1_000)
    mapped_status = _status_name(status)
    result = RawSolverResult(
        status=mapped_status.value,
        optimality_proven=status == cp_model.OPTIMAL,
        solve_duration_ms=duration_ms,
        objective_value=solver.objective_value
        if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
        else None,
        best_bound=solver.best_objective_bound
        if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
        else None,
    )
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return result
    for task_id, task_vars in variables.items():
        if not solver.boolean_value(task_vars.present):
            continue
        selected_index = next(
            index
            for index, selector in enumerate(task_vars.selectors)
            if solver.boolean_value(selector)
        )
        starts_minute = solver.value(task_vars.starts)
        ends_minute = solver.value(task_vars.ends)
        selected_window = task_vars.task.windows[selected_index]
        preference_satisfied = (
            task_vars.task.source.preferred_time_of_day == PreferredTimeOfDay.ANY
            or (
                selected_window.preference_starts_minute is not None
                and selected_window.preference_ends_minute is not None
                and starts_minute >= selected_window.preference_starts_minute
                and ends_minute <= selected_window.preference_ends_minute
            )
        )
        result.placements.append(
            SolverPlacement(
                task_id=task_id,
                starts_minute=starts_minute,
                ends_minute=ends_minute,
                selected_window=selected_window,
                preference_satisfied=preference_satisfied,
            )
        )
        result.selected_task_ids.add(task_id)
    result.placements.sort(key=lambda item: (item.starts_minute, str(item.task_id)))
    return result
