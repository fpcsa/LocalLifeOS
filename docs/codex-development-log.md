# Codex development log

## 2026-07-15 — Prompt 1: repository foundation

### Scope

Built the runnable LocalLife OS monorepo foundation only. No product-domain module, authentication provider, runtime AI, analytics, remote service, service worker, backup encryption, or cloud integration was added.

### Important decisions

- Preserved the user-authored root `README.md` as the product contract and limited edits to commands that differ from the implemented repository.
- Used npm workspaces for the web application, shared TypeScript contracts, and reusable UI package.
- Pinned dependency versions and committed the npm lockfile for repeatable native and container builds. A narrow PostCSS override removes a moderate advisory from Next.js's otherwise stale transitive copy.
- Made application startup apply Alembic migrations and seed the timezone setting, so native and Compose execution share one initialization path.
- Restricted backend storage to SQLite and confined attachment, backup, and import paths beneath the configured data directory.
- Enforced loopback-only browser API URLs and CORS origins. Compose publishes `3000` and `8000` only on `127.0.0.1`.
- Used UUIDs for the first persisted entity, UTC timestamps internally, and a separate IANA timezone value for presentation.
- Used only system fonts and local npm assets. Next.js telemetry is disabled in Compose and application scripts do not configure analytics.
- Chose a restrained neutral, border-based interface with accessible focus states, responsive navigation, health loading/error/retry states, dark mode, and reduced-motion behavior.
- Kept encryption explicitly deferred; it is not implemented or claimed by the foundation.
- Omitted source bind mounts from the default Compose file to favor deterministic judging on Windows, macOS, and Linux. Native Next.js and Uvicorn commands retain hot reload.

### Generated components

- FastAPI application factory, versioned routers, settings, middleware, structured errors, database initialization, and tests
- SQLModel `SystemSetting` entity and initial Alembic migration
- Next.js App Router shell, Today page, local API client, query provider, Zustand UI store, and component tests
- Shared TypeScript contracts and reusable brand-mark package
- Dockerfiles, Compose configuration, Makefile, cross-platform start/stop scripts, and architecture/status documentation

### Files created or materially changed

Root and runtime configuration:

- `.dockerignore`
- `.env.example`
- `.gitattributes`
- `.gitignore`
- `brand.md`
- `docker-compose.yml`
- `Makefile`
- `package.json`
- `package-lock.json`
- `README.md`

Backend:

- `apps/api/.dockerignore`
- `apps/api/Dockerfile`
- `apps/api/alembic.ini`
- `apps/api/alembic/env.py`
- `apps/api/alembic/script.py.mako`
- `apps/api/alembic/versions/20260715_0001_create_system_settings.py`
- `apps/api/app/__init__.py`
- `apps/api/app/api/__init__.py`
- `apps/api/app/api/v1/__init__.py`
- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/__init__.py`
- `apps/api/app/api/v1/routes/health.py`
- `apps/api/app/api/v1/routes/system.py`
- `apps/api/app/core/__init__.py`
- `apps/api/app/core/config.py`
- `apps/api/app/core/errors.py`
- `apps/api/app/core/middleware.py`
- `apps/api/app/db/__init__.py`
- `apps/api/app/db/session.py`
- `apps/api/app/main.py`
- `apps/api/app/models/__init__.py`
- `apps/api/app/models/system_setting.py`
- `apps/api/app/schemas/__init__.py`
- `apps/api/app/schemas/errors.py`
- `apps/api/app/schemas/system.py`
- `apps/api/pyproject.toml`
- `apps/api/requirements-dev.txt`
- `apps/api/requirements.txt`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_health.py`
- `apps/api/tests/test_system.py`

Frontend:

- `apps/web/.dockerignore`
- `apps/web/Dockerfile`
- `apps/web/app/globals.css`
- `apps/web/app/layout.tsx`
- `apps/web/app/page.tsx`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/providers.tsx`
- `apps/web/components/system-status.test.tsx`
- `apps/web/components/system-status.tsx`
- `apps/web/eslint.config.mjs`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/system.ts`
- `apps/web/next-env.d.ts`
- `apps/web/next.config.ts`
- `apps/web/package.json`
- `apps/web/postcss.config.cjs`
- `apps/web/stores/ui-store.ts`
- `apps/web/tailwind.config.ts`
- `apps/web/tests/setup.ts`
- `apps/web/tsconfig.json`
- `apps/web/vitest.config.ts`

Shared packages, data, scripts, tests, and documentation:

- `packages/shared-types/package.json`
- `packages/shared-types/src/index.ts`
- `packages/ui/package.json`
- `packages/ui/src/brand-mark.tsx`
- `packages/ui/src/index.ts`
- `data/attachments/.gitkeep`
- `data/backups/.gitkeep`
- `data/demo/.gitkeep`
- `data/imports/.gitkeep`
- `scripts/start-local.ps1`
- `scripts/start-local.sh`
- `scripts/stop-local.ps1`
- `scripts/stop-local.sh`
- `scripts/verify-offline-mode.py`
- `tests/e2e/.gitkeep`
- `tests/fixtures/.gitkeep`
- `tests/integration/.gitkeep`
- `docs/architecture.md`
- `docs/codex-development-log.md`
- `docs/implementation-status.md`

### Verification record

