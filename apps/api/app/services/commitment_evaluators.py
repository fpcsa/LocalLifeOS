from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.models import (
    CalendarEventStatus,
    GoalStatus,
    PlannedTransactionStatus,
    TaskDependencyType,
    TaskStatus,
    TransactionType,
)
from app.models.common import utc_now
from app.schemas.commitments import (
    AssessmentComponent,
    AssessmentEntityReference,
    AssessmentLevel,
    BudgetImpact,
    CalendarConflictImpact,
    CommitmentImpactResponse,
    CommitmentWarning,
    CurrencyImpact,
    DeadlineImpact,
    DependencyImpact,
    SavingsGoalImpact,
    SuggestedAction,
    TimeImpact,
    WarningSeverity,
)
from app.services.commitment_collectors import CommitmentEvidence
from app.services.finance_calculations import account_balances, budget_end_date

DEADLINE_WARNING_DAYS = 14
DECISION_WARNING_DAYS = 7


def _ref(entity_type: str, entity_id: UUID) -> AssessmentEntityReference:
    return AssessmentEntityReference(entity_type=entity_type, entity_id=entity_id)


def _warning(
    code: str,
    severity: WarningSeverity,
    message: str,
    references: list[AssessmentEntityReference],
    **details: int | str | bool | None,
) -> CommitmentWarning:
    unique = {(item.entity_type, item.entity_id): item for item in references}
    return CommitmentWarning(
        code=code,
        severity=severity,
        message=message,
        contributing_entities=list(unique.values()),
        details=details,
    )


def _action(
    code: str,
    title: str,
    reason: str,
    references: list[AssessmentEntityReference],
) -> SuggestedAction:
    return SuggestedAction(
        code=code,
        title=title,
        reason=reason,
        contributing_entities=references,
    )


def _money_impact(evidence: CommitmentEvidence) -> tuple[list[CurrencyImpact], dict[str, int]]:
    commitment = evidence.commitment
    planned_costs: dict[str, int] = defaultdict(int)
    actual_costs: dict[str, int] = defaultdict(int)
    expected_income: dict[str, int] = defaultdict(int)
    planned_outflows_by_currency: dict[str, int] = defaultdict(int)
    for planned_item in evidence.planned_transactions:
        if planned_item.status != PlannedTransactionStatus.PLANNED:
            continue
        if planned_item.transaction_type == TransactionType.EXPENSE:
            planned_costs[planned_item.currency_code] += planned_item.amount_minor
            planned_outflows_by_currency[planned_item.currency_code] += planned_item.amount_minor
        elif planned_item.transaction_type == TransactionType.INCOME:
            expected_income[planned_item.currency_code] += planned_item.amount_minor
    for actual_item in evidence.actual_transactions:
        if actual_item.transaction_type == TransactionType.EXPENSE:
            actual_costs[actual_item.currency_code] += actual_item.amount_minor
    if commitment.planned_cost_minor is not None and commitment.currency_code is not None:
        planned_costs[commitment.currency_code] += commitment.planned_cost_minor
        planned_outflows_by_currency[commitment.currency_code] += commitment.planned_cost_minor

    balances = account_balances(evidence.accounts, evidence.ledger_transactions)
    ledger: dict[str, int] = defaultdict(int)
    account_buffers: dict[str, int] = defaultdict(int)
    for account in evidence.accounts:
        ledger[account.currency_code] += balances.get(account.id, account.opening_balance_minor)
        account_buffers[account.currency_code] += account.financial_buffer_minor
    required_buffers = dict(account_buffers)
    if (
        commitment.financial_buffer_requirement_minor is not None
        and commitment.currency_code is not None
    ):
        required_buffers[commitment.currency_code] = max(
            required_buffers.get(commitment.currency_code, 0),
            commitment.financial_buffer_requirement_minor,
        )
    currencies = sorted(
        set(planned_costs)
        | set(actual_costs)
        | set(expected_income)
        | ({commitment.currency_code} if commitment.currency_code else set())
    )
    impacts = []
    for currency in currencies:
        projected = (
            ledger.get(currency, 0)
            - planned_costs.get(currency, 0)
            + expected_income.get(currency, 0)
        )
        required = required_buffers.get(currency, 0)
        impacts.append(
            CurrencyImpact(
                currency=currency,
                planned_cost_minor=planned_costs.get(currency, 0),
                actual_cost_minor=actual_costs.get(currency, 0),
                expected_income_minor=expected_income.get(currency, 0),
                ledger_balance_minor=ledger.get(currency, 0),
                projected_available_minor=projected,
                required_financial_buffer_minor=required,
                financial_buffer_violation=projected < required,
            )
        )
    return impacts, planned_outflows_by_currency


