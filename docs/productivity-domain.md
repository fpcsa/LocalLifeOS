# Productivity domain

Prompt 3 turns the productivity records introduced in the persistence foundation into complete
local API workflows. Routes remain thin: Pydantic schemas validate transport shape, services own
business rules and transaction boundaries, repositories own SQLModel queries, and Alembic owns
the SQLite schema.

## API surface

| Resource | Operations |
| --- | --- |
| `/api/v1/projects` | Create, read, update, archive, filter, sort, and paginate projects |
| `/api/v1/tasks` | CRUD, filters, subtasks, dependency actions, recurrence expansion, and bulk actions |
| `/api/v1/notes` | CRUD, SQLite full-text search, daily notes, note links, and backlinks |
| `/api/v1/attachments` | Safe multipart upload, metadata listing, download, and revision-checked deletion |
| `/api/v1/calendar/events` | CRUD, range query, recurrence expansion, move, and resize |
| `/api/v1/calendar/conflicts` | Buffer-aware conflict detection for a date-time range |

Every user-editable record uses optimistic revisions. A stale mutation returns HTTP 409 without
partially applying a bulk operation. Meaningful create, update, action, link, and delete operations
emit typed timeline events in the same database transaction as their primary change.

## Projects and progress

Projects have an active, on-hold, completed, or archived status and optional target start
and end dates. The end cannot precede the start. Archiving is an explicit action and archived
projects cannot receive new tasks or be reopened through the update route.

Progress is derived when a project is read; it is not stored. Active linked tasks count toward the
total, completed tasks count toward completion, and soft-deleted or cancelled tasks are excluded.
`progress_basis_points` ranges from 0 to 10,000, avoiding persisted floating-point percentages.

## Tasks, subtasks, and dependencies

Tasks support project and parent-task links, Markdown descriptions, status, priority, estimated and
actual minutes, due dates, optional scheduled intervals, tags, commitments, and recurrence. A
subtask inherits its parent's project when none is supplied and cannot cross project boundaries.
Parent traversal rejects both a proposed cycle and a pre-existing corrupt cycle.

Dependency edges are directed from a task to its prerequisite. The service builds the workspace
graph before insertion and rejects self-links, duplicates, and any edge that reaches the dependent
task again. Supported dependency semantics are:

- `finish_to_start`: blocked until the prerequisite is completed.
- `start_to_start`: blocked while the prerequisite remains in `todo`.

Derived response fields use the current UTC time and dependency state:

- `overdue` is true for an active task whose due time has passed.
- `blocked` is true when at least one direct dependency condition is unsatisfied.
- `schedulable` is true for an active, unblocked, unscheduled task with an estimate.

Status transitions are explicit. Todo and in-progress tasks can complete or cancel; completed and
cancelled tasks can return to todo. Completing stores `completed_at`; reopening clears it. Bulk
complete and bulk reschedule accept at most 100 unique revision-bearing items and run atomically.

Deleting a task soft-deletes it, removes dependency/tag/commitment and note/calendar domain links,
and detaches children rather than recursively deleting them. Attachment associations are retained
so local files remain discoverable and recoverable until explicitly deleted.

## Recurrence

Tasks and calendar events store one canonical, iCalendar-compatible RRULE string. The API accepts
either a canonical RRULE or the earlier typed frequency/interval/weekday/end representation, never
both. Typed input is converted to RRULE at the service boundary. Parsing and expansion use
`python-dateutil`; LocalLife OS does not maintain a custom recurrence parser.

Expansion uses a caller-supplied half-open range `[start, end)`, preserves timezone-aware starts,
and caps a response at 1,000 occurrences. Task occurrences use scheduled start or due time as
`DTSTART`; scheduled or estimated duration derives occurrence ends. Calendar occurrences preserve
the base event duration. Rules are evaluated locally and never require a network request.

## Notes, links, and search

Notes store Markdown source, title, optional unique active daily-note date, tags, commitments, and
typed links to supported domain records. Directed note links expose outbound links on the source
and backlinks on the target. Link creation rejects self-links and duplicates.

SQLite FTS5 indexes active note titles and Markdown using the Unicode tokenizer. Database triggers
keep the index synchronized on insert, update, soft deletion, and physical deletion. Searches are
workspace-scoped, tokenized into prefix terms, and can use FTS relevance order. No note content is
sent outside the local SQLite database.

Deleting a note is a revision-checked soft delete. Its note links, backlinks, tag/commitment links,
and note/calendar domain links are hard-deleted, and the FTS trigger removes it from search.
Attachment associations and bytes are deliberately retained to avoid implicit file loss; the
attachment API remains responsible for explicit file deletion.

## Attachments

Uploads stream in 1 MiB chunks to a generated temporary path beneath the configured attachment
root. The service validates a plain filename, media type, configured maximum size (25 MiB by
default), active target,
and resolved storage path. It computes SHA-256 and byte size while streaming, then atomically moves
the completed file to a generated UUID path before committing metadata and its typed entity link.
Failures remove both partial and target files.

Client filenames never become directory paths. Absolute paths, separators, drive prefixes, null
bytes, `.`/`..`, traversal segments, and overlong names are rejected. Download resolves the stored
relative path again and verifies confinement. Deleting an attachment soft-deletes its metadata,
hard-deletes all associations, and removes the local bytes. Deleting a linked domain record does
not delete attachment bytes implicitly.

## Calendar and conflict detection

Calendar events are either timed intervals with aware datetimes or all-day intervals with an
exclusive end date. They include status, category, plain local location, IANA timezone,
preparation/travel/recovery buffers, recurrence, commitments, attachments, and typed project/task/
note/goal links. Move preserves duration; resize preserves start. Both require the current revision.

Range queries expand recurrence only far enough to determine intersection and return each matching
event once. Cancelled events remain queryable but do not participate in conflict detection.

Conflict detection converts all-day boundaries from the event timezone to UTC and expands timed
and recurring events over the requested range. Its effective interval is:

```text
start - preparation - travel  ->  end + recovery
```

Two different events conflict when their effective half-open intervals overlap. The service uses
the requested IANA timezone or the workspace preference for local date boundaries. It ignores
self-overlap among occurrences of the same recurring event and returns the exact base and effective
times used for each conflict decision.