- Alembic initial migration: passed
- Backend pytest: 5 passed
- Ruff: passed
- mypy strict check: passed
- Frontend Vitest: 2 passed
- Frontend TypeScript strict check: passed
- Frontend production build: passed
- Frontend ESLint: passed after aligning the toolchain to ESLint 9
- npm advisory audit: 0 vulnerabilities after the PostCSS override
- Offline frontend source and loopback-port scan: passed
- PowerShell and POSIX script syntax: passed
- Docker Compose configuration: passed
- Docker image builds: passed; container `npm ci` reported 0 vulnerabilities
- Docker Compose runtime: API and web containers both healthy on `127.0.0.1`
- Live `GET /api/v1/health`: 200; request ID propagation confirmed
- Live `GET /api/v1/system/info`: 200; SQLite, UTC timezone, telemetry disabled, and external requests disabled confirmed
- Live web root: 200; LocalLife OS and Today shell content confirmed
- Containers stopped after verification; named data volume retained

## 2026-07-15 — Prompt 2: domain and persistence foundation

### Scope

Added the complete persistent domain foundation, repository/service boundaries, stable API
conventions, foundational endpoints, migration, seeds, and backend tests. Full CRUD surfaces and
product-domain user interfaces remain deferred.

### Important decisions

- Split models into core, productivity, finance, and connected-domain modules, with shared UUID,
  audit, revision, workspace, soft-delete, UTC datetime, and currency types.
- Used explicit SQL columns for task/calendar recurrence so rules remain queryable and validated;
  configured nullable JSON weekday fields to persist absent rules as SQL `NULL`.
- Represented money as integer minor units and an ISO 4217 code. Validation occurs in Pydantic
  request models and in a SQLAlchemy bind type, preventing invalid codes at service/model writes.
- Used an atomic `UPDATE ... WHERE revision = expected` for workspace, preference, and tag
  mutations. A zero-row update becomes a structured HTTP 409 revision conflict.
- Kept routes limited to HTTP concerns. Services own business rules and transactions; repositories
  own SQLModel queries, stable pagination, filtering, sorting, and soft deletion.
- Enabled SQLite foreign-key enforcement on every application connection and added check/unique
  constraints for date ranges, durations, transfer shape, recurrence shape, self-links, and typed
  link duplication.
- Modeled polymorphic tag, attachment, and commitment relations as typed link rows. The commitment
  service validates type, active target, and workspace; deleting a link cannot delete its target.
- Implemented scenarios as change overlays. Preview deep-copies primary data before applying an
  operation, so it cannot mutate primary objects or database records.
- Made startup seeding deterministic and idempotent for the default workspace, preferences,
  timezone setting, and initial income/expense categories.
- Kept attachments as metadata and relative POSIX paths confined beneath the configured local
  attachment directory. No content upload pipeline or encryption is claimed.

### Files created or materially changed

Backend model and migration foundation:

- `apps/api/alembic/versions/20260715_0002_create_domain_foundation.py`
- `apps/api/app/models/common.py`
- `apps/api/app/models/core.py`
- `apps/api/app/models/productivity.py`
- `apps/api/app/models/finance.py`
- `apps/api/app/models/connected.py`
- `apps/api/app/models/system_setting.py`
- `apps/api/app/models/__init__.py`
- `apps/api/app/core/config.py`
- `apps/api/app/db/session.py`
- `apps/api/app/db/transactions.py`

API, schemas, repositories, and services:

- `apps/api/app/api/dependencies.py`
- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/system.py`
- `apps/api/app/api/v1/routes/workspaces.py`
- `apps/api/app/api/v1/routes/tags.py`
- `apps/api/app/api/v1/routes/timeline.py`
- `apps/api/app/api/v1/routes/meta.py`
- `apps/api/app/core/exceptions.py`
- `apps/api/app/core/errors.py`
- `apps/api/app/main.py`
- `apps/api/app/schemas/common.py`
- `apps/api/app/schemas/domain.py`
- `apps/api/app/schemas/resources.py`
- `apps/api/app/schemas/__init__.py`
- `apps/api/app/repositories/base.py`
- `apps/api/app/repositories/workspace.py`
- `apps/api/app/repositories/tag.py`
- `apps/api/app/repositories/timeline.py`
- `apps/api/app/repositories/finance.py`
- `apps/api/app/repositories/scenario.py`
- `apps/api/app/repositories/__init__.py`
- `apps/api/app/services/workspace.py`
- `apps/api/app/services/tags.py`
- `apps/api/app/services/timeline.py`
- `apps/api/app/services/meta.py`
- `apps/api/app/services/finance.py`
- `apps/api/app/services/commitments.py`
- `apps/api/app/services/scenarios.py`
- `apps/api/app/services/seed.py`
- `apps/api/app/services/__init__.py`

Tests and documentation:

- `apps/api/tests/conftest.py`
- `apps/api/tests/test_api_foundation.py`
- `apps/api/tests/test_concurrency.py`
- `apps/api/tests/test_data_integrity.py`
- `apps/api/tests/test_migrations.py`
- `apps/api/tests/test_model_validation.py`
- `apps/api/tests/test_money.py`
- `apps/api/tests/test_repositories.py`
- `apps/api/tests/test_scenarios.py`
- `docs/api-conventions.md`
- `docs/data-model.md`
- `docs/architecture.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

- Alembic upgrade from an empty temporary SQLite database: passed at revision `20260715_0002`
- Alembic metadata drift check: passed with no new upgrade operations detected
- Backend pytest: 24 passed
- Ruff for application, tests, and migrations: passed
- mypy strict check: passed across 50 application source files
- Model import/metadata check: 26 SQLModel tables loaded without circular imports
- OpenAPI check: all foundational endpoints and response schemas present
- No external runtime service, telemetry, API key, remote database, or frontend dependency added

## 2026-07-15 — Prompt 3: productivity and calendar backend

### Scope

Implemented production backend workflows for projects, tasks/subtasks/dependencies/recurrence,
notes/links/backlinks/search, local attachments, calendar events/recurrence/conflicts, and timeline
integration. Frontend product pages, finance/goal APIs, automation execution, imports, and runtime
AI remain outside this goal.

