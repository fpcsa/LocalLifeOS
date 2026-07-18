# LocalLife OS — Sequential Codex Implementation Prompts

Use these prompts **in order** and preferably in the **same Codex session** so the final `/feedback` session ID covers most of the core implementation.

Before starting:

- Place the repository-ready `README.md` at the project root.
- Start Codex from the repository root.
- Allow Codex to inspect and modify the repository.
- Keep all work in one main session unless the context becomes unusable.
- After each goal, review the result, run the listed verification commands, and then send the next prompt.
- Do not provide any runtime OpenAI key. LocalLife OS must remain fully local and deterministic.

---

## Prompt 1 — Repository foundation and development environment

```text
/goal Build the complete LocalLife OS monorepo foundation and make the empty application runnable locally through Docker Compose and native development commands.

You are the lead software architect and senior full-stack engineer for LocalLife OS.

Read the root README.md completely before making changes. Treat it as the product contract. Also inspect all existing files and preserve any useful work already present. Do not delete or overwrite unrelated user changes.

LocalLife OS is a fully on-device browser application. It must not require any API key, remote database, telemetry service, CDN asset, remote font, or external runtime request.

Implement the repository foundation only. Do not build full product features yet.

Required architecture:

Frontend:
- Next.js
- TypeScript
- Tailwind CSS
- TanStack Query
- Zustand
- Local assets only
- No remote fonts or CDN imports

Backend:
- Python
- FastAPI
- Pydantic
- SQLModel
- SQLite
- Alembic

Local execution:
- Docker Compose for development and judging
- Native development commands
- Backend bound to 127.0.0.1 outside containers
- Frontend accessible at 127.0.0.1:3000
- Backend API at 127.0.0.1:8000
- No telemetry
- No external requests

Create or normalize this monorepo structure:

locallife-os/
  apps/
    web/
    api/
  packages/
    shared-types/
    ui/
  data/
    demo/
    imports/
    backups/
    attachments/
  docs/
  scripts/
  tests/
    integration/
    e2e/
    fixtures/
  docker-compose.yml
  .env.example
  .gitignore
  Makefile or equivalent cross-platform task documentation
  README.md

Backend requirements:
1. Create a FastAPI application with:
   - GET /api/v1/health
   - GET /api/v1/system/info
   - structured error responses
   - request ID middleware
   - local-only CORS configuration
   - startup database initialization
2. Configure SQLModel and SQLite.
3. Configure Alembic and create an initial migration for a minimal system_settings table or equivalent.
4. Add application settings through Pydantic Settings.
5. Ensure paths are resolved safely and created automatically.
6. Add pytest configuration and initial health tests.
7. Add Ruff and type-checking configuration.

Frontend requirements:
1. Create a functional Next.js application shell.
2. Add:
   - top application bar
   - left navigation
   - main content area
   - simple Today placeholder page
   - system status indicator that calls the backend health endpoint
3. Configure TanStack Query.
4. Configure Zustand with a small UI store.
5. Use only system or bundled local fonts.
6. Add ESLint, TypeScript strict mode, and basic component tests.
7. Add an API client layer rather than calling fetch directly from pages.
8. Add a clean neutral desktop-first visual design.

Docker requirements:
1. Create frontend and backend Dockerfiles.
2. Create docker-compose.yml with:
   - web
   - api
   - persistent local data volume
   - health checks
   - explicit localhost port mappings
3. Containers must not depend on cloud services.
4. Add development-friendly bind mounts only when appropriate.
5. Ensure startup order is reliable.

Scripts and documentation:
1. Create:
   - scripts/start-local.sh
   - scripts/start-local.ps1
   - scripts/stop-local.sh
   - scripts/stop-local.ps1
2. Create docs/architecture.md with the initial architecture.
3. Create docs/codex-development-log.md.
4. Create docs/implementation-status.md with a checklist of this goal and future goals.
5. Record the important decisions made in this goal in the Codex development log.
6. Update README setup instructions only where the generated commands differ from the current draft.

Engineering rules:
- Do not add runtime AI.
- Do not add authentication against remote providers.
- Do not use remote fonts.
- Do not add analytics or telemetry.
- Avoid placeholder code that cannot run.
- Prefer small, typed, testable modules.
- Keep the API under /api/v1.
- Use UTC internally and preserve user timezone settings in data models.
- Use UUIDs for domain entity identifiers unless there is a strong documented reason not to.
- Do not claim encryption is implemented unless it actually is; encryption will be handled in a later goal.

Acceptance criteria:
- docker compose up --build starts both services.
- GET http://127.0.0.1:8000/api/v1/health returns a successful response.
- http://127.0.0.1:3000 loads the LocalLife OS shell and shows backend status.
- Alembic migrations run successfully.
- Backend tests pass.
- Frontend lint and type checking pass.
- No frontend asset references a remote host.
- No API key is required.

At the end:
1. Run all relevant tests, linting, and type checks.
2. Report the exact commands executed and their results.
3. List all files created or materially changed.
4. Update docs/implementation-status.md.
5. Update docs/codex-development-log.md.
6. Stop after completing this goal. Do not continue into product-domain implementation.
```

---

## Prompt 2 — Domain model, persistence layer, and API conventions

