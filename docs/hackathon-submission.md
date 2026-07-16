# Hackathon submission draft

## Project title

LocalLife OS

## Tagline

See whether life fits before you commit—privately, on your own device.

## Category

Apps for Your Life

## Concise project description

LocalLife OS is a fully local browser application that connects tasks, calendars, notes, money,
goals, and commitments. It exposes time, budget, dependency, and schedule consequences; compares
reversible what-if scenarios; and applies only the exact plan a user reviews. It runs without an
account, API key, cloud database, telemetry service, remote asset, or runtime AI request.

## Detailed project description

Personal plans usually live in disconnected tools. A calendar can show an event but not whether the
preparation time fits. A finance app can show a balance but not the work or deadline attached to a
purchase. A task list can show a deadline but not the conflicting commitment that created it.

LocalLife OS treats a commitment as a typed connection between ordinary local records: tasks,
projects, events, notes, transactions, budgets, savings goals, and goals. Its deterministic engine
reports time capacity, financial capacity, dependencies, calendar conflicts, goal impact, and
deadline risk as separate explainable components. Warning codes name the contributing records and
assumptions. There is deliberately no opaque “life score.”

The scheduling engine creates a bounded, non-mutating preview around availability, task duration,
dependencies, calendar occupancy, buffers, and deadlines. Scenario mode overlays typed changes and
compares two or three options without touching primary data. Acceptance shows exact before/after
fields and applies atomically only if revisions and the preview fingerprint still match.

The MVP also includes Markdown notes and backlinks, SQLite full-text search, safe attachments,
minor-unit multi-currency finance, budgets, subscriptions, savings goals, ICS and bank CSV imports,
fixed local automation rules, a unified timeline, an offline shell, and optionally encrypted local
backup/restore.

## How it works

1. A Next.js interface at `127.0.0.1:3000` calls a typed FastAPI API at `127.0.0.1:8000/api/v1`.
2. Pydantic validates input; service modules hold domain logic and transaction boundaries.
3. SQLModel repositories read/write a local SQLite database managed by Alembic migrations.
4. Attachments, imports, runtime state, and backups remain under one confined local data directory.
5. The commitment engine collects typed evidence and calculates explainable component states.
6. OR-Tools CP-SAT produces bounded schedule previews; apply is a separate revision-checked action.
7. Scenario overlays produce deterministic metrics and exact change plans; acceptance is atomic.
8. A service worker caches only the application shell/static assets. API data is never cached.
9. The Python service rejects telemetry and blocks outbound sockets by default.

