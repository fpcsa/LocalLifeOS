# Security boundaries

LocalLife OS is designed for one user on a loopback-only machine. The API and web ports are bound to
`127.0.0.1`, CORS and explicit browser-Origin checks accept only loopback origins, trusted-host
middleware rejects other Host values, the default Python socket guard blocks non-loopback outbound
access, telemetry is rejected by settings, and browser API configuration rejects non-loopback hosts.
API and web responses include CSP and related security headers.

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

## Backup, offline, and privacy controls

- The service worker caches only the application shell and local static GET resources; API and
  cross-origin requests are not intercepted, and API responses use `no-store`.
- Backups contain a consistent SQLite snapshot, attachment and preference data, schema metadata,
  a manifest, and SHA-256 checksums. Optional encryption uses Argon2id and AES-256-GCM. Restore
  verifies before a safety backup and staged activation with rollback.
- Native access logging is disabled, structured log redaction covers sensitive keys and queries,
  and unexpected errors omit exception text and bodies.
- The session timeout is a casual privacy screen and is not authentication.

## Explicitly not implemented

The live database, attachments, imports, runtime state, and unencrypted backup option are not
application-encrypted. There is no user authentication, CSRF token, malware scan, file signature
validation, spreadsheet content disarm for original uploads, parser process isolation, secure
erase, or remote bank/calendar authentication. Anyone able to act as the local user or directly
reach the loopback API can read and mutate the workspace. Imports should be obtained from trusted
sources and the data directory should be protected with OS permissions and device encryption.

These limitations remain visible in [privacy.md](privacy.md) and [threat-model.md](threat-model.md).
Automation backup reminders still do not create backups, and import duplicate detection does not
establish the authenticity of financial records.