```text
/goal Implement the LocalLife OS domain model, database schema, repository layer, service layer, and stable API conventions without building the full user interface.

Continue in the same repository and session.

Read README.md, docs/architecture.md, docs/implementation-status.md, and the existing code before changing anything. Preserve working behavior from the previous goal.

Implement the persistent domain foundation for these entities:

Core:
- Workspace
- UserPreferences
- Tag
- Attachment
- TimelineEvent

Productivity:
- Project
- Task
- TaskDependency
- Note
- NoteLink
- CalendarEvent

Finance:
- FinancialAccount
- Transaction
- TransactionCategory
- Budget
- BudgetCategoryLimit
- SavingsGoal

Connected model:
- Commitment
- CommitmentEntityLink
- Goal
- AutomationRule
- Scenario
- ScenarioChange

Model requirements:
- UUID identifiers.
- created_at and updated_at timestamps.
- soft deletion where it is useful and justified.
- optimistic concurrency field or revision number for user-editable entities.
- timezone-aware event fields.
- monetary values stored as integer minor units plus ISO currency code; do not use binary floating point for persisted money.
- recurring-event and recurring-task metadata represented explicitly.
- normalized many-to-many relationships.
- attachments reference safe local storage paths and metadata, not arbitrary absolute paths.
- notes use Markdown source text.
- transactions support income, expense, and transfer types.
- calendar events support all-day and timed events.
- tasks support status, priority, estimated duration, due date, scheduled interval, and recurrence.
- commitments can link to tasks, events, notes, transactions, budgets, and goals through typed links.
- scenarios must be isolated from primary records through overlay/change records, not destructive copies of the whole database.

Create:
1. SQLModel table models.
2. Pydantic request and response schemas separate from persistence models where appropriate.
3. Repository classes or functions.
4. Service-layer modules.
5. Alembic migrations for all implemented tables.
6. Seed support for a default local workspace and default categories.
7. API pagination, filtering, sorting, and consistent response envelopes.
8. Structured domain exceptions mapped to HTTP responses.
9. Database transaction helpers.
10. Unit tests for model constraints and repository behavior.

Define API conventions in docs/api-conventions.md:
- response shape
- error shape
- pagination
- filtering
- sorting
- timestamp format
- money representation
- concurrency behavior

Provide foundational endpoints:
- GET /api/v1/workspaces/current
- PATCH /api/v1/workspaces/current
- GET /api/v1/preferences
- PATCH /api/v1/preferences
- GET /api/v1/tags
- POST /api/v1/tags
- DELETE /api/v1/tags/{id}
- GET /api/v1/timeline
- GET /api/v1/meta/enums

Do not yet implement every CRUD endpoint for every entity. Those will be added in the next goals.

Data integrity requirements:
- Enforce valid transfer relationships.
- Enforce valid date ranges.
- Prevent self-dependencies.
- Prevent duplicate typed links where inappropriate.
- Prevent invalid currency codes.
- Prevent negative durations.
- Validate recurrence structures.
- Ensure deleting a link does not delete the linked domain record.
- Ensure scenario changes never mutate primary records during preview.

Testing requirements:
- Model validation tests.
- Alembic upgrade from empty database.
- Repository CRUD tests.
- Transaction rollback test.
- Concurrency/revision conflict test.
- Timeline pagination test.
- Money serialization test.
- Scenario isolation foundation test.

Acceptance criteria:
- A clean database can be created entirely through Alembic.
- All models can be imported without circular import failures.
- Foundation endpoints work.
- Tests pass against temporary SQLite databases.
- API schemas are visible in OpenAPI.
- The implementation remains fully local and deterministic.

At the end:
1. Run migrations and all relevant backend tests.
2. Run Ruff and type checks.
3. Document the schema in docs/data-model.md with a Mermaid entity relationship diagram.
4. Update docs/architecture.md.
5. Update docs/implementation-status.md.
6. Update docs/codex-development-log.md.
7. Report commands and results.
8. Stop after this goal.
```

---

## Prompt 3 — Tasks, projects, notes, and calendar backend

```text
/goal Implement production-quality backend APIs and domain services for tasks, projects, notes, attachments, and calendar events.

Continue in the existing LocalLife OS repository.

Read the product README and current architecture, data model, API conventions, tests, and migrations. Preserve existing behavior.

Implement these modules completely:

1. Projects
2. Tasks and subtasks
3. Task dependencies
4. Task recurrence
5. Notes
6. Note links and backlinks
7. Attachments
8. Calendar events
9. Calendar recurrence
10. Timeline event generation for meaningful changes

Required project capabilities:
- Create, read, update, archive, and list projects.
- Project status and target dates.
- Progress derived from linked tasks.
- Optional parent project only if it remains simple and well tested.

Required task capabilities:
- CRUD and list filtering.
- Parent/child subtasks.
- Dependency graph.
- Status transitions.
- Priority.
- Estimate and actual duration.
- Due date.
- Optional scheduled start/end.
- Recurrence rules.
- Tags.
- Project link.
- Commitment link support through the existing generic link model.
- Bulk complete and bulk reschedule operations.
- Prevention and detection of dependency cycles.
- Derived fields such as overdue, blocked, and schedulable.

Required notes capabilities:
- Markdown content.
- Title.
- Tags.
- Daily note date.
- Links to domain entities.
- Backlinks.
- Full-text search using an SQLite-compatible approach.
- Safe attachment upload and download.
- File size and filename validation.
- Path traversal prevention.
- Content metadata.
- Delete behavior documented and tested.

Required calendar capabilities:
- Timed and all-day events.
- Event categories.
- Location as plain local data.
- Preparation, travel, and recovery buffers.
- Recurrence rules.
- Conflict detection service.
- Query by date range.
- Move and resize operations.
- Calendar event links to projects, tasks, notes, goals, and commitments.
- Timeline integration.

Implement API routes under /api/v1:
- /projects
- /tasks
- /notes
- /attachments
- /calendar/events
- /calendar/conflicts

Use RESTful endpoints plus explicit action endpoints where an action is not cleanly represented by CRUD.

Create a reusable recurrence utility. Prefer a standards-based recurrence representation compatible with iCalendar RRULE semantics. Do not implement a fragile custom recurrence parser if a mature local library is appropriate.

Create service-level conflict detection that considers:
- event start/end
- all-day events
- preparation buffer
- travel buffer
- recovery buffer
- user timezone

Testing:
- CRUD tests.
- Task cycle detection.
- Task blocked-state calculation.
- Recurrence expansion.
- Calendar range query.
- Calendar conflict detection with buffers.
- Note search.
- Backlink creation and deletion.
- Safe attachment handling.
- Timeline event emission.
- API pagination and filters.
- Concurrency conflicts.

Do not implement frontend pages beyond any small changes needed to keep the build passing.

Acceptance criteria:
- All listed APIs are documented in OpenAPI.
- Complex logic lives in services, not route handlers.
- Date and timezone behavior is covered by tests.
- Attachments cannot escape the configured local storage directory.
- All backend quality checks pass.

At the end:
1. Run tests, linting, and type checking.
2. Update docs/api-conventions.md if new patterns were introduced.
3. Add docs/productivity-domain.md.
4. Update docs/implementation-status.md.
5. Update docs/codex-development-log.md.
6. Report exact verification results.
7. Stop after this goal.
```

