# Security boundaries

LocalLife OS is designed for one user on a loopback-only machine. The API and web ports are bound to
`127.0.0.1`, CORS accepts only explicit loopback origins, external runtime requests and telemetry
are rejected by settings, and browser API configuration rejects non-loopback hosts.

## Import and automation controls

- Import filenames, extensions, sizes, row counts, resolved storage paths, encodings, delimiters,
  dates, timezones, recurrence, accounts, categories, currencies, and amounts are validated.
- Original imports and normalized history remain inside the configured data directory.
- CSV review exports escape common spreadsheet-formula prefixes. Original source files remain
  unmodified and untrusted.
- ICS and CSV apply operations use preview fingerprints, optimistic revisions, atomic transactions,
  and database uniqueness constraints to prevent accidental replay or concurrent overwrite.
- Automation accepts typed triggers, allow-listed condition fields, fixed operators, and fixed
  actions only. It has no arbitrary-code, network, shell, SQL, or file action.
- Automation execution keys are database-unique and action writes commit atomically with success
  logs.

## Explicitly not implemented

Storage and backups are not encrypted. There is no user authentication, CSRF token, malware scan,
file signature validation, spreadsheet content disarm for original uploads, process isolation for
parsers, operating-system notification integration, remote bank/calendar authentication, or full
threat model. Anyone able to act as the local user or reach the loopback API can read and mutate the
workspace. Imports should be obtained from trusted sources and the data directory should be
protected with operating-system permissions and device encryption.

These limitations must remain visible in product claims. Backup reminders do not create or verify a
backup, and import duplicate detection does not establish the authenticity of financial records.
