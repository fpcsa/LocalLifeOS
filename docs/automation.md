# Deterministic local automation

Automation rules are structured records, not programs. Each enabled rule has one typed trigger,
zero or more allow-listed conditions, and one typed action. Unknown fields are rejected and no rule
can contain Python, JavaScript, shell commands, templates, URLs, or arbitrary expressions.

## Triggers and context

| Trigger | Emission |
| --- | --- |
| `transaction_created` | after a manual or CSV-imported transaction commits |
| `subscription_amount_changed` | after a revision-checked amount update commits |
| `event_created` | after a manual or ICS-imported event commits |
| `event_approaching` | local scheduler scan for timed events inside the rule lookahead |
| `task_overdue` | local scheduler scan for incomplete tasks past their due time |
| `commitment_warning_created` | when a deterministic commitment assessment produces a warning |
| `recurring_schedule` | interval, daily, or weekly local schedule in an IANA timezone |

Conditions support equality, inequality, numeric comparison, case-insensitive containment, and
membership. Each trigger exposes a documented context allow-list. Conditions are ANDed in stored
order. The preview/test endpoint evaluates sample JSON context and describes the resulting action;
it always returns `writes_performed=false`.

## Actions

Rules can create a task, note, planned transaction, tag link, local notification, or local backup
reminder. Actions reuse the same domain validation and transaction boundaries as ordinary records.
They never post an actual financial transaction, perform a backup, send a message, or contact a
remote system. A backup action deliberately creates a reminder only.

## Scheduler and restart behavior

APScheduler runs in the API process when `LOCALLIFE_AUTOMATION_SCHEDULER_ENABLED=true`. Rule
definitions and `next_run_at` are authoritative SQLite state. Executable scheduler jobs use the
in-memory job store and are reconstructed from enabled recurring rules after database migration and
seeding at every startup. This avoids persisting opaque callable state.

If a recurring rule's stored next run is in the past at restart, the service performs at most one
catch-up attempt for that scheduled timestamp, then calculates the next occurrence. Job settings
coalesce late fires, limit each rule to one running instance, and use a one-hour misfire grace
window. A separate one-minute local scan evaluates approaching events and overdue tasks. Shutdown
stops new scheduler work without waiting for a long-running thread.

In test environments the scheduler is disabled and reconciliation is exercised explicitly. The
`GET /api/v1/automation/scheduler` endpoint reports runtime state, scheduled rule IDs, and next
wakeup without changing anything.

## Execution logs and idempotency

Every rule evaluation receives a source key: for example a transaction UUID, event start, task due
timestamp, commitment revision/warning code, or scheduled minute. The service hashes rule ID,
trigger type, and source key into an idempotency key protected by a database unique constraint.
Repeated dispatch returns the first execution and cannot repeat the action. Logs record trigger
context, condition results, action result, status (`succeeded`, `skipped`, or `failed`), error text,
and completion time. Logs remain after a rule is soft-deleted for audit history.

Actions and their success log commit together. A failed action rolls back its domain writes before
a failed log is recorded. Rule CRUD uses optimistic revisions. Scheduler metadata does not bypass
user-edit conflict checks.

## Security boundaries and limitations

- Rules cannot access the filesystem, network, environment, secrets, SQL, or arbitrary domain
  fields.
- Local notifications are database records; there is no operating-system push integration.
- There is no sandbox for arbitrary code because arbitrary code is never accepted.
- The API still trusts the person/process with loopback access; authentication and CSRF hardening
  remain deferred.
- Scheduler availability follows the API process. A machine that is powered off cannot execute
  rules until the next startup catch-up.
- System clock or timezone database changes can alter future wall-clock occurrences. Stored UTC
  execution keys prevent replay of an already-recorded occurrence.

CRUD, preview/test, execution history, notification, and scheduler endpoints are under
`/api/v1/automation`. Example rule payloads are in `data/demo/automation-rules.json`.