---

## Prompt 4 — Personal finance, budgets, and goals backend

```text
/goal Implement the deterministic personal finance and goal-tracking backend for LocalLife OS.

Continue in the same repository and session.

Read all relevant existing code and documentation first. Do not redesign working foundations without a demonstrated need.

Implement:

1. Financial accounts
2. Transaction categories
3. Income, expense, and transfer transactions
4. Recurring transactions
5. Budgets
6. Category budget limits
7. Savings goals
8. General personal goals
9. Cash-flow projections
10. Planned transactions
11. Subscription metadata and price-change detection
12. Finance-related timeline events

Money rules:
- Persist amounts in integer minor units.
- Persist ISO 4217 currency codes.
- Never calculate persisted money with binary floating point.
- Clearly distinguish inflow, outflow, and transfer.
- Transfers must create balanced linked entries or an equivalently safe representation.
- Do not implement exchange-rate conversion or external market data in the MVP.
- Reports involving multiple currencies must group values by currency unless the user explicitly supplies a manual rate.

Required APIs under /api/v1:
- /finance/accounts
- /finance/categories
- /finance/transactions
- /finance/transfers
- /finance/recurring
- /finance/budgets
- /finance/savings-goals
- /goals
- /finance/reports/cash-flow
- /finance/reports/spending-by-category
- /finance/reports/committed-balance
- /finance/subscriptions

Required calculations:
- Account ledger balances.
- Monthly income and expenses.
- Spending by category.
- Budget consumption.
- Planned versus actual spending.
- Committed-but-not-yet-spent amount.
- Effectively available balance.
- Savings goal progress.
- Recurring transaction projection.
- Subscription amount changes.
- Projected monthly cash flow over a configurable horizon.
- Financial-buffer violation detection.

Use deterministic, explainable calculation services. Every report response should include:
- input date range
- currency
- assumptions
- included records
- excluded records where relevant
- calculation timestamp

Recurring transaction support:
- Generate future planned occurrences without duplicating existing generated occurrences.
- Make generation idempotent.
- Allow pausing and ending recurrence.
- Support monthly, weekly, yearly, and custom RRULE-compatible patterns when reasonable.

Validation:
- Transfers cannot use the same source and destination account.
- Transaction dates and planned dates must be valid.
- Budget category limits cannot exceed invalid values.
- Goal targets must be positive.
- Duplicate imports should be preventable through an import fingerprint field or equivalent foundation.

Testing:
- Ledger balance.
- Transfer balance.
- Recurring generation idempotency.
- Cash-flow projection.
- Budget consumption.
- Committed balance.
- Multi-currency grouping.
- Subscription price-change detection.
- Goal progress.
- Financial-buffer violations.
- API filters and pagination.
- Timeline event generation.

Do not add bank APIs, investment APIs, cloud sync, financial advice, or runtime AI.

Acceptance criteria:
- The finance API can support the demo dataset without manual database editing.
- Calculations are deterministic and tested.
- Results are explainable through response metadata.
- Backend tests and quality checks pass.

At the end:
1. Create docs/finance-engine.md.
2. Update docs/data-model.md.
3. Update docs/implementation-status.md.
4. Update docs/codex-development-log.md.
5. Run and report tests, linting, type checks, and migrations.
6. Stop after this goal.
```

---

## Prompt 5 — Commitment engine and unified timeline

