# API conventions

LocalLife OS exposes a local HTTP API under `/api/v1`. These conventions are the stable
foundation for current and future domain endpoints.

## Transport and identifiers

- The API is intended for loopback access only. Docker publishes it on `127.0.0.1:8000`.
- Resource identifiers are UUID strings.
- JSON is the default request and response format. Attachment upload uses `multipart/form-data`,
  and attachment download returns the stored media type as a file response.
- Every response includes `X-Request-ID`. A valid incoming `X-Request-ID` is preserved;
  otherwise the API creates one.
- Request bodies reject unknown fields.

## Successful responses

A single resource is wrapped in a `data` envelope:

```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "name": "Local workspace",
    "revision": 1
  }
}
```

A collection uses the same `data` key and adds pagination metadata:

```json
{
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 50,
    "total_items": 0,
    "total_pages": 0
  }
}
```

Deletion returns a resource-shaped acknowledgement rather than an empty body:

```json
{
  "data": {
    "id": "8a2ce15f-c683-46ad-b17d-c43dfbed342e",
    "deleted": true
  }
}
```

## Errors

All handled errors use one envelope:

```json
{
  "error": {
    "code": "revision_conflict",
    "message": "workspace changed since it was read.",
    "details": {
      "expected_revision": 1,
      "current_revision": 2
    },
    "request_id": "6d6bfbc8-e53a-45d5-9df8-e071a175f6b8"
  }
}
```

`code` is a stable machine-readable value. `message` is suitable for a local user interface.
`details` is optional and its shape depends on the error. Validation errors use HTTP 422,
missing resources 404, uniqueness or revision conflicts 409, and unexpected errors 500.

## Pagination

Collection endpoints accept:

- `page`: one-based page number, default `1`.
- `page_size`: items per page, default `50`, maximum `100`.

`total_items` counts all records matching the filter before offset/limit. `total_pages` is zero
for an empty collection. Ordering always includes a stable UUID tie-breaker so adjacent pages do
not duplicate or omit equal-valued rows.

## Filtering and sorting

Filters are endpoint-specific query parameters. Text search uses `q`; tags use case-insensitive
matching, while notes use workspace-scoped SQLite FTS5. Timeline filters include `entity_type`,
`entity_id`, and `action`. The unified timeline accepts a half-open date range, entity type, entity
ID, stable order, and pagination. Task filters include project, parent, status, priority, tag, due
range, and the derived `overdue`, `blocked`, and `schedulable` states. Calendar events require a
half-open date-time range and can filter by category and status. Omitted optional filters do not
restrict the collection.

Sortable endpoints accept a documented `sort` field and `order=asc|desc`. Unsupported values are
rejected with HTTP 422. The initial tag endpoint supports `name`, `created_at`, and `updated_at`.
The timeline is sorted by `occurred_at` and UUID.

## Timestamps and dates

- API datetimes are RFC 3339 strings with an explicit UTC offset, for example
  `2026-07-15T10:30:00Z`.
- Naive datetimes are rejected at request boundaries.
- Datetimes are normalized to UTC for persistence; the user's IANA timezone is stored separately
  in preferences for presentation.
- All-day calendar intervals use ISO dates and an exclusive `all_day_end`, avoiding artificial
  midnight timestamps.

## Money

Persisted and API money values use an integer minor-unit amount plus an uppercase ISO 4217 code:

```json
{
  "amount_minor": 117000,
  "currency_code": "EUR"
}
```

There are no persisted binary floating-point money values. The application layer decides how
many decimal places to display for a currency. Transfers require distinct source and destination
accounts with the same currency.

## Optimistic concurrency and deletion

User-editable resources expose a positive integer `revision`. Mutation requests must send the
revision last read by the client. Updates atomically match and increment it. If another mutation
won the race, the API responds with HTTP 409 and the expected/current revisions; clients must
reload before retrying.

Soft-deleted user records are excluded from normal reads. Link rows are generally hard-deleted
because they represent relationships, not user content. Removing a tag, note, dependency, or
commitment link never deletes its target. Attachment links are retained when an owning domain
record is soft-deleted to prevent implicit file loss; explicitly deleting the attachment removes
its links, metadata from active reads, and local bytes.

