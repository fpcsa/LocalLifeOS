# Frontend architecture

## Scope

The LocalLife OS frontend is a desktop-first Next.js App Router application that presents the
existing local FastAPI domains without reimplementing their business rules. It runs entirely on
loopback, uses bundled code and system fonts, and makes no runtime request to a remote host.

The application implements Today, Tasks and Projects, Calendar, Notes, Finance and Budgets, Goals,
Commitments, Capacity, Scenarios, Timeline, and Settings. The signature planning experience keeps
the commitment assessment, capacity calculation, scenario projection, and timeline domains visibly
connected without duplicating backend business rules in React.

## Runtime and data flow

```text
Browser route or global overlay
        |
        v
TanStack Query hook -> typed domain API module -> loopback FastAPI /api/v1
        |                                            |
        v                                            v
query-key factory / cache                     domain services + SQLite

Zustand is separate and stores UI-only state:
sidebar, command palette, quick-create dialog, and toasts.
```

- `scripts/export-openapi.py` exports the running FastAPI schema without a network request.
- `openapi-typescript` generates `packages/shared-types/src/openapi.ts` from the exported schema.
- `apps/web/lib/api/types.ts` aliases the generated schemas used by the interface.
- Domain clients in `apps/web/lib/api` own paths, query serialization, envelopes, and request
  payloads. Pages and components do not call `fetch` directly.
- `apps/web/lib/api/query-keys.ts` is the single query-key factory. Mutations invalidate the
  narrowest domain root that can have derived changes.
- The API client rejects a configured base URL unless its hostname is loopback.

Backend revisions remain the source of optimistic-concurrency truth. The frontend sends revisions
on update and action requests and surfaces structured backend errors without attempting to predict
domain outcomes.

## Application shell

The root providers install the shared query client, preference-driven theme synchronization,
offline banner, command palette, quick-create dialog, and toast viewport. The application shell
adds a sticky top bar, a collapsible 240-pixel desktop sidebar, and an overflow-contained compact
navigation row. Primary destinations are:

- Today
- Tasks
- Calendar
- Notes
- Finance
- Goals
- Commitments
- Capacity
- Scenarios
- Timeline
- Imports
- Automation
- Settings

The command palette supports `Ctrl/Cmd+K`, route navigation, and backend search across tasks,
projects, notes, commitments, and transactions. Quick create supports tasks, events, notes, and
transactions without replacing server state in Zustand.

## Route modules

| Route | Feature module and responsibility |
| --- | --- |
| `/` | Today summaries for events, tasks, planned money, warnings, capacity, goals, and deadlines |
| `/tasks` | URL-backed list/board filters, project grouping/progress, bulk completion/rescheduling, forms, task detail, dependencies, subtasks, recurrence, and schedule suggestions |
| `/calendar` | FullCalendar month/week/day/agenda views, conflict list, buffer details, drag/resize, text alternative, and task placement previews |
| `/notes` | Searchable split view, Markdown editing, tags, daily note, links/backlinks, related records, and attachments |
| `/finance` | Accounts, transaction/transfer/category forms, budgets, reports, committed balances, subscriptions, and savings |
| `/goals` | Separate general and savings goal creation, progress, targets, accounts, and commitment links |
| `/commitments` | Searchable commitment portfolio with target, cost, time, warnings, and component states plus the guided creation flow |
| `/commitments/[id]` | Assessment detail, warning contributors, time/finance impacts, linked records, React Flow relationship graph, timeline, and reviewed schedule apply |
| `/capacity` | Daily and weekly raw/focus/committed/remaining capacity plus financial committed-balance summaries and accessible chart alternatives |
| `/scenarios` | Two- or three-way scenario editing, projection, comparison, exact acceptance plan, staleness handling, and signature demo preparation |
| `/timeline` | Incrementally loaded, date-grouped cross-domain activity with URL-backed type, commitment, and date filters and privacy-limited summaries |
| `/imports` | Local ICS/CSV upload, classified and normalized previews, row selection, mapping profiles, apply, export, and history |
| `/automation` | Structured rule builder, lifecycle, write-free test context, scheduler status, notifications, and execution history |
| `/settings` | Revision-checked locale, timezone, currency, week-start, and theme preferences plus local-system guarantees |

Route-level `loading.tsx` and `error.tsx` provide safe fallbacks. Feature views also render local
skeleton, empty, error, and retry states so query failures do not blank the shell.

## Calendar mutation model

FullCalendar provides visual drag and resize interactions. Before a move or resize, the mutation:

1. cancels matching calendar-event queries;
2. snapshots every active event-range cache;
3. applies the proposed time to cached events;
4. sends the revision-checked action request;
5. restores all snapshots and calls FullCalendar's `revert` callback on error; and
6. invalidates events and conflicts after settlement.

Conflict styling is supplemented by a semantic conflict list. A disclosure below the visual
calendar contains the same event range as text, so calendar information does not depend on a grid
or color.

## Money, dates, and charts

Finance values remain integer minor units until formatting. `Intl.NumberFormat` supplies the
currency-specific fraction digits, including zero-decimal currencies, and entry forms convert
major-unit text to integers before submitting. Reports never combine different currencies.

Date helpers use the saved IANA timezone for local day boundaries, labels, and Today queries. The
day-range conversion is tested across daylight-saving transitions. Server UTC timestamps are not
rewritten as local domain data.

Recharts renders cash-flow and category-spending views. Every chart is labelled and has an adjacent
table or list containing the same values. Charts are summaries only; the backend remains the
calculation authority.

React Flow renders commitment relationships from typed backend links. Nodes remain keyboard
focusable, graph records have ordinary links in the surrounding detail view, warning contributors
link directly to their source records, and component states remain available as text. The graph is
an explanatory view rather than an aggregate feasibility score.

Scenario previews are server-calculated overlays. The frontend edits typed change records, shows
baseline and projected metrics, compares two or three previews, and requires a checked review of
the exact change plan before acceptance. Preview fingerprints and captured source revisions make a
stale scenario visible and non-acceptable until it is refreshed.

## Accessibility and responsive behavior

- Landmarks, headings, tables, lists, labels, buttons, links, and native dialogs use semantic HTML.
- Visible focus rings and minimum 40-pixel targets are shared by controls and navigation.
- Field help and errors are connected with `aria-describedby`; required validation is announced.
- Dialogs provide labelled titles, Escape handling, backdrop close, and native focus containment.
- Reduced-motion preferences collapse transitions and animation durations.
- System, explicit light, and explicit dark themes use the same semantic token set.
- Tables, compact navigation, and calendar toolbars contain their own overflow; the document does
  not scroll horizontally at 375, 768, or 1280 pixels.

## Verification strategy

Vitest and Testing Library cover service status, exact money conversion, timezone/DST boundaries,
task validation, commitment creation and linking, reviewed schedule application, import row
selection, and write-free automation test preview. The
Playwright-Core smoke script uses the locally installed Chrome executable—without downloading a
browser—to exercise every route at 1280, 768, and 375 pixels. Its signature desktop flow prepares
the Build Week, Berlin conference, and Laptop purchase records through public APIs, compares the
physical and remote conference scenarios, opens the commitment graph and schedule review, filters
the timeline by commitment, and checks signature-page controls for accessible names. It also
rejects runtime console errors, external HTTP requests, route-boundary failures, and page-level
horizontal overflow.

The test database and screenshots are temporary verification artifacts and are removed after
inspection.

## Deferred work

The following remain intentionally outside this goal: service-worker caching, encryption,
authentication, and any advisory or runtime-AI behavior. Scenario projections
are deterministic planning aids based only on local data and user-entered assumptions.