```text
/goal Implement the LocalLife OS commitment engine that connects tasks, calendar events, notes, finance, and goals into one explainable impact model.

Continue in the existing repository.

Read README.md and all relevant domain documentation before implementation.

The commitment is the key differentiator of LocalLife OS. Treat this goal as core product work, not ordinary CRUD.

Implement commitment capabilities:

1. Create, update, archive, and list commitments.
2. Link and unlink:
   - tasks
   - projects
   - calendar events
   - notes
   - planned transactions
   - actual transactions
   - budgets
   - savings goals
   - general goals
3. Store:
   - title
   - description
   - status
   - category
   - target dates
   - optional decision deadline
   - optional financial buffer requirement
   - optional time-capacity requirement
4. Calculate:
   - planned cost
   - actual cost
   - expected income impact
   - required task duration
   - scheduled task duration
   - preparation/travel/recovery time
   - missing dependencies
   - blocked tasks
   - calendar conflicts
   - budget impact
   - savings-goal impact
   - financial-buffer violations
   - deadline risk
   - unscheduled required work
5. Produce an explainable commitment assessment.

Do not create a mysterious single AI-style score.

If a feasibility score is included:
- derive it from documented deterministic components
- return each component separately
- return warnings and assumptions
- make the formula configurable
- document limitations
- never hide a critical warning behind a high aggregate score

Suggested component outputs:
- time_capacity_status
- financial_capacity_status
- dependency_status
- schedule_conflict_status
- goal_impact_status
- overall_status
- warnings
- assumptions
- suggested deterministic actions

Suggested actions may include:
- schedule an unscheduled task
- reduce a planned expense
- move a conflicting event
- extend a target date
- pause another commitment
- split a task
- reserve money for a planned transaction

These suggestions must be rule-based and traceable to detected constraints.

Implement APIs:
- /api/v1/commitments
- /api/v1/commitments/{id}/links
- /api/v1/commitments/{id}/assessment
- /api/v1/commitments/{id}/impact
- /api/v1/commitments/{id}/warnings
- /api/v1/commitments/{id}/timeline
- /api/v1/commitments/{id}/refresh
- /api/v1/timeline/unified

Unified timeline requirements:
- Combine tasks, events, notes, transactions, goal milestones, and commitment changes.
- Support date filtering, entity filtering, and pagination.
- Avoid leaking note bodies or sensitive finance details in summary fields by default.
- Return typed items suitable for one frontend timeline component.

Assessment architecture:
- Separate collectors from evaluators.
- Use typed intermediate structures.
- Make each warning traceable to contributing entity IDs.
- Make recalculation idempotent.
- Prefer on-demand calculation plus explicit caching only if needed.
- Avoid duplicating source-of-truth values into the commitment record.

Testing:
- Empty commitment.
- Time-only commitment.
- Finance-only commitment.
- Full conference commitment.
- Conflict detection.
- Missing dependency detection.
- Budget violation.
- Savings-goal delay.
- Financial-buffer violation.
- Assessment component transparency.
- Link integrity.
- Unified timeline ordering.
- Refresh idempotency.
- Deletion and archive behavior.

Create a realistic synthetic fixture for:
- OpenAI Build Week project
- Berlin technology conference
- Laptop purchase

Acceptance criteria:
- The backend can generate a complete explainable assessment for all fixtures.
- Every warning references the records that caused it.
- No runtime model is used.
- Tests pass.

At the end:
1. Create docs/commitment-engine.md with formulas, assumptions, and examples.
2. Update docs/data-model.md.
3. Update docs/implementation-status.md.
4. Update docs/codex-development-log.md.
5. Run and report all verification commands.
6. Stop after this goal.
```

---

## Prompt 6 — Scheduling and personal capacity engine

```text
/goal Implement the OR-Tools scheduling engine and transparent personal time-capacity calculations for LocalLife OS.

Continue in the existing repository and inspect all current scheduling-related models and services before changing them.

Build a deterministic scheduling engine that can place eligible tasks into available local calendar windows.

Inputs:
- Task duration.
- Earliest start.
- Deadline.
- Priority.
- Dependencies.
- User working hours.
- User personal availability windows.
- Existing calendar events.
- Preparation, travel, and recovery buffers.
- Minimum focus-block duration.
- Preferred time-of-day.
- Maximum scheduled workload per day.
- Existing scheduled tasks.
- Commitment target date.
- User timezone.

Outputs:
- Suggested task placements.
- Unscheduled tasks.
- Reasons tasks could not be scheduled.
- Conflicts.
- Capacity by day and week.
- Deadline risk.
- Scheduling assumptions.
- Objective breakdown.

OR-Tools requirements:
- Use CP-SAT where appropriate.
- Keep optimization bounded with explicit time limits.
- Return the best known feasible result if optimality is not proven.
- Expose solver status.
- Keep the model understandable and documented.
- Do not silently discard tasks.
- Ensure dependency order.
- Prevent overlaps.
- Respect hard calendar constraints.
- Treat preferences as soft constraints where possible.
- Make the objective weights configurable and documented.

Capacity calculations:
- Raw free time.
- Eligible schedulable time.
- Focus-capable time.
- Already committed time.
- Remaining capacity.
- Overload by day and week.
- Required versus available commitment time.

APIs:
- POST /api/v1/scheduling/preview
- POST /api/v1/scheduling/apply
- GET /api/v1/scheduling/capacity
- GET /api/v1/scheduling/explanations/{preview_id}
- POST /api/v1/tasks/{id}/schedule-suggestions
- POST /api/v1/commitments/{id}/schedule-preview

Safety:
- Preview must not modify primary task or calendar records.
- Apply must use a transaction and optimistic concurrency checks.
- A stale preview must be rejected or explicitly revalidated.
- Applying a schedule must emit timeline events.
- Manual user scheduling always remains possible.

Create tests for:
- One task and one free window.
- Multiple tasks.
- Dependencies.
- Insufficient capacity.
- Hard event conflict.
- Soft preference conflict.
- Cross-midnight behavior.
- Daylight-saving transition.
- All-day events.
- Preparation/travel/recovery buffers.
- Solver timeout.
- Stale preview.
- Apply transaction rollback.
- Deterministic fixture behavior.

Add benchmark fixtures for up to:
- 100 tasks
- 200 calendar events
- 30-day planning horizon

The goal is reliable local performance, not massive enterprise scale.

Do not implement frontend scheduling screens yet beyond any API client types required to keep builds synchronized.

Acceptance criteria:
- The conference and hackathon demo commitments can be scheduled.
- Unschedulable tasks receive precise explanations.
- Preview and apply are safely separated.
- Tests and benchmark smoke checks pass.

At the end:
1. Create or update docs/scheduling-engine.md with variables, constraints, objective, limitations, and examples.
2. Update docs/commitment-engine.md where scheduling affects assessments.
3. Update implementation and Codex logs.
4. Run and report tests, linting, type checks, and benchmark smoke tests.
5. Stop after this goal.
```