Bulk task actions accept up to 100 unique items, each carrying its own revision, and commit as one
transaction. Calendar `move` and `resize`, project `archive`, task dependency operations, and note
link operations use explicit action subresources where ordinary CRUD would obscure intent.

Scheduling follows the same explicit-action rule. `preview` is non-mutating and persists an
expiring source snapshot; `apply` is the only scheduling action that writes task intervals. Apply
compares the current source fingerprint and expected task revisions before writing. A changed task,
dependency, calendar constraint, preference, commitment, or existing scheduled task causes a
structured HTTP 409 instead of silently applying stale advice. Applying multiple placements and
their timeline events is one transaction.

Commitment archive and refresh also use explicit actions. Archive retains typed links, excludes the
record from normal lists, and makes the commitment immutable. Refresh is a read-like calculation
expressed as an action: it writes no cache, emits no timeline event, and does not increment the
revision.

## Recurrence rules

Task and calendar recurrence uses a canonical iCalendar-compatible RRULE value such as
`FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE`. Requests may instead send the typed
frequency/interval/weekday/end form; the API converts it to RRULE. A request cannot provide both
forms. Recurrence ranges are half-open, timezone-aware, and limited to 1,000 returned occurrences.

Finance recurrence rules use the same canonical RRULE representation. Materializing a finance
occurrence creates a planned transaction with a stable rule/UTC-occurrence key. Repeating the same
generation request returns no new rows rather than duplicating projected money.

## Finance calculations

Posted and planned transactions are separate resources. Plans never affect an account ledger;
fulfillment atomically posts one actual transaction and closes the plan. Transfers are represented
by one record with source and destination effects and are cash-flow neutral.

Finance report dates are inclusive API dates converted to half-open UTC ranges in the workspace
timezone. Reports return `metadata` with the exact input range, optional currency filter,
assumptions, included/excluded record references, and calculation timestamp. Without a currency
filter, monetary results are grouped by currency; exchange-rate conversion is never inferred.

## Commitment assessments

Commitment assessments collect active linked evidence and calculate typed time, money, dependency,
calendar, budget, savings, and deadline impacts. Component statuses are `not_applicable`, `ok`,
`warning`, or `critical`; the overall status is the worst applicable component. There is no numeric
feasibility score. Every warning and suggested action carries contributing entity references, and
the response lists calculation assumptions.

Money remains separated by currency. Posted expenses are reported as actual cost but are not
subtracted from projection twice because they already affect the ledger. Calendar conflicts reuse
effective event intervals with preparation, travel, and recovery buffers. Assessment and refresh
responses are calculated on demand and are not persisted.

Unified timeline items expose typed summaries. Note Markdown is omitted. Financial items use
generic titles, are marked `sensitive`, and omit amount, account, category, payee, and note fields.

## Foundational endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/workspaces/current` | Read the default local workspace |
| `PATCH /api/v1/workspaces/current` | Revision-checked workspace update |
| `GET /api/v1/preferences` | Read local workspace preferences |
| `PATCH /api/v1/preferences` | Revision-checked preference update |
| `GET /api/v1/tags` | Filtered, sorted, paginated active tags |
| `POST /api/v1/tags` | Create a tag |
| `DELETE /api/v1/tags/{id}` | Revision-checked soft deletion |
| `GET /api/v1/timeline` | Filtered, paginated timeline |
| `GET /api/v1/timeline/unified` | Filtered typed timeline with privacy-limited summaries |
| `GET /api/v1/meta/enums` | Stable values used by typed API fields |

## Productivity endpoints

