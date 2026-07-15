# Automation rules

LocalLife OS automation is a structured local rule system, never a code-execution system. A rule
contains one typed trigger, zero or more allow-listed AND conditions, and one fixed action. Unknown
fields and arbitrary Python, JavaScript, shell, SQL, URL, template, or expression content are
rejected.

Supported triggers are transaction creation, subscription amount change, event creation, event
approach, overdue task, commitment warning, and interval/daily/weekly recurring schedule. Supported
actions create a task, note, planned transaction, tag link, local notification, or local backup
reminder. Backup reminders do not perform a backup, and planned-transaction actions never post an
actual ledger transaction.

`POST /api/v1/automation/rules/{id}/test` evaluates sample trigger context, reports condition
results and the proposed action, and always returns `writes_performed=false`. Live evaluations use
a database-unique hash of rule, trigger, and source identity so replay returns the existing
execution without repeating its action. Action writes and successful audit logs commit together.

APScheduler runs inside the local API. SQLite rules and `next_run_at` are authoritative; executable
jobs are rebuilt at startup. One overdue recurring occurrence may be caught up after restart, then
the next wall-clock occurrence is calculated in the rule's IANA timezone. Approaching-event and
overdue-task rules are scanned once per minute while the API is running.

For the complete trigger context allow-lists, scheduler lifecycle, execution-log contract,
idempotency behavior, and security limitations, see [automation.md](automation.md). Example rule
payloads are available in `data/demo/automation-rules.json`.
