# LocalLife OS

> A fully on-device personal operating system for managing tasks, calendar events, notes, expenses, income, goals, and commitments from one private local workspace.

LocalLife OS is a local-first browser application that helps users understand whether they can realistically afford a new commitment in **time, money, and attention**.

Instead of keeping tasks, appointments, notes, and finances in disconnected applications, LocalLife OS connects them through a shared data model. A conference, purchase, trip, course, project, or personal goal can include tasks, calendar events, notes, planned expenses, income effects, deadlines, and dependencies.

The application runs entirely on the user's computer. It does not require an API key, cloud account, remote database, or runtime AI model.

---

## Project status

LocalLife OS is currently in the MVP implementation phase for the **OpenAI Build Week — Apps for Your Life** track.

The initial release will focus on a complete local workflow:

1. Import personal calendar and transaction data.
2. Manage tasks, notes, events, income, and expenses.
3. Group related information into commitments.
4. Preview the time and financial impact of a commitment.
5. Compare alternative scenarios before making a decision.
6. Back up and restore the entire workspace locally.

---

## Why LocalLife OS

Most personal applications understand only one part of a user's life:

- A calendar knows when the user is busy.
- A task manager knows what is due.
- A notes application stores context.
- A finance tracker knows what has already been spent.
- A budgeting application estimates what may be affordable.

LocalLife OS connects these areas.

Before the user commits to a new project, trip, course, purchase, or recurring responsibility, the application can show:

- Calendar conflicts
- Required preparation time
- Missing prerequisite tasks
- Planned and recurring costs
- Impact on savings goals
- Available focused time
- Financial and scheduling constraints
- Alternative scenarios

### Product statement

> Your calendar knows when you are free. Your finance app knows what you spent. Your task manager knows what is due. LocalLife OS helps determine whether you can actually afford to say yes—in time, money, and attention.

---

## Core concept: commitments

The central object in LocalLife OS is a **commitment**.

A commitment can connect:

- Tasks and subtasks
- Calendar events
- Notes and attachments
- Planned expenses
- Expected income
- Budgets
- Goals
- Deadlines
- Dependencies
- Recurring obligations

Example:

```text
Commitment: Attend a technology conference

Calendar
- Conference: September 12–14
- Travel: September 11 and 15
- Preparation: 6 hours

Tasks
- Buy ticket
- Reserve hotel
- Request leave
- Prepare presentation

Financial impact
- Ticket: €450
- Hotel: €420
- Transport: €160
- Food estimate: €140
- Total planned cost: €1,170

Detected constraints
- Dentist appointment on September 14
- Project deadline on September 16
- Savings target falls €370 below plan
- Only 4 of 6 preparation hours are currently available
```

---

## MVP features

### Unified dashboard

The dashboard provides one operational view of the user's day and near future:

- Tasks due today
- Upcoming appointments
- Planned expenses
- Expected income
- Overdue commitments
- Budget warnings
- Schedule conflicts
- Goal progress
- Available time capacity

### Tasks and projects

- Tasks and subtasks
- Projects
- Priorities
- Deadlines
- Dependencies
- Recurring tasks
- Estimated duration
- Actual duration
- Completion tracking
- Links to notes, events, goals, and commitments

### Calendar

- Day, week, month, and agenda views
- Appointments and events
- Recurring events
- Preparation time
- Travel time
- Recovery time
- Conflict detection
- `.ics` import and export
- Automatic placement suggestions for eligible tasks

### Notes

- Markdown editor
- Tags
- Backlinks
- Daily notes
- Search
- Attachments
- Links to tasks, events, transactions, goals, and commitments

### Personal finance

- Financial accounts
- Income and expenses
- Transfers
- Categories
- Budgets
- Savings goals
- Planned transactions
- Recurring transactions
- Subscription tracking
- CSV import
- Monthly cash-flow view

### Commitments

- Group tasks, events, notes, and financial records
- Track planned cost and actual cost
- Estimate required time
- Detect scheduling conflicts
- Detect missing dependencies
- Measure effect on budgets and goals
- Compare commitment alternatives

### Scenario mode

Users can create temporary branches of their current life without modifying real data.

Example scenarios:

- Attend a conference physically or remotely
- Buy a laptop now or in three months
- Accept a new job
- Move to a new home
- Take a career break
- Add a recurring course or side project

Each scenario can compare:

- Time requirements
- Calendar conflicts
- Planned cash flow
- Savings impact
- Goal delays
- Capacity constraints
- Risk of dropping below a financial buffer

### Unified timeline

The timeline combines:

- Task activity
- Calendar events
- Notes
- Income
- Expenses
- Commitment changes
- Goal progress
- Scenario decisions

### Local automation rules

Users can define deterministic local rules.

Example:

```yaml
when:
  transaction.category: subscription
  transaction.amount_change: ">10%"

then:
  create_task: "Review subscription price increase"
  due_in_days: 7
```

Another example:

```yaml
when:
  event.category: travel

then:
  create_tasks:
    - "Check travel documents"
    - "Prepare travel budget"
    - "Confirm accommodation"
```

### Backup and restore

- Encrypted local backups
- Manual backup creation
- Backup verification
- Restore preview
- Full workspace export
- No cloud account required

---

## Offline-first principles

LocalLife OS is designed to operate fully on the user's device.

### No runtime AI

The application does not require:

- OpenAI API keys
- External model providers
- Local language models
- Remote inference
- Cloud-based AI services

GPT-5.6 is used through Codex to design and build the software, not as a runtime dependency.

### No external services

The target application configuration includes:

- Backend bound only to `127.0.0.1`
- No telemetry
- No analytics
- No remote database
- No CDN assets
- No remote fonts
- No external API calls
- No cloud synchronization
- No mandatory account registration

### Offline browser experience

The frontend uses a service worker to cache the application shell and local assets. Once installed
and launched locally, the shell remains available without an Internet connection; current data
reads and writes still require the loopback API.

---

## Technology stack

### Frontend

- **Next.js**
- **TypeScript**
- **Tailwind CSS**
- **FullCalendar**
- **React Flow**
- **Recharts**
- **TanStack Query**
- **Zustand**

Zustand is selected for lightweight client-side state management. TanStack Query manages backend state, caching, mutations, and invalidation.

### Backend

- **Python**
- **FastAPI**
- **Pydantic**
- **SQLModel**
- **SQLite**
- **Alembic**
- **OR-Tools**
- **Pandas**
- **APScheduler**
- **Typer**
- **argon2-cffi + cryptography**

### Local execution

- **Docker Compose** for development and judging
- Native Python launcher for normal local use
- Backend exposed only on the loopback interface
- Local SQLite database
- Local attachment storage
- Service worker for offline frontend assets

---

## Architecture

```text
┌───────────────────────────────────────────────┐
│                 Local browser                 │
│                                               │
│  Next.js + TypeScript + Tailwind CSS          │
│  FullCalendar + React Flow + Recharts         │
│  TanStack Query + Zustand                     │
└───────────────────────┬───────────────────────┘
                        │ HTTP on 127.0.0.1
┌───────────────────────▼───────────────────────┐
│                 FastAPI backend               │
│                                               │
│  API routes                                   │
│  Commitment engine                            │
│  Scenario engine                              │
│  Scheduling engine                            │
│  Automation rules                             │
│  Import/export services                       │
│  Backup and restore                           │
└───────────────────────┬───────────────────────┘
                        │
        ┌───────────────┴────────────────┐
        │                                │
┌───────▼────────┐              ┌────────▼────────┐
│ SQLite database│              │ Local file store │
│                │              │                  │
│ SQLModel       │              │ Attachments      │
│ Alembic        │              │ Backups          │
│ Local records  │              │ Import files     │
└────────────────┘              └──────────────────┘
```

---

## Main backend components

### Commitment engine

Calculates the combined effect of linked tasks, events, transactions, goals, and notes.

Responsibilities:

- Planned cost aggregation
- Actual cost aggregation
- Time requirement aggregation
- Dependency validation
- Conflict detection
- Goal-impact analysis
- Commitment status calculation

### Scheduling engine

Uses OR-Tools to evaluate and suggest task placement.

Inputs can include:

- Task duration
- Deadline
- Priority
- Eligible time windows
- Existing calendar events
- Work hours
- Travel and preparation buffers
- Dependency ordering

