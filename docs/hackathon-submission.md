# Hackathon submission draft

## Project title

LocalLife OS

## Tagline

See whether life fits before you commit—privately, on your own device.

## Category

Apps for Your Life

## About the project

### Inspiration

Life decisions rarely belong to a single app. Saying yes to a conference, buying a new laptop, or
starting an ambitious project can affect a calendar, a task list, a budget, and a savings goal at
the same time. Yet most personal tools show only one part of that decision. They help us record a
commitment after we make it, but they do not help us understand whether it actually fits.

We wanted to build the missing layer between those tools: a private place where a person can see
the real consequences of a decision before accepting it. Just as importantly, we wanted those
answers to remain understandable and under the user's control. That led us to a fully local,
deterministic product with explicit assumptions instead of a cloud account, an opaque score, or an
AI making choices on the user's behalf.

### What it does

LocalLife OS brings tasks, projects, calendar events, notes, finances, goals, and commitments into
one local workspace. Its commitment engine connects the records involved in a decision and reports
time capacity, financial capacity, dependencies, scheduling conflicts, goal impact, and deadline
risk as separate, explainable results. Every warning identifies the records and assumptions behind
it.

Users can ask LocalLife OS to suggest a schedule, review every proposed placement, and choose
whether to apply it. They can also compare two or three what-if scenarios—such as attending an
event in person, joining remotely, or skipping it—without changing their real data. Accepting a
scenario shows the exact before-and-after changes and applies them atomically only if the source
data has not changed.

The application also includes Markdown notes and backlinks, calendar and bank-file imports,
multi-currency finance without hidden conversion, local automation rules, a unified timeline,
offline application-shell support, and optional encrypted backups. It needs no account, API key,
remote database, telemetry service, external asset, or runtime AI request.

### How we built it

LocalLife OS is a TypeScript and Python monorepo. The interface is built with Next.js, React,
TanStack Query, and Zustand. A typed FastAPI service uses Pydantic, SQLModel, Alembic, and SQLite,
with an OpenAPI-generated contract connecting the frontend and backend. OR-Tools CP-SAT powers the
bounded scheduling engine, while SQLite FTS5 provides local note search.

We kept complex rules in domain services rather than route handlers. Scheduling and scenario
workflows use a preview/review/apply boundary with optimistic revisions and fingerprints, so a
stale proposal cannot silently overwrite newer work. Attachments, imports, backups, and runtime
state are confined to a local data directory. The browser caches only the application shell and
static assets; API data remains network-only on the local loopback connection.

Docker Compose provides the reproducible judge environment, while PowerShell and POSIX launchers
support native use. The final verification suite covers migrations, domain behavior, concurrency,
timezone and currency rules, unsafe paths, import limits, backup tampering, offline behavior,
performance, and the critical browser flow across desktop, tablet, and compact layouts.

### Challenges we ran into

The hardest challenge was not building each feature independently; it was preserving meaning when
the features met. A scheduled task can affect a commitment, a calendar conflict, a scenario, and a
timeline at once. We had to define clear ownership and transaction boundaries so those views stayed
consistent without duplicating mutable state.

Explainability also required discipline. It would have been easy to collapse everything into a
single “good” or “bad” score. Instead, we built typed evidence and component calculations so users
can see whether a warning comes from missing time, a dependency, a buffer-aware calendar conflict,
or money in a particular currency.

Timezones, daylight-saving transitions, recurring records, minor-unit currency arithmetic, and
safe file handling created many less-visible edge cases. The local-only requirement added another
constraint: offline behavior, fonts, assets, telemetry, networking, and container configuration all
had to be audited so the product did not quietly depend on the internet. End-to-end testing exposed
a particularly subtle issue where a Docker-served Next.js development shell returned HTTP 200 but
could not hydrate reliably offline; switching the image to an optimized production build fixed the
root cause.

### Accomplishments that we're proud of

We are proud that LocalLife OS feels like one coherent system rather than a collection of demo
screens. A user can load a deterministic scenario, inspect a commitment, trace its warnings to real
records, compare alternatives, preview a feasible schedule, apply a reviewed plan, and see the
result reflected across the calendar, tasks, finances, goals, and timeline.

We also preserved user agency throughout the product. Assessments are explainable, previews do not
mutate data, consequential changes require confirmation, concurrency conflicts are detected, and
the workspace remains useful without sending personal information anywhere. The final review
passed 82 backend tests, 31 frontend tests, all 39 browser route checks, strict type and lint checks,
fresh migrations, encrypted backup/restore smoke tests, and the isolated Docker workflow.

### What we learned

We learned that personal productivity is fundamentally a relationship problem. Tasks, time, money,
and goals become much more useful when the links between them are first-class data rather than
labels that only a person can remember.

We also learned that deterministic software can still feel intelligent. Clear constraints,
traceable evidence, bounded optimization, and reversible scenarios produced useful guidance
without pretending to predict a person's future. Privacy was not a final security setting; it
shaped the architecture, feature boundaries, tests, and even the wording of the product from the
beginning.

Finally, preview-before-apply proved valuable far beyond scheduling. It became a general design
pattern for imports, scenarios, restore operations, and any workflow where the user should be able
to inspect consequences before changing primary data.

### What's next for LocalLifeOS

The next step is to package LocalLife OS as a signed desktop application around the existing local
services, making installation and updates simpler without giving up the offline-authoritative
workspace. We also want to design opt-in encryption for live data, including recovery and key
management, before claiming full at-rest protection.

Product work will focus on broader CSV and ICS compatibility, richer but still explainable scenario
templates, improved reports, and a dedicated detail experience for every linked entity. Quality
work will expand screen-reader, Firefox, WebKit, mobile, Linux, and macOS coverage. Longer term, we
would consider user-controlled synchronization only if the local workspace remains authoritative
and the product's privacy and review-before-apply principles are preserved.

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
- Fresh optimized Next.js and API images built and ran healthy with loopback-only ports during the
  2026-07-18 final review. The full Chrome smoke passed all 39 desktop/tablet/compact route checks,
  the critical mutation/demo flow, and an interactive service-worker offline reload.

## Future roadmap

- package signed desktop distributions around the existing loopback launcher;
- add opt-in live-data encryption with key recovery designed before implementation;
- broaden verified CSV/ICS dialect fixtures and non-Chromium accessibility coverage;
- add user-controlled sync only if it preserves an offline-authoritative local workspace;
- expand scenario templates and reporting without adding opaque or autonomous advice.