def _time_impact(evidence: CommitmentEvidence) -> TimeImpact:
    relevant = [task for task in evidence.tasks if task.status != TaskStatus.CANCELLED]
    required = sum(task.estimated_duration_minutes or 0 for task in relevant)
    scheduled = sum(
        max(
            0,
            int((task.scheduled_end_at - task.scheduled_start_at).total_seconds() // 60),
        )
        for task in relevant
        if task.scheduled_start_at is not None and task.scheduled_end_at is not None
    )
    active_events = [
        event for event in evidence.events if event.status != CalendarEventStatus.CANCELLED
    ]
    preparation = sum(event.preparation_buffer_minutes for event in active_events)
    travel = sum(event.travel_buffer_minutes for event in active_events)
    recovery = sum(event.recovery_buffer_minutes for event in active_events)
    buffers = preparation + travel + recovery
    minimum = evidence.commitment.estimated_duration_minutes or 0
    capacity_requirement = max(minimum, required + buffers)
    unscheduled = max(0, capacity_requirement - scheduled - buffers)
    unscheduled_ids = [
        task.id
        for task in relevant
        if task.status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}
        and task.estimated_duration_minutes
        and (task.scheduled_start_at is None or task.scheduled_end_at is None)
    ]
    return TimeImpact(
        required_task_duration_minutes=required,
        scheduled_task_duration_minutes=scheduled,
        preparation_minutes=preparation,
        travel_minutes=travel,
        recovery_minutes=recovery,
        time_capacity_requirement_minutes=capacity_requirement,
        unscheduled_required_work_minutes=unscheduled,
        unscheduled_task_ids=unscheduled_ids,
    )


def _dependency_impact(evidence: CommitmentEvidence) -> DependencyImpact:
    linked_ids = {task.id for task in evidence.tasks}
    missing: set[UUID] = set()
    blocked: set[UUID] = set()
    for dependency in evidence.dependencies:
        prerequisite = evidence.dependency_targets.get(dependency.id)
        if prerequisite is None or prerequisite.id not in linked_ids:
            missing.add(dependency.depends_on_task_id)
        if prerequisite is None:
            blocked.add(dependency.task_id)
        elif dependency.dependency_type == TaskDependencyType.FINISH_TO_START:
            if prerequisite.status != TaskStatus.COMPLETED:
                blocked.add(dependency.task_id)
        elif prerequisite.status == TaskStatus.TODO:
            blocked.add(dependency.task_id)
    return DependencyImpact(
        missing_dependency_ids=sorted(missing, key=str),
        blocked_task_ids=sorted(blocked, key=str),
    )


def _budget_impacts(evidence: CommitmentEvidence) -> list[BudgetImpact]:
    impacts: list[BudgetImpact] = []
    for budget in evidence.budgets:
        report = evidence.budget_reports[budget.id]
        category_ids = {item.category_id for item in report.categories}
        ends_on = budget_end_date(budget)
        commitment_planned = sum(
            item.amount_minor
            for item in evidence.planned_transactions
            if item.status == PlannedTransactionStatus.PLANNED
            and item.transaction_type == TransactionType.EXPENSE
            and item.currency_code == budget.currency_code
            and item.category_id in category_ids
            and budget.start_date
            <= item.planned_for.astimezone(ZoneInfo(evidence.timezone_name)).date()
            <= ends_on
        )
        remaining = (
            report.total_limit_minor - report.total_actual_minor - report.total_planned_minor
        )
        impacts.append(
            BudgetImpact(
                budget_id=budget.id,
                name=budget.name,
                currency=budget.currency_code,
                total_limit_minor=report.total_limit_minor,
                total_actual_minor=report.total_actual_minor,
                total_planned_minor=report.total_planned_minor,
                commitment_planned_minor=commitment_planned,
                remaining_after_planned_minor=remaining,
                violation=commitment_planned > 0 and remaining < 0,
            )
        )
    return impacts


def _savings_impacts(
    evidence: CommitmentEvidence,
    planned_outflows: dict[str, int],
) -> list[SavingsGoalImpact]:
    impacts: list[SavingsGoalImpact] = []
    for goal in evidence.savings_goals:
        outflow = planned_outflows.get(goal.currency_code, 0)
        projected_current = max(0, goal.current_minor - outflow)
        projected_remaining = max(0, goal.target_minor - projected_current)
        delayed = (
            goal.status == GoalStatus.ACTIVE
            and outflow > 0
            and projected_remaining > max(0, goal.target_minor - goal.current_minor)
        )
        impacts.append(
            SavingsGoalImpact(
                savings_goal_id=goal.id,
                name=goal.name,
                currency=goal.currency_code,
                target_minor=goal.target_minor,
                current_minor=goal.current_minor,
                commitment_outflow_minor=outflow,
                projected_current_minor=projected_current,
                projected_remaining_minor=projected_remaining,
                delayed=delayed,
            )
        )
    return impacts