### Important decisions

- Preserved the route → schema → service → repository → SQLModel layering. Route handlers only
  translate HTTP, while cycle detection, state transitions, recurrence, storage, and conflicts live
  in typed services.
- Added a shared revision-aware repository for atomic optimistic updates and soft deletion, then
  used it consistently across projects, tasks, notes, attachments, and calendar events.
- Standardized recurrence on canonical iCalendar-compatible RRULE values and pinned
  `python-dateutil` instead of maintaining a custom parser. The earlier typed recurrence form still
  works and is converted at the service boundary.
- Capped recurrence expansion at 1,000 items and required timezone-aware half-open ranges. All-day
  event boundaries use the event IANA timezone before conversion to UTC.
- Derived project progress and task overdue/blocked/schedulable state at read time so cached values
  cannot drift from linked tasks or dependency status.
- Treated dependency and parent graphs separately: both reject self-links and cycles, while
  dependency insertion evaluates the complete active workspace graph.
- Used SQLite FTS5 with Unicode tokenization and migration-managed triggers for active Markdown note
  search. FTS5 shadow tables are excluded from Alembic model-drift comparison, not from migrations.
- Streamed uploads to confined temporary files while calculating SHA-256 and enforcing the size
  limit. Client filenames are metadata only; generated UUID paths determine storage locations.
- Chose loss-averse attachment lifecycle semantics: deleting a linked domain record retains its
  attachment association and bytes, while explicit attachment deletion removes links and bytes.
- Defined conflict intervals as event time plus preparation/travel before and recovery after.
  Cancelled events remain queryable but are excluded from conflicts.
- Emitted timeline events inside the same transaction as each meaningful mutation, including
  explicit actions and relationship changes.
- Added only local Python dependencies (`python-dateutil`, `python-multipart`, `tzdata`, and typing
  stubs). No remote runtime request, API key, telemetry, CDN asset, or frontend feature was added.

### Files created or materially changed

Migration, models, configuration, and dependencies:

- `.env.example`
- `apps/api/alembic/env.py`
- `apps/api/alembic/versions/20260715_0003_productivity_backend.py`
- `apps/api/app/core/config.py`
- `apps/api/app/models/productivity.py`
- `apps/api/app/models/__init__.py`
- `apps/api/pyproject.toml`
- `apps/api/requirements.txt`
- `apps/api/requirements-dev.txt`

API, schemas, repositories, utilities, and services:

- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/projects.py`
- `apps/api/app/api/v1/routes/tasks.py`
- `apps/api/app/api/v1/routes/notes.py`
- `apps/api/app/api/v1/routes/attachments.py`
- `apps/api/app/api/v1/routes/calendar.py`
- `apps/api/app/schemas/common.py`
- `apps/api/app/schemas/domain.py`
- `apps/api/app/schemas/productivity.py`
- `apps/api/app/schemas/__init__.py`
- `apps/api/app/repositories/revisioned.py`
- `apps/api/app/repositories/projects.py`
- `apps/api/app/repositories/tasks.py`
- `apps/api/app/repositories/notes.py`
- `apps/api/app/repositories/attachments.py`
- `apps/api/app/repositories/calendar.py`
- `apps/api/app/repositories/__init__.py`
- `apps/api/app/services/domain_links.py`
- `apps/api/app/services/events.py`
- `apps/api/app/services/recurrence.py`
- `apps/api/app/services/projects.py`
- `apps/api/app/services/tasks.py`
- `apps/api/app/services/notes.py`
- `apps/api/app/services/attachments.py`
- `apps/api/app/services/calendar.py`
- `apps/api/app/utils/__init__.py`
- `apps/api/app/utils/recurrence.py`

Tests and documentation:

- `apps/api/tests/test_migrations.py`
- `apps/api/tests/test_productivity_api.py`
- `apps/api/tests/test_notes_attachments_api.py`
- `apps/api/tests/test_calendar_api.py`
- `apps/api/tests/test_recurrence.py`
- `docs/api-conventions.md`
- `docs/productivity-domain.md`
- `docs/data-model.md`
- `docs/architecture.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

Commands run from `apps/api` unless marked as repository root:

```text
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app alembic tests
.\.venv\Scripts\python.exe -m ruff format --check app alembic tests
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
npm run lint:web                                      # repository root
npm run typecheck:web                                 # repository root
npm run test:web                                      # repository root
npm run build:web                                     # repository root
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py  # repository root
docker compose config --quiet                         # repository root
```

- Alembic upgrade from an empty temporary SQLite database: passed at revision `20260715_0003`
- Alembic metadata drift check: passed with no new upgrade operations detected
- Backend pytest: 36 passed
- Ruff for application, tests, and migrations: passed
- mypy strict check: passed across 72 application source files
- OpenAPI generation: 31 paths; all requested Prompt 3 route groups present
- Python dependency consistency (`pip check`): passed
- Frontend ESLint and strict TypeScript check: passed
- Frontend Vitest: 2 passed
- Frontend production build: passed; 3 static pages generated
- Repository offline-runtime scan: passed with no remote frontend assets or non-loopback ports
- Docker Compose configuration parse: passed (Docker emitted a host config permission warning)
- No external runtime service, telemetry, API key, remote database, or frontend asset added

## 2026-07-15 — Prompt 4: finance and goal-tracking backend

### Scope

Implemented local deterministic finance workflows for accounts, categories, posted transactions,
transfers, plans, recurring rules, budgets, savings and general goals, subscriptions, projections,
reports, and timeline integration. Finance user interfaces, bank connections, exchange-rate
downloads, investment pricing, automation execution, and scenario acceptance remain outside this
goal.

