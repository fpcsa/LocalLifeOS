# LocalLife OS foundation architecture

## Scope

This document describes the runnable repository foundation, local productivity and finance domains,
commitment and capacity engines, isolated scenario planning, unified timeline, and their connected
desktop-first frontend through Prompt 9. Imports, automation execution, service-worker caching, and
encrypted backups remain future work.

## Runtime boundary

LocalLife OS has two local processes and one local persistence boundary:

```text
Browser on this device
        |
        | HTTP over loopback only
        v
Next.js web :3000  ----->  FastAPI :8000  ----->  SQLite + local files
                                                   data/
```

- Docker Compose publishes both ports on `127.0.0.1`; neither service is published on a LAN interface.
- The API container listens on `0.0.0.0` only inside its private Compose network so host port forwarding can reach it.
- Browser API requests are restricted in code and configuration to loopback hosts.
- CORS accepts only explicit `127.0.0.1`, `localhost`, or IPv6 loopback origins.
- The application has no telemetry, analytics, remote database, runtime AI, CDN, remote font, or required external service.

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `apps/web` | Next.js application shell, local API client, TanStack Query, Zustand, and component tests |
| `apps/api` | FastAPI routes, schemas, services, repositories, SQLModel persistence, Alembic, and API tests |
| `packages/shared-types` | TypeScript contracts shared by frontend packages |
| `packages/ui` | Reusable local UI components |
| `data` | SQLite database plus imports, attachments, backups, and demo data |
| `docs` | Architecture, implementation status, and Codex development history |
| `scripts` | Cross-platform Compose launch and stop commands |
| `tests` | Repository-level integration, live-browser end-to-end, and fixture suites |

## Backend

The API is mounted under `/api/v1`.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/health` | Local service readiness and version |
| `GET /api/v1/system/info` | Local runtime guarantees and configured timezone |
| `GET/PATCH /api/v1/workspaces/current` | Current workspace and revision-checked updates |
| `GET/PATCH /api/v1/preferences` | Local preferences and revision-checked updates |
| `GET/POST /api/v1/tags` | Paginated tag discovery and creation |
| `DELETE /api/v1/tags/{id}` | Revision-checked tag soft deletion |
| `GET /api/v1/timeline` | Paginated and filtered domain activity |
| `GET /api/v1/meta/enums` | Stable enum values for clients |
| `/api/v1/projects` | Project lifecycle, targets, and derived progress |
| `/api/v1/tasks` | Tasks, subtasks, dependency graph, recurrence, filters, and bulk actions |
| `/api/v1/notes` | Markdown notes, daily notes, FTS5 search, links, and backlinks |
| `/api/v1/attachments` | Streaming local upload, metadata, download, and deletion |
| `/api/v1/calendar/events` | Timed/all-day events, recurrence, range query, move, and resize |
| `GET /api/v1/calendar/conflicts` | Timezone- and buffer-aware conflict detection |
| `/api/v1/finance` | Ledger, plans, recurrence, budgets, subscriptions, goals, and reports |
| `/api/v1/commitments` | Commitment lifecycle, typed links, impacts, warnings, and assessment |
| `/api/v1/scenarios` | Isolated typed changes, deterministic previews, comparison, and exact acceptance |
| `GET /api/v1/timeline/unified` | Typed cross-domain timeline with privacy-limited summaries |
| `/api/v1/scheduling` | Non-mutating CP-SAT previews, atomic apply, capacity, and explanations |

Every response receives an `X-Request-ID`. HTTP, validation, and unexpected errors use one structured `error` envelope. Settings are loaded with Pydantic Settings and reject remote database URLs, non-loopback CORS origins, telemetry, and external-request enablement.

Application startup creates the permitted data directories, runs `alembic upgrade head`, and
idempotently seeds the default workspace, preferences, categories, and `user.timezone` setting.
Domain identifiers use UUIDs, timestamps are generated in UTC, and the user-facing timezone is
stored separately.

### Backend layers

```text
FastAPI route -> Pydantic request/response schema -> domain service
                                                   |
                                                   v
                                             repository -> SQLModel -> SQLite
```

- Routes perform HTTP translation and never issue persistence queries.
- Schemas reject unknown fields and encode time, recurrence, money, and link invariants.
- Services own business rules and transaction boundaries.
- Repositories own query composition, stable pagination, soft deletion, and atomic revision checks.
- Domain exceptions are translated once into the common HTTP error envelope.

### Domain persistence

The current Alembic head creates the core, productivity, finance, commitment, goal, automation,
scenario, and normalized relationship tables documented in [data-model.md](data-model.md). Most
user-editable records use revision numbers and soft deletion. Link records are hard-deleted without
deleting their targets.

SQLite stores monetary values only as integer minor units plus validated ISO 4217 codes. Local file
attachments stream to generated, confined paths relative to `data/attachments` and store size,
media type, and SHA-256 metadata. Calendar/task recurrence uses canonical RRULE values parsed by
`python-dateutil`; notes use local SQLite FTS5 with migration-managed triggers. Productivity
services calculate task/project state and calendar conflicts without remote calls. Finance services
derive ledger balances, budget consumption, and projections without floating-point money or remote
rates. Commitment evidence collectors reuse those domain services; pure evaluators then derive
component statuses, traceable warnings, and suggested actions without an AI score or persisted
assessment cache. Scenario previews apply typed change records to detached copies and do not mutate
primary rows; fingerprint- and revision-checked acceptance applies an exact reviewed plan atomically.
Scheduling previews use OR-Tools CP-SAT over integer UTC minutes, persist their
request, result, and source fingerprint, and change task schedules only through an explicit atomic
apply action. API response, pagination, timestamp, recurrence, action, money, and concurrency
contracts are defined in [api-conventions.md](api-conventions.md); domain rules are detailed in
[productivity-domain.md](productivity-domain.md), [finance-engine.md](finance-engine.md), and
[commitment-engine.md](commitment-engine.md). Solver constraints, capacity formulas, preview
consistency, and operational limits are detailed in [scheduling-engine.md](scheduling-engine.md).

## Frontend

The App Router shell contains a top application bar, responsive primary navigation, connected
product routes, and a health status component. TanStack Query owns server state; Zustand owns only
shell and overlay state. Network calls are isolated in `lib/api`, whose base URL validator permits
only loopback hosts. Commitment views combine explainable assessments, typed links, warning source
navigation, and an accessible React Flow graph. Capacity views pair charts with equivalent tables.
Scenario views support typed editing, two- or three-way comparison, staleness detection, and an
explicit exact-plan review before acceptance. The unified timeline loads incrementally and groups
privacy-limited summaries by local date.

The interface uses Tailwind tokens and a system font stack. It includes light and dark color schemes, visible focus states, semantic elements, minimum interaction targets, a reduced-motion fallback, and loading/success/error health states. No asset refers to a remote host.

## Containers and persistence

The API and web images install from pinned Python requirements and `package-lock.json`. Compose waits for the API health check before starting the web service. A named volume, `locallife-os-data`, persists `/workspace/data` across container restarts.

Source bind mounts are intentionally omitted from the default Compose file to make the judging path reproducible across host operating systems. Native development commands provide hot reload.

## Deferred security work

The foundation includes loopback binding, path confinement, upload size/filename checks, local-only
CORS, request IDs, structured error handling, typed persistence validation, and foreign-key
enforcement. Encryption, authentication, CSRF policy for browser mutations, attachment malware or
content scanning, backup verification, service-worker caching, and a full threat model are not
implemented in this goal and must not be represented as complete.