def _deadline_impact(evidence: CommitmentEvidence, now: datetime) -> DeadlineImpact:
    decision = evidence.commitment.decision_deadline_at
    target = evidence.commitment.ends_at
    return DeadlineImpact(
        decision_deadline_at=decision,
        target_end_at=target,
        decision_deadline_passed=decision is not None and decision < now,
        target_deadline_passed=target is not None and target < now,
        days_until_decision=(decision - now).days if decision is not None else None,
        days_until_target=(target - now).days if target is not None else None,
    )


def build_commitment_impact(
    evidence: CommitmentEvidence,
    *,
    now: datetime | None = None,
) -> CommitmentImpactResponse:
    evaluated_at = (now or utc_now()).astimezone(UTC)
    currencies, planned_outflows = _money_impact(evidence)
    return CommitmentImpactResponse(
        commitment_id=evidence.commitment.id,
        currencies=currencies,
        time=_time_impact(evidence),
        dependencies=_dependency_impact(evidence),
        calendar_conflicts=[
            CalendarConflictImpact(
                first_event_id=item.first.event_id,
                second_event_id=item.second.event_id,
                first_effective_start=item.first.effective_starts_at,
                first_effective_end=item.first.effective_ends_at,
                second_effective_start=item.second.effective_starts_at,
                second_effective_end=item.second.effective_ends_at,
            )
            for item in evidence.calendar_conflicts
        ],
        budgets=_budget_impacts(evidence),
        savings_goals=_savings_impacts(evidence, planned_outflows),
        deadline=_deadline_impact(evidence, evaluated_at),
        missing_link_targets=[
            _ref(entity_type.value, entity_id) for entity_type, entity_id in evidence.missing_links
        ],
    )


def _status(level: AssessmentLevel, summary: str, codes: list[str]) -> AssessmentComponent:
    return AssessmentComponent(status=level, summary=summary, warning_codes=codes)