### Important decisions

- Kept account balances derived from opening balance plus posted ledger effects. Planned money
  never mutates a ledger, avoiding cached-total drift.
- Represented a transfer as one atomic row with negative source and positive destination effects.
  Both accounts must be distinct and share the validated ISO currency; reports treat the record as
  cash-flow neutral.
- Kept all money in integer minor units. Multi-currency reports group by currency and explicitly do
  not perform or imply exchange-rate conversion.
- Separated posted and planned transactions. Plan fulfillment creates exactly one posted record and
  closes the plan in one transaction; fulfilled plans and their actual records are retained for
  auditability.
- Added workspace-scoped import fingerprints for deterministic duplicate rejection.
- Reused the bounded `python-dateutil` RRULE utility. Generated plans carry a stable rule ID plus UTC
  occurrence key, with a database uniqueness constraint and idempotent repeated generation.
- Made subscriptions authoritative for linked recurrence amount and billing schedule. Reports count
  the subscription once, linked rule generation reads current subscription data, and price changes
  synchronize the rule representation while appending immutable history.
- Derived budget consumption, savings progress, monthly cash flow, category spending, committed
  amounts, effectively available balances, and financial-buffer warnings instead of persisting
  mutable report totals.
- Included calculation inputs, assumptions, included/excluded source records, and timestamps in
  report metadata. Workspace timezone controls date boundaries and monthly grouping.
- Emitted finance and goal timeline events within the same transaction as their source mutation.
  Existing domain entity types are reused, with the specific finance resource named by action and
  payload, avoiding a compatibility-breaking enum expansion.
- Added a persistence-level non-negative financial-buffer constraint in addition to API validation.
- Added no remote service, API key, telemetry, external request, floating-point money, or frontend
  feature.

### Files created or materially changed

Migrations and models:

- `apps/api/alembic/versions/20260715_0004_finance_engine.py`
- `apps/api/alembic/versions/20260715_0005_finance_safeguards.py`
- `apps/api/app/models/common.py`
- `apps/api/app/models/finance.py`
- `apps/api/app/models/__init__.py`

API, schemas, repositories, and services:

- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/finance_accounts.py`
- `apps/api/app/api/v1/routes/finance_transactions.py`
- `apps/api/app/api/v1/routes/finance_planning.py`
- `apps/api/app/api/v1/routes/finance_budgets.py`
- `apps/api/app/api/v1/routes/finance_subscriptions.py`
- `apps/api/app/api/v1/routes/finance_reports.py`
- `apps/api/app/api/v1/routes/goals.py`
- `apps/api/app/schemas/finance.py`
- `apps/api/app/repositories/finance_engine.py`
- `apps/api/app/services/finance_accounts.py`
- `apps/api/app/services/finance_categories.py`
- `apps/api/app/services/finance_transactions.py`
- `apps/api/app/services/finance_recurring.py`
- `apps/api/app/services/finance_budgets.py`
- `apps/api/app/services/finance_calculations.py`
- `apps/api/app/services/finance_validation.py`
- `apps/api/app/services/finance_reports.py`
- `apps/api/app/services/goals.py`
- `apps/api/app/services/subscriptions.py`
- `apps/api/app/services/meta.py`

Tests and documentation:

- `apps/api/tests/test_finance_api.py`
- `apps/api/tests/test_finance_planning_reports.py`
- `apps/api/tests/test_migrations.py`
- `docs/api-conventions.md`
- `docs/data-model.md`
- `docs/finance-engine.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

Commands run from `apps/api` unless marked as repository root:

```text
.\.venv\Scripts\ruff.exe format --check app tests alembic
.\.venv\Scripts\ruff.exe check app tests alembic
.\.venv\Scripts\mypy.exe app
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe check
.\.venv\Scripts\python.exe -c "...OpenAPI finance path assertions..."
npm run lint:web                                      # repository root
npm run typecheck:web                                 # repository root
npm run test:web                                      # repository root
npm run build:web                                     # repository root
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py  # repository root
docker compose config --quiet                         # repository root
```

- Backend pytest: 42 passed
- Ruff format check and lint across 114 application/test/migration files: passed
- Strict mypy: passed across 91 application source files
- Python dependency consistency: passed
- Alembic upgraded to `20260715_0005`; empty-database migration test and metadata drift check passed
- OpenAPI generation: 62 paths; every required finance and goal route group present
- Frontend ESLint and strict TypeScript check: passed
- Frontend Vitest: 2 passed
- Frontend production build: passed; 3 static pages generated
- Offline source verification: passed with no remote frontend assets or non-loopback ports
- Docker Compose configuration parse: passed; Docker emitted only a host config permission warning

## 2026-07-15 — Prompt 5: commitment engine and unified timeline

### Scope

Implemented the local commitment lifecycle, polymorphic links across productivity and finance,
deterministic impact assessment, traceable warnings and suggested actions, idempotent refresh, and a
privacy-limited unified timeline. Commitment and timeline frontend pages, notification scheduling,
probabilistic forecasting, automation execution, and runtime AI remain outside this goal.

### Important decisions

- Kept assessments derived from source records rather than persisting mutable score or warning
  snapshots. The commitment revision changes only when user-owned commitment fields change.
- Split the engine into a typed evidence collector, impact calculators, and a rule evaluator. The
  collector reuses calendar conflict and finance budget services; the evaluator performs no
  persistence queries.
- Used explicit `not_applicable`, `ok`, `warning`, and `critical` components. Overall status is the
  worst applicable component, not an opaque numeric feasibility score.
