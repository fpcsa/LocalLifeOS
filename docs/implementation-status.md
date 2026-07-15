# Implementation status

Last updated: 2026-07-15

## Prompt 1 — Repository foundation

- [x] Monorepo directories for applications, packages, data, docs, scripts, and tests
- [x] FastAPI application under `/api/v1`
- [x] Health and system information endpoints
- [x] Structured errors and request ID middleware
- [x] Loopback-only CORS validation
- [x] Pydantic Settings with local storage path confinement
- [x] SQLModel, SQLite, Alembic, and initial `system_settings` migration
- [x] Startup migration, storage initialization, and timezone seed
- [x] Backend pytest, Ruff, and mypy configuration
- [x] Next.js, TypeScript strict mode, and Tailwind CSS application shell
- [x] Top bar, responsive navigation, Today placeholder, and API health status
- [x] TanStack Query, Zustand, and a dedicated API client
- [x] Local system fonts, neutral design tokens, dark scheme, and reduced-motion support
- [x] Frontend component tests, ESLint, type checking, and production build scripts
- [x] Shared TypeScript and reusable UI workspaces
- [x] Frontend and backend Dockerfiles
- [x] Docker Compose services, loopback port mappings, health checks, startup ordering, and persistent data volume
- [x] Native setup and verification commands
- [x] Cross-platform Compose start and stop scripts
- [x] Initial architecture and development documentation
- [x] Final Docker Compose build and live endpoint verification
- [x] Final repository-wide offline-asset scan and acceptance rerun

## Prompt 2 — Domain model, persistence, and API conventions

- [x] Core workspace, preferences, tags, attachments, and timeline models
- [x] Projects, tasks, dependencies, Markdown notes/links, and calendar event models
- [x] Accounts, typed transactions, categories, budgets/limits, and savings goal models
- [x] Commitments and typed entity links, goals, automation rules, and isolated scenario changes
- [x] UUIDs, UTC audit timestamps, soft deletion, and optimistic revisions
- [x] Explicit task/event recurrence and all-day/timed calendar constraints
- [x] Integer minor-unit money and ISO 4217 validation at API and persistence boundaries
- [x] Safe relative attachment metadata and normalized many-to-many link tables
- [x] Repository layer, service transaction boundaries, and structured domain exceptions
- [x] Default workspace, preferences, timezone setting, and category seed data
- [x] Alembic domain migration from a clean SQLite database
- [x] Consistent data/error envelopes, pagination, filtering, sorting, and enum metadata
- [x] Current workspace, preferences, tags, timeline, and enum endpoints
- [x] Atomic revision conflicts and link-target integrity services
- [x] Model, repository, rollback, concurrency, timeline, money, migration, and scenario tests
- [x] API conventions and Mermaid data-model documentation
- [x] Ruff and strict mypy verification

## Prompt 3 — Productivity and calendar backend

- [x] Project create/read/update/archive/list APIs with target dates and derived task progress
- [x] Task CRUD, filters, subtasks, status transitions, priority, estimates, actuals, and scheduling
- [x] Directed task dependencies with duplicate, self-link, and cycle prevention
- [x] Task tags, project and commitment links, bulk complete, and bulk reschedule actions
- [x] Derived overdue, blocked, and schedulable task fields and filters
- [x] Canonical iCalendar-compatible RRULE validation and bounded recurrence expansion
- [x] Markdown notes, unique daily notes, typed domain links, directed links, and backlinks
- [x] Workspace-scoped SQLite FTS5 note search with migration-managed synchronization triggers
- [x] Streaming attachment upload, SHA-256 metadata, confined download, filename/size validation,
  cleanup, and explicit deletion behavior
- [x] Timed/all-day calendar events, category, location, IANA timezone, and buffer fields
- [x] Calendar range query, recurrence, move, resize, typed links, and cancellation behavior
- [x] Timezone- and buffer-aware calendar conflict detection
- [x] Transactional timeline emission for meaningful productivity changes
- [x] Pagination, filters, optimistic concurrency, and complete OpenAPI registration
- [x] Alembic productivity migration and migration drift handling for SQLite FTS5 shadow tables
- [x] CRUD, cycles, blocked state, recurrence, note search/backlink, attachment, calendar,
  timeline, pagination, timezone, migration, and concurrency tests
- [x] Prompt 3 API conventions, productivity-domain, data-model, architecture, status, and log docs
- [x] Backend pytest, Ruff, strict mypy, and Alembic verification

## Prompt 4 — Finance and goal-tracking backend