def evaluate_commitment(
    evidence: CommitmentEvidence,
    impact: CommitmentImpactResponse,
) -> tuple[
    dict[str, AssessmentComponent],
    AssessmentLevel,
    list[CommitmentWarning],
    list[SuggestedAction],
    list[str],
]:
    commitment_ref = _ref("commitment", evidence.commitment.id)
    warnings: list[CommitmentWarning] = []
    actions: list[SuggestedAction] = []

    time_codes: list[str] = []
    if impact.time.unscheduled_required_work_minutes > 0:
        refs = [_ref("task", task_id) for task_id in impact.time.unscheduled_task_ids]
        refs = refs or [commitment_ref]
        warning = _warning(
            "unscheduled_required_work",
            WarningSeverity.WARNING,
            "Required commitment work is not fully scheduled.",
            refs,
            unscheduled_minutes=impact.time.unscheduled_required_work_minutes,
        )
        warnings.append(warning)
        time_codes.append(warning.code)
        for task_id in impact.time.unscheduled_task_ids:
            task_ref = _ref("task", task_id)
            actions.append(
                _action(
                    "schedule_unscheduled_task",
                    "Schedule required task",
                    "This linked task has estimated work but no scheduled interval.",
                    [task_ref],
                )
            )
        for task in evidence.tasks:
            if (
                task.id in impact.time.unscheduled_task_ids
                and (task.estimated_duration_minutes or 0) >= 240
            ):
                actions.append(
                    _action(
                        "split_task",
                        "Split a large task",
                        "Smaller scheduled blocks may be easier to place before the target date.",
                        [_ref("task", task.id)],
                    )
                )

    financial_codes: list[str] = []
    for money in impact.currencies:
        if not money.financial_buffer_violation:
            continue
        refs = [commitment_ref]
        refs.extend(_ref("financial_account", item.id) for item in evidence.accounts)
        refs.extend(
            _ref("planned_transaction", item.id)
            for item in evidence.planned_transactions
            if item.currency_code == money.currency
            and item.status == PlannedTransactionStatus.PLANNED
        )
        warning = _warning(
            "financial_buffer_violation",
            WarningSeverity.CRITICAL,
            f"Projected {money.currency} funds fall below the required financial buffer.",
            refs,
            currency=money.currency,
            projected_available_minor=money.projected_available_minor,
            required_buffer_minor=money.required_financial_buffer_minor,
        )
        warnings.append(warning)
        financial_codes.append(warning.code)
        actions.append(
            _action(
                "reduce_planned_expense",
                "Reduce a planned expense",
                "Lowering linked planned outflow can restore the required buffer.",
                refs,
            )
        )
        actions.append(
            _action(
                "reserve_money",
                "Reserve money for the commitment",
                "Reserve funds before accepting further discretionary spending.",
                [commitment_ref],
            )
        )

    dependency_codes: list[str] = []
    if impact.dependencies.missing_dependency_ids:
        refs = [commitment_ref] + [
            _ref("task", item) for item in impact.dependencies.missing_dependency_ids
        ]
        warning = _warning(
            "missing_dependencies",
            WarningSeverity.CRITICAL,
            "Linked work depends on tasks that are not part of this commitment.",
            refs,
            missing_count=len(impact.dependencies.missing_dependency_ids),
        )
        warnings.append(warning)
        dependency_codes.append(warning.code)
    if impact.dependencies.blocked_task_ids:
        refs = [_ref("task", item) for item in impact.dependencies.blocked_task_ids]
        warning = _warning(
            "blocked_tasks",
            WarningSeverity.WARNING,
            "One or more linked tasks are blocked by unfinished dependencies.",
            refs,
            blocked_count=len(refs),
        )
        warnings.append(warning)
        dependency_codes.append(warning.code)
        actions.append(
            _action(
                "resolve_dependency",
                "Resolve blocked task dependencies",
                "Complete or explicitly schedule the prerequisite tasks.",
                refs,
            )
        )

    schedule_codes: list[str] = []
    for conflict in impact.calendar_conflicts:
        refs = [
            _ref("calendar_event", conflict.first_event_id),
            _ref("calendar_event", conflict.second_event_id),
        ]
        warning = _warning(
            "calendar_conflict",
            WarningSeverity.CRITICAL,
            "A linked calendar event conflicts with another effective event interval.",
            refs,
        )
        warnings.append(warning)
        schedule_codes.append(warning.code)
        actions.append(
            _action(
                "move_conflicting_event",
                "Move a conflicting event",
                "Move one event or reduce its preparation, travel, or recovery buffer.",
                refs,
            )
        )

    goal_codes: list[str] = []
    for budget in impact.budgets:
        if not budget.violation:
            continue
        refs = [_ref("budget", budget.budget_id)] + [
            _ref("planned_transaction", item.id)
            for item in evidence.planned_transactions
            if item.currency_code == budget.currency
            and item.status == PlannedTransactionStatus.PLANNED
        ]
        warning = _warning(
            "budget_violation",
            WarningSeverity.CRITICAL,
            f"Linked planned spending contributes to exceeding budget '{budget.name}'.",
            refs,
            remaining_after_planned_minor=budget.remaining_after_planned_minor,
        )
        warnings.append(warning)
        goal_codes.append(warning.code)
    for goal in impact.savings_goals:
        if not goal.delayed:
            continue
        refs = [_ref("savings_goal", goal.savings_goal_id), commitment_ref]
        warning = _warning(
            "savings_goal_delay",
            WarningSeverity.WARNING,
            f"Commitment outflow increases the remaining amount for '{goal.name}'.",
            refs,
            projected_remaining_minor=goal.projected_remaining_minor,
        )
        warnings.append(warning)
        goal_codes.append(warning.code)
        actions.append(
            _action(
                "extend_target_date",
                "Review the savings target date",
                "The linked outflow increases the amount still required for this goal.",
                refs,
            )
        )

    deadline_codes: list[str] = []
    deadline = impact.deadline
    if deadline.decision_deadline_passed or deadline.target_deadline_passed:
        warning = _warning(
            "deadline_passed",
            WarningSeverity.CRITICAL,
            "A commitment decision or target deadline has passed.",
            [commitment_ref],
            decision_deadline_passed=deadline.decision_deadline_passed,
            target_deadline_passed=deadline.target_deadline_passed,
        )
        warnings.append(warning)
        deadline_codes.append(warning.code)
    elif (
        deadline.days_until_decision is not None
        and deadline.days_until_decision <= DECISION_WARNING_DAYS
    ) or (
        deadline.days_until_target is not None
        and deadline.days_until_target <= DEADLINE_WARNING_DAYS
        and impact.time.unscheduled_required_work_minutes > 0
    ):
        warning = _warning(
            "deadline_risk",
            WarningSeverity.WARNING,
            "A decision or target date is near while required work remains unresolved.",
            [commitment_ref],
        )
        warnings.append(warning)
        deadline_codes.append(warning.code)
        actions.append(
            _action(
                "extend_target_date",
                "Extend the target date",
                "More time may be needed for the currently unscheduled or blocked work.",
                [commitment_ref],
            )
        )

    if impact.missing_link_targets:
        warning = _warning(
            "missing_link_targets",
            WarningSeverity.CRITICAL,
            "One or more stored commitment links no longer resolve to active records.",
            [commitment_ref, *impact.missing_link_targets],
            missing_count=len(impact.missing_link_targets),
        )
        warnings.append(warning)
        dependency_codes.append(warning.code)

    def component(
        codes: list[str],
        *,
        applicable: bool,
        summary: str,
    ) -> AssessmentComponent:
        relevant = [item for item in warnings if item.code in codes]
        if not applicable:
            return _status(AssessmentLevel.NOT_APPLICABLE, summary, codes)
        if any(item.severity == WarningSeverity.CRITICAL for item in relevant):
            return _status(AssessmentLevel.CRITICAL, summary, codes)
        if relevant:
            return _status(AssessmentLevel.WARNING, summary, codes)
        return _status(AssessmentLevel.OK, summary, codes)

    components = {
        "time": component(
            time_codes,
            applicable=impact.time.time_capacity_requirement_minutes > 0,
            summary=(
                f"{impact.time.unscheduled_required_work_minutes} required minutes "
                "remain unscheduled."
            ),
        ),
        "financial": component(
            financial_codes,
            applicable=bool(impact.currencies),
            summary=f"{len(impact.currencies)} currency group(s) evaluated.",
        ),
        "dependency": component(
            dependency_codes,
            applicable=bool(evidence.tasks or impact.missing_link_targets),
            summary=(
                f"{len(impact.dependencies.blocked_task_ids)} blocked task(s), "
                f"{len(impact.dependencies.missing_dependency_ids)} missing prerequisite(s)."
            ),
        ),
        "schedule": component(
            schedule_codes,
            applicable=bool(evidence.events),
            summary=f"{len(impact.calendar_conflicts)} calendar conflict(s) detected.",
        ),
        "goal": component(
            goal_codes,
            applicable=bool(impact.budgets or impact.savings_goals or evidence.goals),
            summary=(
                f"{len(impact.budgets)} budget(s) and "
                f"{len(impact.savings_goals)} savings goal(s) evaluated."
            ),
        ),
        "deadline": component(
            deadline_codes,
            applicable=(
                impact.deadline.decision_deadline_at is not None
                or impact.deadline.target_end_at is not None
            ),
            summary="Decision and target deadlines evaluated against the calculation time.",
        ),
    }
    applicable_levels = [
        item.status for item in components.values() if item.status != AssessmentLevel.NOT_APPLICABLE
    ]
    if AssessmentLevel.CRITICAL in applicable_levels:
        overall = AssessmentLevel.CRITICAL
    elif AssessmentLevel.WARNING in applicable_levels:
        overall = AssessmentLevel.WARNING
    elif applicable_levels:
        overall = AssessmentLevel.OK
    else:
        overall = AssessmentLevel.NOT_APPLICABLE
    severity_order = {
        WarningSeverity.CRITICAL: 0,
        WarningSeverity.WARNING: 1,
        WarningSeverity.INFO: 2,
    }
    warnings.sort(key=lambda item: (severity_order[item.severity], item.code, item.message))
    unique_actions = {(item.code, item.title, item.reason): item for item in actions}
    ordered_actions = sorted(unique_actions.values(), key=lambda item: (item.code, item.title))
    assumptions = [
        "All money is evaluated in separate ISO 4217 currency groups without conversion.",
        "Only active linked source records contribute; missing targets are surfaced explicitly.",
        (
            "Posted transactions already affect ledger balance; only open linked plans "
            "affect projection."
        ),
        (
            "Time capacity is the greater of the manual requirement and linked task "
            "estimates plus event buffers."
        ),
        (
            "Calendar conflicts use effective intervals including preparation, travel, "
            "and recovery buffers."
        ),
        (
            f"Deadline warning windows are {DECISION_WARNING_DAYS} days for decisions "
            f"and {DEADLINE_WARNING_DAYS} days for targets."
        ),
        (
            "No aggregate feasibility score is calculated; overall status is the worst "
            "applicable component."
        ),
    ]
    return components, overall, warnings, ordered_actions, assumptions