- Required every warning and suggested action to carry contributing entity IDs. Stable warning
  codes and explicit assumptions make results inspectable by clients and tests.
- Kept money in integer minor units grouped by ISO currency without conversion. Posted costs are
  reported but not subtracted twice because the ledger already contains their effects.
- Calculated effective time from linked task estimates and event buffers, with the greater manual
  capacity requirement taking precedence. Missing linked prerequisites remain distinct from tasks
  blocked by unfinished prerequisites.
- Included conflicts where either event is linked, allowing the engine to explain competition from
  an otherwise unrelated calendar appointment. Existing all-day, timezone, and buffer rules remain
  authoritative.
- Treated linked budget and savings impacts conservatively and deterministically: budget warnings
  require linked spending to contribute to a negative remainder; same-currency planned outflow can
  increase a linked savings goal's remaining amount.
- Made archive an immutable audit state: archived records are omitted by default and reject direct
  field/link changes while retaining current links. Final deletion removes link rows.
- Implemented refresh as a write-free recalculation. It creates no cached record, revision bump, or
  timeline event, so unchanged repeated calls differ only by calculation timestamp.
- Built the unified timeline from typed current-domain summaries plus commitment change events.
  Note bodies are excluded; financial items expose no amount, account, category, payee, or note and
  carry an explicit `sensitive` marker.
- Added no external service, API key, telemetry, remote request, runtime AI, floating-point money,
  or frontend product feature.

### Files created or materially changed

Migration and models:

- `apps/api/alembic/versions/20260715_0006_commitment_engine.py`
- `apps/api/app/models/common.py`
- `apps/api/app/models/connected.py`

API, schemas, repositories, and services:

- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/commitments.py`
- `apps/api/app/api/v1/routes/timeline.py`
- `apps/api/app/schemas/commitments.py`
- `apps/api/app/repositories/__init__.py`
- `apps/api/app/repositories/commitments.py`
- `apps/api/app/services/commitments.py`
- `apps/api/app/services/commitment_management.py`
- `apps/api/app/services/commitment_collectors.py`
- `apps/api/app/services/commitment_evaluators.py`
- `apps/api/app/services/commitment_engine.py`
- `apps/api/app/services/unified_timeline.py`
- `apps/api/app/services/domain_links.py`
- `apps/api/app/services/finance_budgets.py`
- `apps/api/app/services/finance_transactions.py`
- `apps/api/app/services/goals.py`

Tests, fixtures, and documentation:

- `apps/api/tests/fixtures/commitment_scenarios.json`
- `apps/api/tests/test_commitments_api.py`
- `apps/api/tests/test_commitment_scenarios.py`
- `apps/api/tests/test_data_integrity.py`
- `apps/api/tests/test_migrations.py`
- `docs/commitment-engine.md`
- `docs/api-conventions.md`
- `docs/data-model.md`
- `docs/architecture.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

Commands run from `apps/api` unless marked as repository root:

```text
.\.venv\Scripts\ruff.exe format --check app tests alembic
.\.venv\Scripts\ruff.exe check app tests alembic
.\.venv\Scripts\mypy.exe app
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe check
.\.venv\Scripts\python.exe -c "...OpenAPI commitment path assertions..."
npm run lint:web                                      # repository root
npm run typecheck:web                                 # repository root
npm run test:web                                      # repository root
npm run build:web                                     # repository root
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py  # repository root
docker compose config --quiet                         # repository root
```

- Backend pytest: 48 passed
- Ruff format check and lint across 125 application, test, and migration files: passed
- Strict mypy: passed across 99 application source files
- Python dependency consistency (`pip check`): passed
- Alembic migration from an empty database, local upgrade/current, and metadata drift check: passed
  at `20260715_0006`
- OpenAPI generation: 73 paths; all commitment, assessment, link, refresh, and unified-timeline
  routes present
- Frontend ESLint and strict TypeScript: passed
- Frontend Vitest: 2 passed
- Frontend production build: passed; all three generated static entries completed
- Offline source verification: passed with no remote frontend assets or non-loopback ports
- Docker Compose configuration parse: passed; Docker emitted only host config permission warnings

## 2026-07-15 — Prompt 6: scheduling and personal capacity engine

### Scope

Implemented a fully local OR-Tools CP-SAT planning engine for tasks and commitment-linked work,
including timezone-aware availability, current calendar/task constraints, dependency order,
capacity reports, persisted non-mutating previews, structured explanations, and atomic schedule
acceptance. Background rescheduling, task splitting, predictive estimates, runtime AI, and product
frontend pages remain outside this goal.

### Important decisions

- Pinned `ortools==9.15.6755` in both Python dependency manifests and verified its CP-SAT import in
  the Python 3.12 API image.
- Modeled one optional fixed-duration interval per task over integer UTC minutes. Proposed tasks do
  not overlap and are not split; current scheduled tasks, recurring/all-day calendar occurrences,
  and preparation/travel/recovery buffers are removed from eligible free time.
- Built weekly working hours in local wall time and unioned them with explicit absolute personal
  availability. Overnight windows are supported. Local day boundaries are converted through the
  workspace IANA timezone, so daylight-saving days use real elapsed minutes.
- Enforced earliest start, task/commitment deadlines, finish-to-start and start-to-start dependency
  order, eligible free windows, and daily workload headroom as hard constraints. Time-of-day bands
  remain soft and produce explicit conflicts when violated.
- Used a configurable weighted objective with visible components for scheduled-task count, priority,
  preferred time, earlier starts, and free-window fragmentation. The solver uses one worker, seed
  zero, and a per-request wall-time limit. Feasible timeout results never claim optimality.