The engine must provide transparent results. Scheduling suggestions should include the constraints and assumptions that produced them.

### Scenario engine

Creates isolated scenario branches based on the current workspace state.

A scenario can modify:

- Income
- Expenses
- Calendar events
- Commitments
- Goals
- Time availability
- Financial buffer
- Recurring obligations

Scenario changes are not applied to the primary workspace unless the user explicitly accepts them.

### Import service

Initial supported imports:

- Calendar files in `.ics` format
- Bank transactions in `.csv` format
- LocalLife OS backup archives

CSV column mapping will be configurable to support different bank export formats.

### Automation engine

APScheduler runs local recurring jobs such as:

- Generating recurring tasks
- Creating recurring transactions
- Checking upcoming deadlines
- Recalculating capacity
- Evaluating local automation rules
- Creating scheduled backup reminders

---

## Proposed data model

Core entities:

```text
Workspace
├── UserPreferences
├── Accounts
├── Transactions
├── Budgets
├── Goals
├── Tasks
├── Projects
├── CalendarEvents
├── Notes
├── Commitments
├── Scenarios
├── AutomationRules
├── Attachments
└── TimelineEvents
```

Important relationships:

```text
Commitment
├── Tasks
├── CalendarEvents
├── Notes
├── PlannedTransactions
├── Goals
└── Dependencies
```

The data model should support many-to-many relationships so that one note, task, or transaction can provide context to more than one object where appropriate.

---

## Repository structure

The intended monorepo structure is:

```text
locallife-os/
├── apps/
│   ├── web/                         # Next.js frontend
│   └── api/                         # FastAPI backend
│
├── packages/
│   ├── shared-types/                # Shared schemas and generated clients
│   └── ui/                          # Reusable frontend components
│
├── data/
│   ├── demo/                        # Synthetic judge-friendly sample data
│   ├── imports/                     # Local import workspace
│   ├── backups/                     # Local backup archives
│   └── attachments/                 # Local attachment storage
│
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── privacy.md
│   ├── threat-model.md
│   ├── scheduling-engine.md
│   ├── codex-development-log.md
│   └── implementation-status.md
│
├── scripts/
│   ├── start-local.sh
│   ├── start-local.ps1
│   ├── stop-local.sh
│   ├── stop-local.ps1
│   ├── load-demo-data.py
│   └── verify-offline-mode.py
│
├── tests/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── docker-compose.yml
├── .env.example
├── LICENSE
└── README.md
```

---

## Quick start with Docker Compose

### Prerequisites

- Docker
- Docker Compose

### Start the application

```bash
git clone <repository-url>
cd locallife-os

docker compose up --build
```

Equivalent repository scripts are available:

Linux or macOS:

```bash
sh ./scripts/start-local.sh
```

Windows PowerShell:

```powershell
.\scripts\start-local.ps1
```

Open:

```text
http://127.0.0.1:3000
```

### Supported native launcher

After installing the Python and npm dependencies above, use the same supported command set on
Windows, Linux, and macOS.

Windows PowerShell:

```powershell
.\scripts\locallife.ps1 doctor
.\scripts\locallife.ps1 start --open-browser
.\scripts\locallife.ps1 status
.\scripts\locallife.ps1 backup --encrypt
.\scripts\locallife.ps1 restore .\data\backups\<backup>.llbackup
.\scripts\locallife.ps1 stop
```

Linux or macOS:

```bash
./scripts/locallife.sh doctor
./scripts/locallife.sh start --open-browser
./scripts/locallife.sh status
./scripts/locallife.sh backup --encrypt
./scripts/locallife.sh restore ./data/backups/<backup>.llbackup
./scripts/locallife.sh stop
```

The launcher binds both processes to `127.0.0.1`, checks occupied ports, displays process and data
status, and opens a browser only with `--open-browser`. See
[docs/native-launcher.md](docs/native-launcher.md).

The backend API will be available locally at:

```text
http://127.0.0.1:8000
```

### Stop the application

```bash
docker compose down
```

### Remove local development volumes

```bash
docker compose down --volumes
```

This deletes local development data. Create a backup first when working with non-demo data.

---

## Native local development

### Prerequisites

