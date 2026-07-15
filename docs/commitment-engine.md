# Commitment engine and unified timeline

## Scope

The commitment engine answers a local planning question: what does accepting or continuing a
commitment require from the user's existing time, schedule, money, budgets, and goals? It does not
predict behavior, call a remote service, or produce an opaque feasibility score. Every result is a
deterministic projection over active local records and includes the source entity IDs that explain
warnings and suggested actions.

Commitments can link projects, tasks, calendar events, notes, planned transactions, posted
transactions, budgets, savings goals, and general goals. A commitment stores its own title,
Markdown description, lifecycle status, category, target interval, optional decision deadline,
optional manual time-capacity requirement, and optional currency-specific financial-buffer
requirement.

## Service pipeline

Assessment is deliberately split into three layers:

```text
commitment + typed links
          |
          v
evidence collector -----> typed CommitmentEvidence
          |
          v
impact calculators -----> money, time, dependencies, conflicts, budgets, goals, deadlines
          |
          v
rule evaluator ---------> component statuses, warnings, assumptions, suggested actions
```

The collector resolves links in the current workspace, rejects soft-deleted records from active
evidence, loads task prerequisites, delegates conflict detection to the calendar service, and
delegates budget consumption to the finance report service. Missing stored targets are retained in
the assessment as explicit evidence rather than silently ignored.

Calculators return typed intermediate results. The evaluator consumes those results without
querying the database. This separation keeps data collection, arithmetic, and policy rules
independently testable.

## Component calculations

### Time capacity

The engine sums estimates for linked non-cancelled tasks and preparation, travel, and recovery
buffers for linked non-cancelled events. The effective requirement is the greater of:

- the commitment's manual time-capacity requirement; or
- linked task estimates plus linked event buffers.

Scheduled minutes come from complete start/end intervals on linked tasks. Remaining unscheduled
work is the effective requirement minus scheduled task time and event buffers, clamped at zero.
Active estimated tasks without a complete scheduled interval are returned as traceable unscheduled
task IDs.

The capacity assessment remains a fast deterministic diagnostic. Prompt 6 adds a separate
commitment scheduling action that takes the active tasks linked to a commitment, treats the target
end as an effective hard deadline, and returns concrete CP-SAT placements or per-task reasons. It
does not change the assessment formula or mutate the commitment.

### Dependencies

A prerequisite is *missing from the commitment* when a linked task depends on a task that is not
also linked, or when the stored prerequisite no longer resolves. Blocking follows the existing task
dependency semantics: a finish-to-start prerequisite must be completed; a start-to-start
prerequisite must have progressed beyond `todo`. Missing prerequisites and blocked dependent tasks
are returned separately.

### Calendar conflicts

The existing calendar conflict service expands each event to an effective interval:

```text
effective start = event start - preparation - travel
effective end   = event end + recovery
```

All-day boundaries are interpreted in the event's IANA timezone before UTC comparison. The
assessment includes a conflict when at least one side is linked to the commitment, so it can expose
an unlinked appointment that competes with linked commitment time. Both event IDs and both
effective intervals are returned.

### Money and financial buffers

Money is grouped by ISO 4217 currency and never converted. For each applicable currency:

```text
planned cost       = open linked expense plans + legacy manual commitment cost
actual cost        = linked posted expenses, including the actual of a fulfilled linked plan
expected income    = open linked income plans
ledger balance     = opening balances + all posted ledger effects in that currency
projected available = ledger balance - planned cost + expected income
required buffer    = max(sum of account buffers, commitment-specific buffer)
```

Posted expense is reported as actual cost but is not subtracted twice: it already affects the
derived ledger balance. A critical buffer warning fires when projected available money is below the
required buffer.

### Budgets and savings goals

Linked budgets reuse their normal actual/planned consumption report. The engine identifies linked
expense plans that fall within the budget period, currency, and limited categories. A budget
warning fires only when linked planned spending contributes and the budget's remaining amount
after all actual and planned consumption is negative.

For each linked active savings goal, the engine conservatively applies linked planned outflow in
the same currency to the current saved amount. It reports projected current and remaining amounts.
A delay warning fires when the outflow increases the amount still required to reach the goal.

General goals can be linked and appear in timeline context. They currently make the goal component
applicable but do not invent a monetary or percentage effect without a defined domain relationship.

### Deadlines

Decision and target deadlines are compared with the UTC calculation time. Passed deadlines are
critical. A decision within seven days is a warning; a target within fourteen days is a warning
when required work remains unscheduled. These constants are explicit in the evaluator rather than
learned or hidden.

## Status and explanation contract

Each assessment has six components: time capacity, financial capacity, dependencies, schedule
conflicts, goal impact, and deadlines. A component is one of:

- `not_applicable`: no relevant evidence or configured constraint;
- `ok`: applicable evidence was evaluated and no rule fired;
- `warning`: at least one non-critical rule fired;
- `critical`: at least one critical rule fired.