- Bounded previews to 100 unique tasks and 30 days. The maximum fixture adds 200 event constraints,
  sets a one-second solver limit, and verifies that all requested tasks are still accounted for.
- Kept preview and apply separate. Preview persists request/result JSON and a canonical SHA-256
  fingerprint but never updates a task or event. Apply recollects sources, rejects stale/expired or
  repeated previews, revision-checks each task, and commits all intervals, timeline events, and the
  applied marker in one transaction.
- Calculated raw, eligible, focus-capable, committed, suggested, remaining, and overloaded capacity
  per local day and week. A cross-midnight placement is charged to its local start day; this policy
  is returned as an explicit assumption.
- Returned every requested task as a placement or an unscheduled item with stable reason codes,
  entity references, capacity details, deadline risk, conflicts, objective components, and solver
  status. No advice is silently dropped.
- Added no telemetry, API key, remote database, remote asset, external runtime request, automatic
  calendar mutation, or frontend product feature.

### Files created or materially changed

Dependencies, configuration, migration, and models:

- `.env.example`
- `apps/api/pyproject.toml`
- `apps/api/requirements.txt`
- `apps/api/alembic/versions/20260715_0007_scheduling_engine.py`
- `apps/api/app/core/config.py`
- `apps/api/app/models/common.py`
- `apps/api/app/models/productivity.py`
- `apps/api/app/models/scheduling.py`
- `apps/api/app/models/__init__.py`

API, schemas, repositories, and services:

- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/scheduling.py`
- `apps/api/app/api/v1/routes/tasks.py`
- `apps/api/app/api/v1/routes/commitments.py`
- `apps/api/app/schemas/scheduling.py`
- `apps/api/app/schemas/productivity.py`
- `apps/api/app/repositories/scheduling.py`
- `apps/api/app/repositories/__init__.py`
- `apps/api/app/services/scheduling.py`
- `apps/api/app/services/scheduling_capacity.py`
- `apps/api/app/services/scheduling_collectors.py`
- `apps/api/app/services/scheduling_intervals.py`
- `apps/api/app/services/scheduling_solver.py`
- `apps/api/app/services/scheduling_types.py`
- `apps/api/app/services/calendar.py`
- `apps/api/app/services/tasks.py`
- `apps/api/app/services/meta.py`

Tests, fixtures, and documentation:

- `apps/api/tests/fixtures/scheduling_scenarios.json`
- `apps/api/tests/fixtures/scheduling_benchmarks.json`
- `apps/api/tests/test_scheduling_api.py`
- `apps/api/tests/test_scheduling_benchmark.py`
- `apps/api/tests/test_migrations.py`
- `docs/scheduling-engine.md`
- `docs/commitment-engine.md`
- `docs/api-conventions.md`
- `docs/data-model.md`
- `docs/architecture.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

Commands run from `apps/api` unless marked as repository root:

```text
.\.venv\Scripts\ruff.exe format --check app tests alembic
.\.venv\Scripts\ruff.exe check app tests alembic
.\.venv\Scripts\mypy.exe app
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\pytest.exe tests\test_scheduling_api.py -q
.\.venv\Scripts\pytest.exe tests\test_scheduling_benchmark.py -q
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe check
.\.venv\Scripts\python.exe -c "...OpenAPI scheduling assertions..."
npm run lint:web                                      # repository root
npm run typecheck:web                                 # repository root
npm run test:web                                      # repository root
npm run build:web                                     # repository root
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py  # repository root
docker compose config --quiet                         # repository root
docker compose build api                              # repository root
docker run --rm locallife-os-api python -c "...CP-SAT import..."  # repository root
docker compose up -d --wait --wait-timeout 60 api     # repository root
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health # repository root
Invoke-RestMethod http://127.0.0.1:8000/openapi.json  # repository root
docker compose stop api                               # repository root
```

- Backend pytest: 59 passed
- Scheduling API scenarios: 10 passed; maximum scheduling benchmark: 1 passed
- Ruff format check and lint across 138 application, test, and migration files: passed
- Strict mypy: passed across 109 application source files
- Python dependency consistency: passed
- Alembic empty-database migration test, local upgrade/current, and metadata drift check: passed at
  `20260715_0007`
- OpenAPI generation: 79 paths; all scheduling, task-suggestion, commitment-preview, capacity, apply,
  and explanation routes and task constraint fields present
- Frontend ESLint and strict TypeScript: passed
- Frontend Vitest: 2 passed
- Frontend production build: passed; all three generated static entries completed
- Offline source verification: passed with no remote frontend assets or non-loopback ports
- Docker Compose configuration: parsed successfully; only host Docker-config permission warnings
- API image: built successfully with OR-Tools 9.15.6755; CP-SAT import passed
- Compose API runtime: became healthy, returned `status=ok`, and exposed scheduling in OpenAPI; the
  temporary container was stopped after verification

## 2026-07-15 — Prompt 8: frontend application shell and core modules

### Scope

Implemented the complete desktop-first frontend over the existing local APIs: shared shell and
overlays, Today, tasks/projects, calendar, notes, finance/budgets, goals, unified timeline, settings,
and intentionally scoped Commitment and Scenario destinations. No backend domain rule was copied
into a component, and no remote runtime asset or service was introduced.

### Important decisions

- Exported FastAPI OpenAPI locally and generated TypeScript contracts with `openapi-typescript`.
  Frontend aliases and domain API modules now compile against all 79 paths and 223 schemas.
- Centralized query identity in one key factory. TanStack Query owns server state; Zustand owns only
  the sidebar, overlays, quick-create selection, and transient toasts.
- Kept the API base URL loopback-only and verified all browser requests. The UI loads no remote
  font, image, script, analytics, telemetry, or runtime data source.
