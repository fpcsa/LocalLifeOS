# Local import and calendar export

LocalLife OS treats every import as a two-phase operation: **preview** persists a source fingerprint
and classified rows, while **apply** writes only the rows the user explicitly kept. Files and import
history stay beneath `data/imports`; no parser makes an external request.

## Supported formats

| Format | Supported input | Output |
| --- | --- | --- |
| iCalendar | `.ics`, RFC 5545 `VCALENDAR` containing `VEVENT` records | standards-compatible `.ics` for all or selected active events |
| Bank data | `.csv` encoded as UTF-8/UTF-8 with BOM or Windows-1252 | UTF-8 review CSV with spreadsheet-formula escaping |

The default limits are 25 MiB per file and 10,000 CSV data rows. Filenames must be simple basename
values with the expected extension. Stored paths are generated beneath the configured imports
directory and checked after resolution.

## Calendar import behavior

The `icalendar` parser reads timed and all-day events, summary, description, location, category,
status, UID, sequence, start/end or duration, timezone identifiers, and common RRULE recurrence.
Timed values are normalized to UTC while retaining the IANA timezone name; floating timestamps use
the workspace timezone. All-day end dates remain exclusive. Unsupported or malformed events are
reported as invalid rows without preventing valid siblings from being previewed.

Classification is deterministic:

- `new`: no active event has the imported UID;
- `changed`: the UID exists but the normalized content fingerprint differs;
- `duplicate`: UID and normalized fingerprint both match;
- `invalid`: required shape, timezone, range, or recurrence validation failed.

UID-less events receive a stable local UID derived from normalized content. Applying changed rows
requires the event revision captured at preview, so a concurrent local edit returns HTTP 409 rather
than being overwritten. Re-uploading byte-identical content returns the existing batch, and applying
an already-applied batch is a no-op. Calendar export includes UID, sequence, timezone components,
RRULE, status, text metadata, and LocalLife buffer extension fields.

## Bank CSV workflow

Delimiter detection is restricted to comma, semicolon, tab, and pipe. Encoding detection tries
UTF-8 with BOM, strict UTF-8, then Windows-1252; binary NUL bytes are rejected. Pandas reads every
column as text so bank identifiers, leading zeroes, and decimal parsing stay under application
control.

The mapping step supports date, description, signed amount or debit/credit, currency, account,
category, and external ID. Account, category, and currency may come from source columns or explicit
defaults. Date format, decimal separator, and signed-amount direction are stored in reusable,
revision-checked mapping profiles. Amounts are converted to integer ISO 4217 minor units; no binary
floating-point amount is persisted.

Exact duplicates match an existing external ID or import fingerprint and are excluded. Probable
duplicates match account, type, amount, and timestamp and are flagged but may be included after
review. The database's unique import fingerprint provides a final concurrency guard. Apply creates
all selected transactions and their timeline entries atomically; a stale selection changes nothing.

## Spreadsheet and local-file safety

Review CSV cells beginning with `=`, `+`, `-`, `@`, tab, or carriage return are prefixed with an
apostrophe before export. This mitigates formula execution when the generated review file is opened
in a spreadsheet. The original uploaded bank file is retained unchanged for local audit history and
must still be treated as untrusted input.

The application does not provide antivirus scanning, content-disarm, encrypted storage, or bank
signature verification. A valid local CSV or ICS file may still contain misleading human-readable
content. Preview classifications are assistance, not proof that a transaction or event is genuine.

## Public endpoints

- `GET /api/v1/imports` and `GET /api/v1/imports/{batch_id}`: history and row review.
- `POST /api/v1/imports/calendar/preview` and `POST .../{batch_id}/apply`: ICS phases.
- `GET /api/v1/imports/calendar/export.ics`: export all or repeated `event_id` selections.
- `POST /api/v1/imports/csv/preview`, `POST .../{batch_id}/map`, and `POST .../{batch_id}/apply`:
  bank phases.
- `/api/v1/imports/mapping-profiles`: revision-checked reusable mappings.
- `PATCH /api/v1/imports/rows/{row_id}`: persisted include/exclude selection.
- `GET /api/v1/imports/{batch_id}/rows.csv`: formula-safe local review export.

Sample files live in `data/demo/calendar.ics`, `bank-transactions.csv`, and
`sample-bank-debit-credit.csv`.