---

## Prompt 7 — Scenario engine and decision comparison

```text
/goal Implement LocalLife OS scenario branching, deterministic projections, comparison, and explicit scenario acceptance.

Continue in the current repository and read the scenario-related foundation, commitment engine, scheduling engine, and finance engine before implementation.

A scenario is a temporary branch of the user's current life. It must not modify the primary workspace until explicitly accepted.

Implement:

1. Scenario creation from current workspace state.
2. Typed scenario changes for:
   - add/update/remove planned transaction
   - add/update/remove calendar event
   - add/update/remove task
   - change income
   - change recurring expense
   - change financial buffer
   - change commitment option
   - change task availability
   - change target date
   - pause another commitment
3. Scenario preview.
4. Scenario recalculation.
5. Scenario comparison.
6. Scenario acceptance.
7. Scenario discard.
8. Scenario export as a portable local JSON document with schema version.
9. Scenario timeline/audit history.

Architecture requirements:
- Use overlays or change sets.
- Avoid copying the entire production database.
- Never mutate primary entities during preview.
- Use deterministic projections.
- Reuse finance, commitment, and scheduling services rather than duplicating formulas.
- Version scenario assumptions.
- Include source revision information so stale scenarios can be detected.

Comparison dimensions:
- Projected cash flow.
- Lowest projected balance.
- Financial-buffer violation duration.
- Planned commitment cost.
- Time required.
- Available schedulable time.
- Number of schedule conflicts.
- Number of missing dependencies.
- Goal completion impact.
- Deadline risk.
- Unscheduled work.
- User-defined notes.

APIs:
- /api/v1/scenarios
- /api/v1/scenarios/{id}/changes
- /api/v1/scenarios/{id}/preview
- /api/v1/scenarios/{id}/recalculate
- /api/v1/scenarios/compare
- /api/v1/scenarios/{id}/accept
- /api/v1/scenarios/{id}/discard
- /api/v1/scenarios/{id}/export

Acceptance behavior:
- Show an exact change plan before applying.
- Validate optimistic revisions.
- Apply in one database transaction.
- Roll back everything on failure.
- Emit timeline events.
- Preserve the scenario as accepted history or archive it with the applied revision.

Create demo scenarios:
1. Attend conference physically.
2. Attend conference remotely.
3. Skip conference.
4. Buy laptop in August.
5. Delay laptop purchase until October.

Testing:
- Scenario isolation.
- Recalculation.
- Finance projection differences.
- Schedule differences.
- Commitment assessment differences.
- Stale source detection.
- Comparison ordering.
- Accept transaction.
- Rollback on partial failure.
- Export schema.
- Discard behavior.

Acceptance criteria:
- The demo scenarios produce materially different, explainable results.
- Primary data remains unchanged until acceptance.
- Accepted changes are auditable.
- Tests pass.

At the end:
1. Create docs/scenario-engine.md.
2. Update data-model and architecture documentation.
3. Update implementation and Codex logs.
4. Run and report all verification commands.
5. Stop after this goal.
```

---

## Prompt 8 — Frontend application shell and core modules

```text
/goal Build the complete desktop-first LocalLife OS frontend for tasks, projects, notes, calendar, finance, budgets, and goals using the existing backend APIs.

Continue in the same repository.

Read README.md and inspect all backend OpenAPI routes before implementing frontend behavior. Generate or maintain typed API clients from OpenAPI where practical. Do not duplicate backend domain logic in frontend components.

Use:
- Next.js
- TypeScript strict mode
- Tailwind CSS
- FullCalendar
- Recharts
- TanStack Query
- Zustand
- React Hook Form or another typed local form solution if already present and justified
- Local bundled assets only

Build a coherent application shell with:

Navigation:
- Today
- Tasks
- Calendar
- Notes
- Finance
- Goals
- Commitments
- Scenarios
- Timeline
- Settings

Global features:
- Command palette for local navigation and entity creation.
- Global search across notes, tasks, projects, commitments, and transactions using backend search APIs.
- Quick-create action.
- Consistent loading, empty, error, and offline states.
- Toast notifications.
- Keyboard navigation.
- Responsive desktop and tablet browser layout, but no smartphone-native application.
- Accessible focus states and semantic markup.

Today page:
- Today's events.
- Tasks due and overdue.
- Planned income and expenses.
- Active commitment warnings.
- Goal progress.
- Available capacity summary.
- Upcoming deadlines.
- Quick-create actions.

Tasks:
- List and board views.
- Filters.
- Project grouping.
- Subtasks.
- Dependencies.
- Recurrence.
- Duration estimates.
- Schedule fields.
- Bulk actions.
- Task detail drawer or page.

Calendar:
- Month, week, day, and agenda views.
- FullCalendar integration.
- Drag and resize with optimistic update and rollback.
- Preparation/travel/recovery buffers visible in detail.
- Conflict indicators.
- Task schedule suggestions.
- Accessible text alternative to calendar view.

Notes:
- Markdown editor.
- Note list.
- Search.
- Tags.
- Backlinks.
- Related entities.
- Daily note.
- Attachment upload and download.

Finance:
- Accounts.
- Transaction table.
- Income/expense entry forms.
- Transfer form.
- Category management.
- Budget view.
- Cash-flow chart.
- Spending-by-category chart.
- Committed balance display.
- Subscription price-change alerts.
- Savings goals.

Goals:
- General and savings goals.
- Progress.
- Target dates.
- Linked tasks, commitments, and transactions.

Engineering requirements:
- Central typed API layer.
- TanStack Query query-key factory.
- Mutation invalidation rules.
- Zustand only for local UI state, not duplicated server state.
- Route-level error boundaries.
- Skeleton loading states.
- No remote image/font/script requests.
- Charts must have textual summaries.
- Money formatting must respect currency codes and minor units.
- Dates must respect user timezone settings.
- Avoid giant components; build reusable feature modules.
- Add component tests for critical forms and views.

Do not yet build the full commitment and scenario visualization; those are the next goal. Navigation entries can exist.

Acceptance criteria:
- All core modules are usable end to end.
- The app does not require direct database manipulation.
- Frontend lint, type checking, unit tests, and production build pass.
- Core browser flows work against the local backend.
- No remote assets are loaded.

At the end:
1. Run frontend and backend checks.
2. Add docs/frontend-architecture.md.
3. Update implementation and Codex logs.
4. Report exact commands and results.
5. Stop after this goal.
```