- [x] Account and category CRUD with derived balances, running ledgers, and protected seed categories
- [x] Integer minor-unit actual transactions with ISO 4217 validation and import fingerprints
- [x] Atomic same-currency transfers with explicit source/destination effects
- [x] Separate planned transaction lifecycle with cancellation and atomic one-time fulfillment
- [x] Canonical RRULE recurring transactions with active/paused/ended lifecycle
- [x] Idempotent occurrence generation backed by stable unique occurrence keys
- [x] Weekly/monthly/quarterly/yearly/custom budgets and normalized expense-category limits
- [x] Actual/planned budget-consumption reports with basis-point calculations
- [x] Savings goals, contributions, derived progress, optional account links, and general goals
- [x] Subscription lifecycle, recurring billing representation, and immutable price-change history
- [x] Explainable cash-flow, spending-by-category, and committed-balance reports
- [x] Currency-separated multi-currency reporting with no implicit exchange-rate conversion
- [x] Committed-but-not-spent calculations and account financial-buffer warnings
- [x] Transactional timeline integration for meaningful finance and goal changes
- [x] Pagination, filters, optimistic concurrency, structured errors, and complete OpenAPI registration
- [x] Finance Alembic migration and metadata drift verification
- [x] Ledger, transfer, fingerprint, planned fulfillment, recurrence idempotency/lifecycle, budget,
  report, multi-currency, subscription, goal, timeline, migration, and concurrency tests
- [x] Finance engine, API conventions, data model, status, and development-log documentation
- [x] Backend pytest, Ruff, strict mypy, dependency, Alembic, and frontend regression verification

## Prompt 5 — Commitment engine and unified timeline

- [x] Commitment create/read/update/archive/delete/list APIs with category, targets, decision
  deadline, time-capacity requirement, and currency-specific financial buffer
- [x] Validated typed links for projects, tasks, calendar events, notes, planned and posted
  transactions, budgets, savings goals, and general goals
- [x] Duplicate, missing-target, cross-workspace, soft-delete, source-deletion, archive, and final
  deletion link integrity
- [x] Separate typed evidence collector, impact calculators, and deterministic rule evaluator
- [x] Derived planned/actual cost, expected income, ledger projection, and financial-buffer impact
- [x] Derived task duration, scheduled capacity, event buffers, unscheduled work, missing
  prerequisites, and blocked tasks
- [x] Reused timezone- and buffer-aware calendar conflict and finance budget-consumption services
- [x] Budget violation, savings-goal delay, deadline, missing-target, and conflict impact
- [x] Explainable component statuses, stable warning codes, assumptions, suggested actions, and
  contributing entity references with no feasibility score
- [x] Read-only assessment, impact, warning, refresh, and commitment timeline subresources
- [x] Idempotent on-demand refresh without cached writes, revision changes, or timeline noise
- [x] Workspace-wide unified timeline with date/type/entity filters, stable order, and pagination
- [x] Privacy-limited note and financial timeline summaries with explicit sensitive markers
- [x] Transactional commitment timeline events and cleanup integration across linked domains
- [x] Alembic migration for commitment fields, archive status, and expanded typed links
- [x] Synthetic OpenAI Build Week, Berlin technology conference, and Laptop purchase fixtures
- [x] Empty, time-only, finance-only, full, conflict, dependency, budget, savings, buffer,
  transparency, link, lifecycle, refresh, and unified-timeline tests
- [x] Commitment engine, API conventions, data model, architecture, status, and development-log docs
- [x] Backend pytest, Ruff, strict mypy, migration, OpenAPI, frontend, and offline regression checks

## Prompt 6 — Scheduling and personal capacity engine

- [x] Pinned local OR-Tools CP-SAT dependency in native and container requirements
- [x] Task earliest-start and soft preferred-time fields with API and enum metadata
- [x] Weekly working hours, explicit personal availability, focus minimum, and daily workload policy
- [x] Timezone-aware availability and real elapsed-minute handling across daylight-saving changes
- [x] Hard calendar, all-day, recurrence, buffer, and existing scheduled-task constraints
- [x] Finish-to-start and start-to-start dependency ordering inside and outside the selected task set
- [x] Task duration, earliest start, due date, commitment target deadline, and non-overlap constraints
- [x] Configurable transparent objective for task count, priority, preference, earlier starts, and fragmentation
- [x] Explicit optimal, feasible, infeasible, unknown, invalid, and not-run solver statuses
- [x] Non-mutating persisted previews with source snapshots, fingerprints, expiry, and explanations
- [x] Atomic revision-checked apply with stale-preview rejection and task timeline events
- [x] Daily, weekly, workspace, and commitment capacity reporting with documented formulas
- [x] Task suggestion, commitment preview, multi-task preview/apply, capacity, and explanation endpoints
- [x] Detailed unscheduled reasons, hard/soft conflicts, capacity gaps, and deadline-risk reporting
- [x] Conference and hackathon acceptance fixtures
- [x] Bounded 10/20, 50/100, and 100-task/200-event benchmark fixtures through a 30-day horizon
- [x] Dependency, priority, insufficient-capacity, buffers, all-day, soft preference, midnight, DST,
  staleness, timeout, rollback, route, commitment, and maximum-benchmark tests