- Used React Hook Form for typed forms and backend revisions for concurrent writes. Form help and
  errors are connected to controls; native dialogs supply focus containment and Escape behavior.
- Applied FullCalendar's drag/resize interactions with cache snapshots, optimistic changes, backend
  revision checks, explicit rollback, conflict invalidation, and user-facing error toasts.
- Kept calendar and chart information available as semantic text. Finance charts have tables/lists,
  and the calendar has a range-matched event list.
- Preserved integer minor-unit money through API boundaries and used currency-specific `Intl`
  digits only at entry/formatting boundaries. Multi-currency summaries remain separated.
- Derived local-day query ranges through the saved IANA timezone and tested the Europe/Rome
  daylight-saving transition as a 23-hour day.
- Added a preference-driven semantic light/dark theme and retained reduced-motion behavior. The
  frontend design checklist was inspected at 1280, 768, and 375 pixels in local Chrome.
- Kept full Commitment and Scenario visualizations deferred as required. Their routes state the
  scope honestly rather than inventing unsupported APIs or domain behavior.

### Files created or materially changed

Contracts, dependencies, and verification:

- `package.json`
- `package-lock.json`
- `apps/web/package.json`
- `scripts/export-openapi.py`
- `packages/shared-types/src/index.ts`
- `packages/shared-types/src/openapi.json`
- `packages/shared-types/src/openapi.ts`
- `tests/e2e/frontend-smoke.mjs`

Shared application infrastructure:

- `apps/web/app/layout.tsx`
- `apps/web/app/globals.css`
- `apps/web/app/icon.svg`
- `apps/web/app/loading.tsx`
- `apps/web/app/error.tsx`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/providers.tsx`
- `apps/web/components/command-palette.tsx`
- `apps/web/components/quick-create.tsx`
- `apps/web/components/offline-banner.tsx`
- `apps/web/components/theme-sync.tsx`
- `apps/web/components/toast-viewport.tsx`
- `apps/web/components/ui/`
- `apps/web/stores/ui-store.ts`
- `apps/web/lib/api/`
- `apps/web/lib/cn.ts`
- `apps/web/lib/date-range.ts`
- `apps/web/lib/format.ts`
- `apps/web/lib/scheduling-defaults.ts`

Routes and features:

- `apps/web/app/page.tsx`
- `apps/web/app/tasks/`
- `apps/web/app/calendar/`
- `apps/web/app/notes/`
- `apps/web/app/finance/`
- `apps/web/app/goals/`
- `apps/web/app/commitments/`
- `apps/web/app/scenarios/`
- `apps/web/app/timeline/`
- `apps/web/app/settings/`
- `apps/web/features/today/`
- `apps/web/features/tasks/`
- `apps/web/features/calendar/`
- `apps/web/features/notes/`
- `apps/web/features/finance/`
- `apps/web/features/goals/`
- `apps/web/features/commitments/`
- `apps/web/features/timeline/`
- `apps/web/features/settings/`

Tests and documentation:

- `apps/web/components/system-status.test.tsx`
- `apps/web/features/tasks/task-form.test.tsx`
- `apps/web/lib/date-range.test.ts`
- `apps/web/lib/format.test.ts`
- `apps/web/tests/setup.ts`
- `docs/frontend-architecture.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

Commands run from the repository root unless a working directory is noted:

```text
npm install
.\apps\api\.venv\Scripts\python.exe scripts\export-openapi.py
npm run generate:api-types
npm run test:web
npm run lint:web
npm run typecheck:web
npm run build:web
npm run test:e2e:web
docker compose config --quiet
.\.venv\Scripts\python.exe -m pytest                         # working directory: apps/api
.\.venv\Scripts\python.exe -m ruff check .                    # working directory: apps/api
.\.venv\Scripts\python.exe -m mypy app                        # working directory: apps/api
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py
```

- Dependency install: completed with zero reported vulnerabilities.
- OpenAPI export/generation: 79 paths and 223 schemas; generated TypeScript refreshed.
- Frontend Vitest: 4 files, 8 tests passed.
- Frontend ESLint: passed with zero warnings.
- Frontend strict TypeScript: passed.
- Frontend production build: passed; 13 static entries including all 10 product routes and the
  local application icon were generated.
- Live Chrome E2E: all 10 routes passed at desktop, tablet, and compact widths (30 route checks);
  task creation and bulk rescheduling, note and account creation, command navigation/search,
  calendar agenda, and calendar text
  alternative passed. No external request, runtime console error, route-boundary failure, or
  document-level horizontal overflow was detected.
- Visual inspection: Today screenshots at 1280, 768, and 375 pixels passed the design checklist.
- Backend pytest: 59 passed with 48 known Alembic SQLite warnings.
- Backend Ruff: passed; strict mypy: passed across 109 source files.
- Offline source verifier: passed with no remote frontend assets or non-loopback ports.
- Docker Compose configuration: parsed successfully.
- Temporary browser database, attachments, logs, and screenshots were removed; ports 3000 and 8000
  were stopped after verification.

## 2026-07-15 — Prompt 9: commitment, capacity, scenarios, and signature timeline

### Scope

Built the connected LocalLife OS planning experience: commitment portfolio and creation, explainable
commitment detail and relationship graph, time and financial capacity, isolated scenario editing and
comparison, exact reviewed scenario acceptance, and an incrementally loaded unified timeline. Added
a deterministic one-click Build Week, Berlin conference, Laptop purchase, and physical-versus-remote
demo that runs only through public loopback APIs.

### Important decisions

- Kept backend assessments authoritative. The frontend presents time, finance, conflicts,
  dependencies, warnings, assumptions, actions, and contributing records separately and introduces
  no feasibility score or advisory language.