| Method and path | Purpose |
| --- | --- |
| `GET/POST /api/v1/projects` | Paginated projects and project creation |
| `GET/PATCH /api/v1/projects/{id}` | Read or revision-check a project update |
| `POST /api/v1/projects/{id}/archive` | Explicit revision-checked archive action |
| `GET/POST /api/v1/tasks` | Filtered tasks and task creation |
| `GET/PATCH/DELETE /api/v1/tasks/{id}` | Task CRUD with optimistic concurrency |
| `POST/DELETE /api/v1/tasks/{id}/dependencies[...]` | Directed dependency actions |
| `POST /api/v1/tasks/actions/bulk-complete` | Atomic bulk completion |
| `POST /api/v1/tasks/actions/bulk-reschedule` | Atomic bulk scheduling |
| `GET /api/v1/tasks/{id}/occurrences` | Expand task RRULE in a range |
| `POST /api/v1/tasks/{id}/schedule-suggestions` | Persist a non-mutating single-task preview |
| `GET/POST /api/v1/notes` | FTS-backed notes and note creation |
| `GET/PATCH/DELETE /api/v1/notes/{id}` | Note CRUD with optimistic concurrency |
| `POST/DELETE /api/v1/notes/{id}/links[...]` | Note link and backlink lifecycle |
| `GET/POST /api/v1/attachments` | Attachment metadata list and multipart upload |
| `GET /api/v1/attachments/{id}/download` | Confined local file download |
| `DELETE /api/v1/attachments/{id}` | Revision-checked attachment deletion and byte removal |
| `GET/POST /api/v1/calendar/events` | Range query and event creation |
| `GET/PATCH/DELETE /api/v1/calendar/events/{id}` | Calendar event CRUD |
| `POST /api/v1/calendar/events/{id}/move` | Move while preserving duration |
| `POST /api/v1/calendar/events/{id}/resize` | Resize while preserving start |
| `GET /api/v1/calendar/events/{id}/occurrences` | Expand event RRULE in a range |
| `GET /api/v1/calendar/conflicts` | Buffer- and timezone-aware conflicts |

Task create/update accepts `earliest_start_at` and `preferred_time_of_day`. Earliest start is a hard
bound; `morning`, `afternoon`, and `evening` are soft preferences. Existing manual task scheduling
and bulk reschedule endpoints remain authoritative and unchanged.

## Finance and goal endpoints

| Method and path | Purpose |
| --- | --- |
| `GET/POST /api/v1/finance/accounts` | Derived-balance account list and creation |
| `GET/PATCH/DELETE /api/v1/finance/accounts/{id}` | Revision-checked account CRUD |
| `GET /api/v1/finance/accounts/{id}/ledger` | Ordered ledger with running balances |
| `GET/POST /api/v1/finance/categories` | Income/expense category list and creation |
| `GET/PATCH/DELETE /api/v1/finance/categories/{id}` | Category CRUD; seeded defaults are protected |
| `GET/POST /api/v1/finance/transactions` | Filtered posted transactions and creation |
| `GET/PATCH/DELETE /api/v1/finance/transactions/{id}` | Posted transaction CRUD |
| `GET/POST /api/v1/finance/transfers` | Atomic same-currency transfers |
| `GET/POST /api/v1/finance/transactions/planned` | Planned transaction list and creation |
| `GET/PATCH/DELETE /api/v1/finance/transactions/planned/{id}` | Planned transaction CRUD |
| `POST .../planned/{id}/cancel` | Revision-checked plan cancellation |
| `POST .../planned/{id}/fulfill` | Atomic plan fulfillment into one posted transaction |
| `GET/POST /api/v1/finance/recurring` | Recurring rule list and creation |
| `GET/PATCH/DELETE /api/v1/finance/recurring/{id}` | Recurring rule CRUD |
| `POST .../recurring/{id}/generate` | Idempotently generate plans in a range |
| `POST .../recurring/{id}/{pause,resume,end}` | Explicit recurrence lifecycle actions |
| `GET/POST /api/v1/finance/budgets` | Budget and normalized category-limit management |
| `GET /api/v1/finance/budgets/{id}/consumption` | Actual/planned budget consumption |
| `GET/POST /api/v1/finance/savings-goals` | Savings-goal tracking |
| `POST .../savings-goals/{id}/contributions` | Revision-checked goal contribution |
| `GET/POST /api/v1/finance/subscriptions` | Subscription lifecycle and billing rules |
| `GET/PATCH/DELETE /api/v1/finance/subscriptions/{id}` | Subscription CRUD and price-change history |
| `GET /api/v1/finance/reports/cash-flow` | Explainable monthly cash-flow projection |
| `GET /api/v1/finance/reports/spending-by-category` | Actual/planned category spending |
| `GET /api/v1/finance/reports/committed-balance` | Effective balance and buffer check |
| `GET/POST /api/v1/goals` | General goal tracking |