Architecture and sequence diagrams are in [README](../README.md#architecture-and-data-flow) and
[architecture.md](architecture.md).

## Why it is fully on-device

- Both application processes bind to loopback interfaces outside containers.
- The database is a file on the user’s device; attachments/imports/backups are local files.
- No remote database, authentication provider, analytics SDK, CDN, remote font, or provider API is
  configured.
- There is no runtime AI feature. Assessments, schedules, imports, searches, and automations execute
  with deterministic local code and pinned local libraries.
- The frontend validates its API base as loopback-only; the backend validates CORS/Origin/Host and
  has a default-deny outbound socket guard.
- Repository and live-runtime asset scans fail on unexpected external URLs, redirects, or requests.

“On-device” does not mean “encrypted at rest”: the live SQLite database and ordinary local files are
plaintext. Only backups created with a password are encrypted. This limitation is explicit in the
UI, README, privacy documentation, and threat model.

## How Codex and GPT-5.6 were used

Codex and GPT-5.6 acted as an engineering copilot across twelve bounded implementation goals. They
accelerated repository inspection, architecture decomposition, SQLModel/Pydantic schemas, Alembic
migrations, service/repository implementation, generated API contracts, React UI composition,
deterministic fixtures, adversarial testing, and verification scripting.

High-impact examples:

- converting product requirements into typed, transactional modules and acceptance tests;
- constructing explainable commitment, scheduling, and scenario services without runtime AI;
- generating migration, concurrency, recurrence, import-security, path-safety, backup-tamper,
  offline, and end-to-end workflow tests;
- auditing request patterns and replacing an unbounded unified-timeline loader with bounded per-source
  queries and page-only relationship hydration;
- discovering and fixing a real delete-all foreign-key ordering defect through the judge workflow;
- producing cross-platform setup, demo, security, privacy, and submission documentation.

Human review retained control of product scope and consequential claims: no runtime AI, no cloud
dependency, currency separation without conversion, explicit preview/apply boundaries, no opaque
feasibility score, plaintext live-storage disclosure, encryption wording, supported-platform claims,
and known limitations. Detailed decisions and verification evidence are in
[codex-development-log.md](codex-development-log.md).

## Repository test instructions

Prerequisites: Python 3.12+, Node.js 22+, npm, and installed development dependencies.

```powershell
.\apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests -q
.\apps\api\.venv\Scripts\python.exe -m ruff check --config apps\api\pyproject.toml apps\api scripts
.\apps\api\.venv\Scripts\python.exe -m mypy --config-file apps\api\pyproject.toml apps\api\app
npm run typecheck:web
npm run lint:web
npm run test:web
npm run build:web
```

Critical judge flow and local performance:

```powershell
.\apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests\test_judge_workflow.py -q
.\apps\api\.venv\Scripts\python.exe scripts\performance-smoke-test.py
```

Offline, assets, and backup/restore:

```powershell
.\apps\api\.venv\Scripts\python.exe scripts\check-external-assets.py
.\apps\api\.venv\Scripts\python.exe scripts\verify-offline-mode.py
.\apps\api\.venv\Scripts\python.exe scripts\backup-smoke-test.py
.\apps\api\.venv\Scripts\python.exe scripts\restore-smoke-test.py
npm run test:e2e:web
```

The complete command set and prerequisites are in [README](../README.md#verification-and-judge-tests).
Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs` while running.

## Demo instructions

```bash
docker compose up --build
curl -X POST http://127.0.0.1:8000/api/v1/demo/load
```

Open `http://127.0.0.1:3000` and follow [demo-script.md](demo-script.md). No login or credentials are
required. The `2026.07` data is entirely synthetic and can be refreshed from the Scenarios screen or
with `scripts/reset-demo-data.py` in native mode.

Screenshot placeholders before form submission:

- [ ] Today dashboard with demo warnings and capacity.
- [ ] Berlin physical/remote/skip comparison.
- [ ] Berlin commitment relationship graph.
- [ ] Offline shell and banner after a disconnected reload.

## Supported platforms

- Docker Compose was verified with Linux-based containers on Docker Desktop for Windows.
- Native Windows was verified with PowerShell, Python, Node.js, and Chrome.
- POSIX launcher and setup commands are included; the API entrypoint ran in Debian containers, but
  a separate Linux/macOS host was not part of the final matrix.
- Current Chromium is the verified browser. Firefox, WebKit, mobile, and screen-reader matrices are
  not complete.

## Known limitations

- The live database and ordinary data directories are plaintext.
- Single local workspace; no multi-user sync, cloud login, or hosted backup.
- No live bank/provider sync, exchange-rate service, runtime AI, or natural-language automation.
- Import coverage is intentionally conservative; not every bank/ICS dialect is supported.
- Scenarios are deterministic projections from current records, not probabilistic forecasts.
- Scheduling is bounded optimization and can report unscheduled work.
- Automated Axe scanning could not be installed because the development environment blocked the
  dependency download; semantic/label/focus browser checks and manual review remain, but a full
  assistive-technology pass is still required.
- The final submission pass validated Compose configuration but could not freshly build/start the
  Prompt 12 images because the development environment blocked Docker-engine access. Prompt 11 had
  verified healthy unprivileged containers; rerun `docker compose up --build` on the judge host.
- The extended Chrome smoke completed its desktop critical workflow, but the environment blocked a
  retry after the runner output was truncated. The earlier 1280/768/375 baseline passed; capture a
  fresh extended all-viewport marker before release sign-off.

## Future roadmap

- package signed desktop distributions around the existing loopback launcher;
- add opt-in live-data encryption with key recovery designed before implementation;
- broaden verified CSV/ICS dialect fixtures and non-Chromium accessibility coverage;
- add user-controlled sync only if it preserves an offline-authoritative local workspace;
- expand scenario templates and reporting without adding opaque or autonomous advice.