- Python 3.12 or later
- Node.js 22 or later
- npm or pnpm

### Backend

```bash
cd apps/api

python -m venv .venv
```

Activate the virtual environment.

Linux or macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies and run migrations:

```bash
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
```

Start the backend:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```bash
cd locallife-os
npm install
npm run dev:web
```

Open:

```text
http://127.0.0.1:3000
```

---

## Environment configuration

LocalLife OS should run with minimal configuration.

Example `.env`:

```dotenv
LOCALLIFE_ENV=development
LOCALLIFE_HOST=127.0.0.1
LOCALLIFE_PORT=8000
LOCALLIFE_CONTAINER_MODE=false

LOCALLIFE_DATA_DIR=./data
LOCALLIFE_DATABASE_URL=sqlite:///./data/locallife.db
LOCALLIFE_ATTACHMENTS_DIR=./data/attachments
LOCALLIFE_BACKUPS_DIR=./data/backups
LOCALLIFE_IMPORTS_DIR=./data/imports
LOCALLIFE_RUNTIME_DIR=./data/runtime
LOCALLIFE_MAX_BACKUP_BYTES=2147483648

LOCALLIFE_CORS_ORIGINS=["http://127.0.0.1:3000","http://localhost:3000"]
LOCALLIFE_DEFAULT_TIMEZONE=UTC
LOCALLIFE_TELEMETRY_ENABLED=false
LOCALLIFE_EXTERNAL_REQUESTS_ENABLED=false

NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_TELEMETRY_DISABLED=1
```

There are no AI-provider or third-party API keys.

---

## Demo data

The repository will include a synthetic workspace for judges.

The demo dataset will contain:

- Tasks and projects
- Calendar appointments
- Notes
- Income and expenses
- Financial accounts
- Savings goals
- A technology-conference commitment
- A laptop-purchase scenario
- Scheduling conflicts
- A planned budget shortfall

Load the demo dataset:

```bash
python scripts/load-demo-data.py
```

All names, accounts, transactions, and documents in the demo dataset will be fictional.

---

## Testing

### Backend tests

```bash
cd apps/api
python -m pytest
python -m ruff check .
python -m mypy app
```

Test coverage should include:

- API validation
- Commitment calculations
- Scheduling constraints
- Scenario isolation
- CSV import
- Calendar import
- Recurring jobs
- Backup and restore
- Automation rules

### Frontend tests

```bash
npm run test:web
npm run lint:web
npm run typecheck:web
npm run build:web
```

### End-to-end tests

The repository-level browser smoke flow uses the locally installed Chrome executable and exercises
every route at desktop, tablet, and compact widths. It also covers core mutations, accessible form
labels, external-request rejection, and an offline service-worker reload.

E2E scenarios should include:

1. Create a commitment.
2. Attach tasks and calendar events.
3. Add planned expenses.
4. Detect a conflict.
5. Create an alternative scenario.
6. Resolve the conflict.
7. Export and restore a backup.

### Offline verification

```bash
python scripts/verify-offline-mode.py
python scripts/check-external-assets.py
python scripts/backup-smoke-test.py
python scripts/restore-smoke-test.py
```

The verification scripts confirm that:

- The backend binds only to the loopback interface.
- The application makes no external HTTP requests.
- No remote assets are referenced.
- Core workflows function with network access disabled.

The service worker caches only the application shell and same-origin static assets. API requests
use `no-store` and are never placed in the service-worker cache. A live runtime URL can be checked
with `python scripts/check-external-assets.py --runtime-url http://127.0.0.1:3000`.

---

## Privacy and security

LocalLife OS is designed around local ownership of personal data.

### Privacy principles

- Data remains on the user's computer.
- No account registration is required.
- No telemetry is collected.
- No analytics are collected.
- No remote requests are required.
- No personal data is used for model inference.
- No external model is included at runtime.

### Local security goals

The MVP provides:

- Local session protection
- Secure backup format
- Attachment path validation
- Input-file validation
- CSV formula-injection protection
- Strict CORS configuration
- Loopback-only backend binding
- Content Security Policy
- CSRF protection where applicable
- Safe file upload limits
- Database migration safeguards