---

## Prompt 9 — Commitment, scenario, graph, and visualization frontend

```text
/goal Build the signature LocalLife OS product experience for commitments, capacity, scenario comparison, and the unified timeline.

Continue in the current repository. Reuse existing frontend architecture and backend APIs.

This goal must make LocalLife OS feel like one connected product rather than separate productivity modules.

Commitment experience:
1. Commitment list with:
   - status
   - target date
   - planned cost
   - required time
   - warning count
   - component status indicators
2. Commitment creation wizard:
   - basic information
   - link existing tasks/events/notes/transactions/goals
   - create new linked records
   - define financial buffer
   - define target date
   - preview assessment
3. Commitment detail:
   - overview
   - time impact
   - financial impact
   - linked entities
   - dependencies
   - conflicts
   - warnings
   - assumptions
   - suggested deterministic actions
   - timeline
4. React Flow graph showing relationships among commitment entities.
5. Every warning must link to its contributing records.
6. Never hide critical information behind only an aggregate score.

Capacity experience:
- Daily and weekly time-capacity charts.
- Raw free time versus eligible focus time.
- Already committed versus remaining capacity.
- Financial capacity and committed balance.
- Transparent component summaries.
- Scheduling preview with proposed task placements.
- Apply schedule with explicit review.

Scenario experience:
1. Scenario list.
2. Create scenario from current workspace.
3. Edit typed changes.
4. Preview.
5. Compare two or three scenarios side by side.
6. Show:
   - projected cash flow
   - lowest balance
   - financial-buffer violations
   - time required
   - schedule conflicts
   - goal impact
   - unscheduled tasks
   - commitment status
7. Show differences with clear before/after visualizations.
8. Accept scenario only after showing an exact change plan.
9. Handle stale scenarios safely.

Unified timeline:
- One chronological view for tasks, events, notes, transactions, goals, and commitment changes.
- Filters by entity type and commitment.
- Compact summaries that do not reveal full sensitive content until opened.
- Infinite pagination or reliable incremental loading.
- Date grouping.

Demo-specific experience:
- Include polished views for:
  - OpenAI Build Week project
  - Berlin conference
  - Laptop purchase
- Make the physical versus remote conference comparison visually impressive.
- Show feasibility component changes without pretending to provide AI advice.

Design:
- Desktop-first.
- Calm, private, local-first identity.
- No excessive gradients or generic AI aesthetic.
- No references to an AI assistant in runtime UI.
- Use animation sparingly and support reduced motion.
- Strong empty states and sample-data hints.

Testing:
- Commitment creation.
- Link management.
- Warning navigation.
- Scheduling preview and apply.
- Scenario comparison.
- Stale scenario handling.
- Scenario acceptance.
- Timeline filtering.
- Accessibility smoke checks.
- Production build.

Acceptance criteria:
- A judge can understand the core product within 30 seconds.
- The conference scenario can be demonstrated without developer tools.
- All signature flows work locally.
- Tests and builds pass.

At the end:
1. Update docs/frontend-architecture.md.
2. Add docs/demo-flow.md with the exact demo clicks and expected results.
3. Update implementation and Codex logs.
4. Run and report all checks.
5. Stop after this goal.
```

---

## Prompt 10 — Calendar/finance imports and local automation

```text
/goal Implement safe local calendar import/export, bank CSV import, configurable mapping, duplicate detection, and deterministic automation rules.

Continue in the existing repository.

Implement calendar import/export:
- Import `.ics`.
- Preview before applying.
- Show new, changed, duplicate, and invalid events.
- Preserve timezone data.
- Support common recurrence rules.
- Export selected or all local events to `.ics`.
- Do not contact calendar providers.
- Make imports idempotent through source fingerprints or equivalent.
- Store import batch history.

Implement bank CSV import:
- Upload local CSV.
- Detect delimiter and encoding conservatively.
- Provide a mapping UI for:
  - date
  - description
  - amount
  - debit
  - credit
  - currency
  - account
  - category
  - external transaction ID
- Preview normalized rows.
- Show invalid rows.
- Detect probable duplicates.
- Let users include or exclude rows.
- Persist mapping profiles locally.
- Protect exported CSV and spreadsheet workflows from formula injection.
- Never upload data externally.
- Store import batch history and fingerprints.

Use Pandas for parsing and normalization where appropriate, but keep domain validation outside dataframe-only code.

Implement local automation:
- AutomationRule CRUD.
- Trigger types:
  - transaction created
  - subscription amount changed
  - event created
  - event approaching
  - task overdue
  - commitment warning created
  - recurring schedule
- Action types:
  - create task
  - create note
  - create planned transaction
  - add tag
  - create notification
  - request local backup reminder
- Rule conditions must be structured and deterministic.
- Do not execute arbitrary Python, JavaScript, shell, or user-provided code.
- Add a preview/test mode.
- Add execution logs.
- Make actions idempotent.
- Use APScheduler for recurring local jobs.
- Ensure scheduled jobs resume safely after application restart.

Add frontend screens:
- Imports center.
- Import history.
- CSV mapping.
- Calendar import preview.
- Automation rule builder.
- Rule test/preview.
- Execution history.

Create sample files:
- data/demo/calendar.ics
- data/demo/bank-transactions.csv
- at least one alternative bank CSV format
- demo automation rules

Testing:
- ICS import.
- Timezone preservation.
- Recurrence import.
- Duplicate prevention.
- CSV delimiter and mapping.
- Debit/credit normalization.
- Invalid row handling.
- Formula injection sanitization.
- Rule matching.
- Rule preview.
- Rule idempotency.
- APScheduler restart behavior.

Acceptance criteria:
- Demo data can be imported through the UI.
- Re-import does not duplicate records.
- No external request is made.
- Automation rules are safe and deterministic.
- Tests pass.

At the end:
1. Add docs/imports.md and docs/automation-rules.md.
2. Update implementation and Codex logs.
3. Run and report all checks.
4. Stop after this goal.
```