The overall status is the worst applicable component. It is not a numeric score. Warnings have a
stable code, severity, message, calculation details, and one or more contributing entity
references. Suggested actions likewise name their source entities. Assumptions explicitly state
currency separation, active-record handling, ledger semantics, time-capacity rules, conflict
buffers, deadline windows, and the absence of an aggregate score.

Current warning codes are:

| Code | Trigger |
| --- | --- |
| `unscheduled_required_work` | Effective required minutes exceed scheduled task time and buffers |
| `financial_buffer_violation` | Projected available funds fall below the required buffer |
| `missing_dependencies` | A linked task prerequisite is not linked or no longer resolves |
| `blocked_tasks` | A linked task has an unfinished blocking prerequisite |
| `calendar_conflict` | A linked event's effective interval overlaps another event |
| `budget_violation` | Linked planned expense contributes to a negative budget remainder |
| `savings_goal_delay` | Linked outflow increases a linked goal's remaining amount |
| `deadline_passed` | Decision or target deadline is past |
| `deadline_risk` | A configured deadline is near under the documented rule |
| `missing_link_targets` | A stored link does not resolve to an active local record |

## Lifecycle and refresh

Commitments use optimistic revisions for updates, archive, and deletion. Archive is an explicit
action. Archived commitments are omitted from the default collection, remain readable when
requested, retain their links as an audit snapshot, and reject edits and link mutations. Final
deletion soft-deletes the commitment and removes relationship rows. Deleting a linked source
record removes its commitment links through the source service's transaction.

`POST /api/v1/commitments/{id}/refresh` recalculates on demand and returns the same assessment
contract as `GET .../assessment`. It does not persist cached totals, increment the commitment
revision, or emit timeline activity. Repeating it against unchanged source records is idempotent
apart from `calculated_at`.

## API surface

| Method and path | Purpose |
| --- | --- |
| `GET/POST /api/v1/commitments` | Filtered collection and creation |
| `GET/PATCH/DELETE /api/v1/commitments/{id}` | Read, revision-checked update, and deletion |
| `POST /api/v1/commitments/{id}/archive` | Revision-checked archive action |
| `GET/POST /api/v1/commitments/{id}/links` | Read or create typed links |
| `DELETE /api/v1/commitments/{id}/links/{link_id}` | Remove one active link |
| `GET /api/v1/commitments/{id}/assessment` | Full component assessment |
| `GET /api/v1/commitments/{id}/impact` | Calculation intermediates without policy summaries |
| `GET /api/v1/commitments/{id}/warnings` | Warnings, assumptions, and suggested actions |
| `POST /api/v1/commitments/{id}/refresh` | Idempotent on-demand recalculation |
| `GET /api/v1/commitments/{id}/timeline` | Unified timeline restricted to the commitment context |
| `POST /api/v1/commitments/{id}/schedule-preview` | Non-mutating schedule for linked tasks |
| `GET /api/v1/timeline/unified` | Workspace-wide unified timeline |

## Unified timeline and privacy

The unified timeline returns typed items for task schedule/deadline/activity, calendar events, note
activity, posted and planned transactions, savings and general goal milestones, and commitment
changes. It supports half-open date filters, entity type, entity ID, stable ascending or descending
order, and pagination. A commitment-specific query includes its own change events and current
timeline representations of linked source records.

Timeline items are summaries, not a second data export. Note items expose the title and activity
timestamp but never Markdown. Financial items are marked `sensitive`, use generic titles such as
`Planned expense`, and omit amount, account, payee, note, and category. Clients that need those
details must deliberately request the protected domain endpoint. Related commitment IDs are
included as typed references.

## Synthetic acceptance fixtures

`apps/api/tests/fixtures/commitment_scenarios.json` defines three reusable cases:

- **OpenAI Build Week**: time-only work whose estimates are completely scheduled;
- **Berlin technology conference**: tasks, a missing prerequisite, buffered event conflict,
  actual/planned money, expected reimbursement, budget overrun, savings delay, financial-buffer
  violation, note, project, and general goal;
- **Laptop purchase**: finance-only planned expense that breaches a manual buffer.

Tests also cover an empty commitment, all nine link target types, optimistic conflicts, archive and
deletion behavior, target-deletion cleanup, component transparency, refresh idempotency, unified
timeline filters/order/pagination, and content privacy.

`apps/api/tests/fixtures/scheduling_scenarios.json` adds conference and hackathon commitments with
bounded task sets. Both are solved through the commitment schedule-preview endpoint, and every
linked task must appear as either a placement or an explainable unscheduled result.

## Deferred work

There is no commitment frontend, notification scheduler, exchange-rate service, probabilistic
forecast, AI recommendation, persisted assessment snapshot, or automatic action execution. Those
capabilities require separate product decisions and must not be inferred from the current local
calculation engine.