- Used local `@xyflow/react` code and styles for the commitment graph. Every node is keyboard
  focusable, warning state is not color-only, and the graph supplements ordinary linked-record and
  warning-contributor navigation.
- Exposed the existing commitment `planned_cost_minor` calculation in list/detail responses so the
  portfolio can show requested cost without recomputing linked finance records in React.
- Added service-owned scenario APIs because the persisted overlay model previously had no complete
  lifecycle. Typed changes support task, calendar event, planned transaction, commitment, and goal
  projections; previews remain isolated and deterministic.
- Captured source revisions when changes are added, fingerprinted previews, surfaced stale causes,
  and required the same fingerprint at acceptance. Acceptance revalidates and applies the displayed
  exact plan atomically; preview, comparison, and discard never mutate primary records.
- Added forward migrations `0008` and `0009`: the first permits planned transactions in scenario
  overlays, and the second safely aligns all shared entity columns and constraints without rewriting
  an already-applied migration.
- Paired Recharts capacity visuals with equivalent semantic tables and kept the timeline's sensitive
  summaries compact. Server state remains in TanStack Query; Zustand remains UI-only.
- Used the deferred neutral brand contract, system fonts, restrained motion, semantic tokens, strong
  empty/sample states, and responsive overflow containment. No runtime AI, remote asset, telemetry,
  API key, or external service was introduced.

### Files created or materially changed

Backend scenarios, commitments, timeline, and persistence:

- `apps/api/app/models/common.py`
- `apps/api/app/repositories/connected.py`
- `apps/api/app/schemas/commitments.py`
- `apps/api/app/schemas/scenarios.py`
- `apps/api/app/services/commitment_management.py`
- `apps/api/app/services/scenarios.py`
- `apps/api/app/api/v1/router.py`
- `apps/api/app/api/v1/routes/scenarios.py`
- `apps/api/app/api/v1/routes/timeline.py`
- `apps/api/alembic/versions/20260715_0008_scenario_planning.py`
- `apps/api/alembic/versions/20260715_0009_domain_entity_width.py`
- `apps/api/tests/test_scenarios_api.py`
- `apps/api/tests/test_migrations.py`

Frontend contracts, navigation, and signature features:

- `apps/web/package.json`
- `package-lock.json`
- `apps/web/app/globals.css`
- `apps/web/components/app-shell.tsx`
- `apps/web/lib/api/types.ts`
- `apps/web/lib/api/connected.ts`
- `apps/web/lib/api/finance.ts`
- `apps/web/lib/api/query-keys.ts`
- `apps/web/app/commitments/`
- `apps/web/app/capacity/`
- `apps/web/app/scenarios/`
- `apps/web/app/timeline/`
- `apps/web/features/commitments/`
- `apps/web/features/capacity/`
- `apps/web/features/scenarios/`
- `apps/web/features/timeline/`
- `tests/e2e/frontend-smoke.mjs`
- `packages/shared-types/src/openapi.json`
- `packages/shared-types/src/openapi.ts`

Documentation:

- `docs/frontend-architecture.md`
- `docs/demo-flow.md`
- `docs/api-conventions.md`
- `docs/data-model.md`
- `docs/architecture.md`
- `docs/implementation-status.md`
- `docs/codex-development-log.md`

### Verification record

Commands run from the repository root unless a working directory is noted:

```text
npm install @xyflow/react --workspace @locallife/web
.\apps\api\.venv\Scripts\python.exe scripts\export-openapi.py
npm run generate:api-types
.\.venv\Scripts\python.exe -m pytest -q                         # apps/api
.\.venv\Scripts\python.exe -m pytest tests\test_migrations.py -q # apps/api
.\.venv\Scripts\python.exe -m ruff format --check app tests alembic # apps/api
.\.venv\Scripts\python.exe -m ruff check .                    # apps/api
.\.venv\Scripts\python.exe -m mypy app                        # apps/api
.\.venv\Scripts\alembic.exe upgrade head                     # apps/api
.\.venv\Scripts\alembic.exe current                          # apps/api
.\.venv\Scripts\alembic.exe check                            # apps/api
npm run test:web
npm run lint:web
npm run typecheck:web
npm run build:web
npm run test:e2e:web
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py
docker compose config --quiet
git -c safe.directory=C:/Python/fpcsa/LocalLifeOS diff --check
```

- Dependency installation: 13 packages added with zero reported vulnerabilities.
- OpenAPI export/generation: 87 paths and 249 schemas; generated TypeScript refreshed.
- Backend pytest: 62 tests passed. The warnings are the known Alembic SQLite implicit-constraint
  notices; no test failed.
- Migration verification: clean database reached `20260715_0009`; targeted migration test passed;
  local upgrade/current passed; metadata check reported no new operations.
- Ruff format check: 143 files formatted; Ruff lint passed; strict mypy passed across 111 source files.
- Frontend Vitest: 6 files and 10 tests passed. ESLint passed with zero warnings; strict TypeScript
  passed.
- Production build: passed with 14 routes, including `/capacity` and dynamic commitment detail.
- Live Chrome E2E: 11 routes passed at desktop, tablet, and compact widths (33 route checks), plus
  commitment/scenario/timeline/accessibility and mutation/search/calendar flows. No external
  request, runtime console error, route-boundary failure, or document-level overflow was detected.
- Visual inspection: physical-versus-remote scenario comparison and the commitment relationship
  graph passed the calm neutral design, hierarchy, traceability, and reduced-clutter review.
- Offline source verification passed. Compose configuration parsed successfully; Docker emitted
  only the known access warning for the user's Docker config file.
- Git whitespace check passed.