The inactivity lock is a casual privacy screen, not authentication. The live SQLite database and
ordinary data directories are not application-encrypted; protect the OS account and disk. Optional
password-protected `.llbackup` files use Argon2id and AES-256-GCM, are checksum-verified before
success, and are safety-backed up before restore. See [privacy.md](docs/privacy.md),
[threat-model.md](docs/threat-model.md), and [backup-format.md](docs/backup-format.md) for exact
claims, limitations, and recovery instructions.

---

## Accessibility

The application should target:

- Keyboard navigation
- Visible focus states
- Semantic HTML
- Screen-reader-friendly labels
- Sufficient contrast
- Reduced-motion support
- Scalable text
- Accessible charts with textual summaries

---

## Hackathon use of GPT-5.6 and Codex

LocalLife OS is being designed and implemented with Codex powered by GPT-5.6.

GPT-5.6 and Codex are used during development for:

- Product scoping
- Architecture decisions
- Data-model design
- Backend implementation
- Frontend implementation
- Database migrations
- Scheduling-engine implementation
- Test generation
- Accessibility improvements
- Security review
- Documentation
- Demo-data generation
- Refactoring and code review

The final application does not call GPT-5.6 or any other model at runtime.

The repository will include:

```text
docs/codex-development-log.md
```

This document will summarize:

- Major Codex sessions
- Key technical decisions
- Important generated components
- Human-reviewed changes
- Testing and verification performed
- The primary `/feedback` Codex session ID used for the submission

---

## Three-minute demo flow

The planned demonstration is:

1. Start LocalLife OS locally.
2. Import a synthetic `.ics` calendar.
3. Import a synthetic bank transaction CSV.
4. Show the unified Today dashboard.
5. Create a commitment to attend a conference.
6. Add tasks, dates, and planned expenses.
7. Detect a calendar conflict and savings shortfall.
8. Compare physical and remote attendance scenarios.
9. Resolve the conflict and improve feasibility.
10. Disable network access and continue using the application.
11. Show the Codex session and explain how GPT-5.6 built the project.

---

## MVP roadmap

### Phase 1 — Foundation

- Monorepo setup
- FastAPI service
- Next.js application
- SQLite and Alembic
- Core entities
- Local launcher
- Docker Compose

### Phase 2 — Core modules

- Tasks
- Calendar
- Notes
- Financial accounts
- Transactions
- Budgets
- Goals

### Phase 3 — Connected life model

- Commitments
- Entity relationships
- Unified timeline
- Conflict detection
- Capacity calculations

### Phase 4 — Scenario engine

- Scenario branching
- Financial projections
- Scheduling projections
- Comparison view
- Scenario acceptance

### Phase 5 — Imports and automation

- `.ics` import
- Transaction CSV import
- APScheduler jobs
- Local automation rules

### Phase 6 — Offline and privacy hardening

- Service worker
- Local asset verification
- Backup and restore
- Security controls
- Threat model
- Offline test suite

### Phase 7 — Submission readiness

- Synthetic demo data
- E2E tests
- README verification
- Demo video
- Architecture documentation
- Codex development log
- `/feedback` session ID

---

## Non-goals for the MVP

The initial version will not include:

- Mobile applications
- Cloud synchronization
- Bank API synchronization
- Google Calendar integration
- Email integration
- Collaboration
- Receipt OCR
- Investment trading
- Tax advice
- Financial advice
- Runtime AI
- Remote inference
- Browser extensions

---

## Contributing

Contribution guidelines will be added once the initial architecture and repository structure are stable.

Until then:

1. Open an issue describing the proposed change.
2. Keep all runtime features local-first.
3. Do not introduce telemetry or external network dependencies.
4. Add tests for new behavior.
5. Update relevant documentation.

---

## License

The project is intended to be released under the **MIT License**.

The final repository will include the complete license text in `LICENSE`.

---

## Disclaimer

LocalLife OS is a personal organization and simulation tool.

It does not provide financial, legal, medical, tax, or investment advice. Forecasts and scenarios depend on the data and assumptions supplied by the user and may not reflect future outcomes.

---

## Name

**LocalLife OS**

Alternative repository slug:

```text
locallife-os
```

Tagline:

> Plan your time, money, and commitments—privately, on your own device.