---

## Prompt 11 — Offline hardening, local privacy, backup/restore, and native launcher

```text
/goal Harden LocalLife OS as a fully on-device product with verified offline operation, secure local backup/restore, privacy controls, and simple native launch commands.

Continue in the current repository.

This goal must not introduce cloud dependencies or runtime AI.

Offline frontend:
1. Add a service worker and application-shell caching suitable for the chosen Next.js architecture.
2. Ensure all frontend assets are local.
3. Add an offline status indicator.
4. Ensure the application remains usable when public internet access is disabled, while the local backend is running.
5. Do not cache sensitive API responses in browser caches unless explicitly safe.
6. Document the service-worker strategy.

Network hardening:
- Backend defaults to 127.0.0.1.
- Strict CORS allowlist.
- Strict host validation where appropriate.
- Content Security Policy.
- No telemetry.
- No analytics.
- No error-reporting SaaS.
- No external fonts.
- No CDN scripts.
- Add an automated repository and runtime check for unexpected external URLs.
- Add an optional configuration guard that refuses outbound HTTP from application services unless explicitly enabled for development tests; default disabled.

Local privacy:
- Add local application lock/session timeout if feasible without compromising usability.
- Do not claim OS-grade credential security unless implemented.
- Redact sensitive values from logs.
- Ensure notes and transaction descriptions are not written to normal debug logs.
- Validate attachment paths.
- Add upload limits.
- Add secure temporary-file cleanup.
- Document data locations.

Backup:
- Create a versioned LocalLife OS backup container.
- Include:
  - database
  - attachments
  - preferences
  - schema version
  - checksums
  - manifest
- Support optional password-based authenticated encryption using mature libraries.
- Use Argon2id or another well-established password KDF and authenticated encryption.
- Do not design custom cryptographic primitives.
- Never log the backup password or derived key.
- Verify backup integrity before reporting success.

Restore:
- Inspect backup.
- Verify manifest and checksums.
- Show restore preview.
- Detect incompatible schema versions.
- Create an automatic safety backup before replacing current data.
- Restore transactionally where possible.
- Roll back on failure.
- Provide clear recovery instructions.

CLI/native launcher:
- Provide a supported local command or script interface:
  - locallife start
  - locallife stop
  - locallife status
  - locallife backup
  - locallife restore
  - locallife doctor
- A Python Typer launcher is acceptable.
- Include Windows PowerShell and Linux/macOS shell entry points.
- Open the browser automatically only when requested.
- Detect occupied ports.
- Show data directory and process status.
- Do not bind publicly.

Privacy UI:
- Settings page showing:
  - local data path
  - network mode
  - telemetry status: always off
  - backup status
  - last successful backup
  - session timeout
  - delete all local data workflow
- Require explicit confirmation for destructive deletion.

Verification scripts:
- scripts/verify-offline-mode.py
- scripts/check-external-assets.py
- scripts/backup-smoke-test.py
- scripts/restore-smoke-test.py

Threat model:
Create docs/threat-model.md covering:
- protected assets
- trust boundaries
- local attacker assumptions
- browser/backend boundary
- malicious import files
- path traversal
- CSV formula injection
- backup tampering
- database theft
- limitations
- non-goals

Testing:
- External URL scan.
- Loopback binding.
- Backup integrity.
- Wrong backup password.
- Tampered backup.
- Restore rollback.
- Attachment traversal.
- CSV malicious payload.
- Session expiration.
- No sensitive logging.
- Service-worker offline smoke test.
- Local launcher commands.

Acceptance criteria:
- Core workflows work with public network access disabled.
- Backup and restore are demonstrated end to end.
- The backend does not bind to 0.0.0.0 by default in native mode.
- No runtime API key is required.
- Security and privacy claims match actual implementation.
- Tests pass.

At the end:
1. Update docs/privacy.md.
2. Complete docs/threat-model.md.
3. Add docs/backup-format.md.
4. Update README setup and privacy sections.
5. Update implementation and Codex logs.
6. Run and report all verification commands.
7. Stop after this goal.
```

---

## Prompt 12 — Demo data, complete testing, performance, accessibility, and submission readiness