- [x] Scheduling engine, commitment integration, API conventions, data model, architecture, status,
  and development-log documentation
- [x] Backend pytest, Ruff, strict mypy, dependency, migration, OpenAPI, frontend, offline, and
  Compose regression verification

## Prompt 8 — Frontend application shell and core modules

- [x] Generated OpenAPI TypeScript contracts and central typed domain API modules
- [x] Shared TanStack Query key factory and mutation invalidation conventions
- [x] Zustand restricted to shell, overlay, and toast UI state
- [x] Desktop-first shell with collapsible 240-pixel sidebar and compact responsive navigation
- [x] Command palette, five-domain backend search, quick create, offline banner, and toasts
- [x] Consistent skeleton, empty, error, retry, route-boundary, and local-service states
- [x] Today events, tasks, planned money, commitment warnings, goals, capacity, and deadlines
- [x] Task list/board filters, project grouping, subtasks, dependencies, recurrence, timing, bulk
  completion/rescheduling, detail, and schedule suggestions
- [x] FullCalendar month/week/day/agenda views, optimistic move/resize rollback, conflicts, buffers,
  accessible text list, and task suggestions
- [x] Searchable Markdown notes, tags, daily notes, links/backlinks, related records, and attachments
- [x] Finance accounts, transactions, transfers, categories, budgets, reports, committed balances,
  subscription price alerts, and savings goals
- [x] General and savings goal creation, progress, targets, accounts, and commitment-linked records
- [x] Unified timeline filters and revision-checked regional/theme settings
- [x] Scoped Commitment overview and explicit Scenario placeholder for deferred visualization work
- [x] Currency-specific minor-unit formatting and timezone/DST-aware date helpers
- [x] Recharts summaries with equivalent text tables/lists
- [x] Keyboard navigation, semantic controls, labelled dialogs/forms, focus states, dark theme, and
  reduced-motion support
- [x] Unit/component tests plus live Chrome route, mutation, search, calendar, viewport, runtime,
  overflow, and no-external-request smoke coverage
- [x] Frontend ESLint, strict TypeScript, Vitest, production build, backend regression, generated
  OpenAPI, and offline-source verification
- [x] Frontend architecture and development-log documentation

## Prompt 9 — Commitment, capacity, scenarios, and signature timeline

- [x] Commitment portfolio with status, target, planned cost, required time, warning count, and
  component states
- [x] Guided commitment creation with existing links, new linked records, financial buffer, target,
  and explainable assessment preview
- [x] Commitment detail with separate overview, time, finance, links, graph, and timeline views
- [x] Traceable warning contributors, dependencies, conflicts, assumptions, and deterministic actions
- [x] Accessible React Flow relationship graph backed by the same ordinary linked-record navigation
- [x] Daily and weekly raw, focus-eligible, committed, remaining, and financial capacity views with
  equivalent chart tables
- [x] Non-mutating scheduling preview and explicit reviewed apply flow
- [x] Isolated scenario list, typed editing, deterministic preview, and two- or three-way comparison
- [x] Cash-flow, lowest-balance, buffer, time, conflict, goal, unscheduled-task, and commitment metrics
- [x] Exact-plan scenario acceptance with source fingerprint, revision checks, atomic apply, and stale
  scenario rejection
- [x] Incremental date-grouped unified timeline with entity, commitment, privacy, and date filters
- [x] One-click Build Week, Berlin conference, Laptop purchase, and physical-versus-remote demo setup
- [x] Local-only generated API contracts and no runtime AI, remote asset, telemetry, or advisory flow
- [x] Commitment wizard and schedule-review component tests plus signature browser flows at desktop,
  tablet, and compact widths
- [x] Frontend architecture, API/data-model notes, exact demo flow, status, and development log
- [x] Backend, migration, OpenAPI, frontend quality, production build, offline, Compose, accessibility,
  and live Chrome verification

## Future product goals

- [x] Productivity user interfaces for tasks, projects, calendar, notes, and attachments
- [x] User interfaces for finance and goals
- [x] Unified timeline user interface
- [x] Full commitment planning and assessment visualizations
- [ ] Automation user interface
- [x] Scenario projections, comparison, and acceptance workflow
- [ ] `.ics` and CSV imports plus deterministic local automation
- [ ] Service worker, offline workflow verification, backup/restore, and security hardening
- [x] Build Week, Berlin conference, and Laptop purchase demo data plus signature-flow E2E coverage
- [ ] Broader repository-level E2E coverage and submission readiness

Encryption is deferred. No current checklist item should be interpreted as encrypted storage or encrypted backups.