## Commitment endpoints

| Method and path | Purpose |
| --- | --- |
| `GET/POST /api/v1/commitments` | Filtered commitment list and creation |
| `GET/PATCH/DELETE /api/v1/commitments/{id}` | Revision-aware commitment lifecycle |
| `POST /api/v1/commitments/{id}/archive` | Explicit archive with retained links |
| `GET/POST /api/v1/commitments/{id}/links` | List and add validated typed links |
| `DELETE /api/v1/commitments/{id}/links/{link_id}` | Remove one active relationship |
| `GET /api/v1/commitments/{id}/assessment` | Full explainable component assessment |
| `GET /api/v1/commitments/{id}/impact` | Typed calculation intermediates |
| `GET /api/v1/commitments/{id}/warnings` | Traceable warnings, assumptions, and actions |
| `POST /api/v1/commitments/{id}/refresh` | Idempotent on-demand recalculation |
| `GET /api/v1/commitments/{id}/timeline` | Unified timeline scoped to one commitment |
| `POST /api/v1/commitments/{id}/schedule-preview` | Schedule tasks linked to one commitment |

## Scenario endpoints and acceptance contract

| Method and path | Purpose |
| --- | --- |
| `GET/POST /api/v1/scenarios` | List isolated branches or capture a new branch from the workspace |
| `GET/PATCH /api/v1/scenarios/{id}` | Read or revision-check scenario metadata |
| `POST /api/v1/scenarios/{id}/discard` | Explicitly discard without touching primary records |
| `GET/POST /api/v1/scenarios/{id}/changes` | List or append typed overlay changes |
| `PATCH/DELETE /api/v1/scenarios/{id}/changes/{change_id}` | Revision-check an overlay edit or removal |
| `GET /api/v1/scenarios/{id}/preview` | Calculate metrics, differences, staleness, and an exact change plan |
| `POST /api/v1/scenarios/compare` | Compare exactly two or three scenario previews |
| `POST /api/v1/scenarios/{id}/accept` | Atomically apply the reviewed exact plan |

Scenario changes target tasks, calendar events, planned transactions, commitments, or goals and
use `create`, `update`, or `delete`. The service captures `__expected_revision` when an existing
record is added to a branch; clients do not manufacture it. Preview returns a deterministic source
fingerprint and marks missing or concurrently edited sources stale. Acceptance must include that
fingerprint, rechecks all source revisions, and either applies the entire ordered plan or applies
nothing. Preview and comparison never write primary domain records.

## Scheduling endpoints and preview contract

| Method and path | Purpose |
| --- | --- |
| `POST /api/v1/scheduling/preview` | Solve and persist a non-mutating multi-task preview |
| `POST /api/v1/scheduling/apply` | Atomically apply all or a selected subset of placements |
| `GET /api/v1/scheduling/capacity` | Report required, free, focus-capable, and remaining time |
| `GET /api/v1/scheduling/explanations/{preview_id}` | Read persisted reasons, conflicts, risks, and objective |

Preview requests accept at most 100 unique tasks and a half-open planning horizon no longer than 30
days. They include weekly local working windows, optional absolute personal-availability windows,
minimum focus block, maximum daily scheduled minutes, objective weights, and an explicit solver
time limit. Results always account for every requested task as either a placement or an unscheduled
item with one or more reason codes.

Solver status distinguishes `optimal`, best-known `feasible`, `infeasible`, `unknown`,
`model_invalid`, and `not_run`. A timeout can therefore return a feasible result without claiming
optimality; `unknown` returns no invented placement and uses the `solver_timeout` reason. Preview
responses also include hard/soft conflicts, daily and weekly capacity, deadline risk, assumptions,
source fingerprint, and an objective breakdown.