```text
/goal Make LocalLife OS judge-ready with deterministic demo data, full test coverage of critical workflows, accessibility checks, performance validation, documentation, and a reproducible three-minute demo.

Continue in the existing repository.

Do not add new broad product features. Focus on correctness, polish, testability, and submission quality.

Demo dataset:
Create a fully synthetic, deterministic workspace containing:
- A current calendar.
- Salary and recurring income.
- Normal household expenses.
- Subscriptions.
- Savings goals.
- Tasks and projects.
- Notes.
- OpenAI Build Week project commitment.
- Berlin conference commitment.
- Laptop purchase commitment.
- At least two schedule conflicts.
- At least one budget shortfall.
- Physical, remote, and skip conference scenarios.
- August and October laptop-purchase scenarios.
- Safe sample attachments.
- Automation rules.

Provide:
- scripts/load-demo-data.py
- scripts/reset-demo-data.py
- one-click demo mode or documented setup
- deterministic IDs or lookup labels where useful for E2E tests
- no real personal data
- no real credentials

End-to-end tests:
1. Start from an empty workspace.
2. Import calendar `.ics`.
3. Import bank CSV.
4. Create a task and project.
5. Create a note and backlink.
6. Create income and expense records.
7. Create a commitment.
8. Link records.
9. Generate assessment.
10. Detect conflict and budget impact.
11. Preview schedule.
12. Apply schedule.
13. Create scenarios.
14. Compare scenarios.
15. Accept a scenario.
16. Create encrypted backup.
17. Restore into a clean workspace.
18. Verify offline mode.

Testing layers:
- Backend unit tests.
- Backend API integration tests.
- Frontend component tests.
- Playwright E2E tests.
- Migration test from empty database.
- Backup/restore tests.
- Import security tests.
- Offline tests.
- Accessibility smoke tests.
- Performance smoke tests.

Accessibility:
- Keyboard navigation.
- Visible focus.
- Form labels.
- Error announcements.
- Dialog focus management.
- Reduced motion.
- Color-independent status indicators.
- Text summaries for charts.
- Accessible calendar alternative.
- Run an automated accessibility scanner where feasible.

Performance targets for demo hardware:
- Dashboard first meaningful content quickly on local machine.
- Common API responses under a reasonable local threshold.
- Scenario comparison responsive for demo dataset.
- Scheduling preview bounded and cancellable.
- Timeline pagination.
- No unnecessary frontend request waterfalls.
- Database indexes for common filters.
- Avoid loading all notes, transactions, or timeline records at once.

Developer experience:
- One command to run with Docker Compose.
- Clear native setup.
- Seed/reset scripts.
- Troubleshooting section.
- Judge test instructions.
- Supported platforms documented honestly.
- Architecture and data-flow diagrams.
- API docs link.
- Demo credentials: none.
- Demo data clearly identified as synthetic.

Codex/GPT-5.6 documentation:
Update docs/codex-development-log.md with:
- goals completed
- major architecture decisions
- where Codex accelerated development
- important human-reviewed decisions
- test and security work
- placeholder for the final /feedback session ID

Create docs/hackathon-submission.md containing:
- project title
- tagline
- category: Apps for Your Life
- concise project description
- detailed project description
- how it works
- why it is fully on-device
- how Codex and GPT-5.6 were used
- repository test instructions
- demo instructions
- supported platforms
- known limitations
- future roadmap

Create docs/demo-script.md:
- less than three minutes
- timestamped sections
- exact screen actions
- exact facts to narrate
- explicit explanation of Codex and GPT-5.6 usage
- offline proof
- final impact statement

README:
- Verify every command.
- Remove aspirational claims not implemented.
- Add screenshots placeholders if images are not yet available.
- Add current status and known limitations.
- Add license.
- Add judge quick-start.
- Add privacy summary.
- Add exact demo-data commands.

Final verification:
- Clean clone simulation where practical.
- docker compose up --build.
- Native backend and frontend startup.
- All migrations.
- All tests.
- Frontend production build.
- Offline verification.
- Backup/restore smoke test.
- External asset scan.
- Demo reset and load.
- No required API key.
- No unresolved critical TODOs in user-facing paths.
- No secrets in repository.
- No remote telemetry.

Do not hide failing checks. Fix failures within scope, and document any remaining limitations honestly.

At the end:
1. Present a concise final readiness report.
2. List all verification commands and results.
3. List remaining known limitations.
4. Update docs/implementation-status.md to reflect actual completion.
5. Update docs/codex-development-log.md.
6. Do not invent a /feedback session ID; leave a clear placeholder and explain how the user should obtain it from this Codex session.
7. Stop after this goal.
```

---

# Optional Prompt 13 — Final bug-fix and review pass

Use this only after manually testing the application.

```text
/goal Perform a final senior-engineering review of LocalLife OS, reproduce the issues I provide, fix them without expanding scope, and leave the repository in submission-ready condition.

Read README.md, docs/implementation-status.md, docs/hackathon-submission.md, and the current test results first.

The issues observed during manual testing are:

[PASTE YOUR ISSUE LIST HERE]

For each issue:
1. Reproduce it.
2. Identify the root cause.
3. Add or update a regression test.
4. Implement the smallest maintainable fix.
5. Run the relevant focused tests.
6. Run the complete affected test suite.
7. Record the fix in docs/codex-development-log.md.

Then perform a bounded final review for:
- broken navigation
- invalid empty states
- incorrect loading states
- inconsistent money formatting
- timezone errors
- stale TanStack Query caches
- scenario mutations leaking into primary data
- scheduling preview/apply inconsistencies
- unsafe file paths
- accidental external requests
- Docker startup failures
- README commands that do not work
- inaccessible dialogs or forms
- visible demo-data inconsistencies

Do not refactor stable areas merely for style.
Do not add new major features.
Do not introduce runtime AI, cloud services, telemetry, or external assets.
Do not invent passing results.

Acceptance criteria:
- Every reported issue is fixed or documented with a precise reason.
- Regression tests exist for fixed defects.
- Core demo flow passes.
- Docker and native judge instructions remain valid.
- Final documentation matches the real product.

At the end:
1. Run the final verification suite.
2. Report exact results.
3. Update implementation and Codex logs.
4. Produce a final remaining-risk list.
5. Stop.
```
