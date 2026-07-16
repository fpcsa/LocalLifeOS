# LocalLife OS backup format

## Overview

LocalLife OS backup files use the `.llbackup` extension and format version 1. A backup is either a
plain ZIP container or an authenticated encrypted envelope containing that ZIP. Creation uses
SQLite's online backup API while attachment mutation is held by the process-local storage lock, so
the database snapshot and attachment directory describe one application point in time.

## Inner container

The ZIP contains only regular files with POSIX-style relative names:

```text
manifest.json
database/locallife.db
preferences.json
attachments/<workspace-generated paths...>
```

`manifest.json` contains:

- `format: "locallife-backup"`
- `format_version: 1`
- application version and UTC creation time
- exact Alembic `schema_revision`
- encryption flag
- database and preferences member names
- non-secret workspace/preference metadata used for preview
- every payload member's path, kind, uncompressed size, and SHA-256 checksum

The manifest is limited to 1 MiB. Verification rejects missing/extra/duplicate members, directory
entries, symlinks, absolute paths, `..`, drive/colon components, backslashes, NULs, more than 100,000
members, mismatched sizes, mismatched checksums, and total expanded data beyond the configured
`LOCALLIFE_MAX_BACKUP_BYTES` limit. Restore streams validated members individually and never calls
`extractall`.

For an unencrypted container, the file begins with the ordinary ZIP `PK` signature. SHA-256 detects
accidental corruption or tampering that does not also replace the manifest. It is not a signature:
an attacker who can rewrite the whole unencrypted container can calculate new checksums.

## Password-protected envelope

An encrypted file has this binary layout:

```text
8 bytes   ASCII magic LLOSBAK1
4 bytes   unsigned big-endian JSON header length
N bytes   canonical UTF-8 JSON header
rest      AES-256-GCM ciphertext and 128-bit authentication tag
```

The canonical header declares envelope format/version, cipher, creation time, schema revision, a
16-byte random salt, a 12-byte random nonce, and Argon2id parameters. Defaults are Argon2 version 19,
64 MiB memory, time cost 3, parallelism 4, and a 32-byte derived key. Parameters are persisted so
future versions can read the file; restore bounds them before derivation to prevent hostile resource
settings. AES-GCM authenticates the whole header prefix as associated data and encrypts the complete
inner ZIP. Every backup uses fresh OS-random salt and nonce.

The implementation uses `argon2-cffi` and `cryptography` rather than custom cryptographic
primitives. Password input is hidden in the CLI; automation can use a protected local password file
instead of a process-list-visible command argument. The password, key, and plaintext are never
logged. Mutable temporary password/key buffers are overwritten on a best-effort basis, but Python
and OS memory behavior is not claimed to provide guaranteed memory erasure. There is no password
recovery.

## Creation and success criteria

1. Create a confined random temporary directory.
2. Use SQLite backup plus `PRAGMA quick_check` for the database snapshot.
3. Read schema and preference metadata from the snapshot.
4. Hash database, preferences JSON, and each attachment.
5. Write manifest and payload ZIP.
6. Optionally derive the key and encrypt/authenticate the ZIP.
7. Reopen the output, decrypt when applicable, validate every member, and recompute every checksum.
8. Atomically rename the verified temporary file to its final backup name.

No API or CLI success is returned before step 7 succeeds.

## Inspection and restore preview

`locallife restore <path>` reads envelope metadata, prompts for a password when required, verifies
the authenticated payload, displays creation time/schema/encryption state, and requests confirmation.
Restore refuses any schema revision other than the application's current Alembic head. This exact
match is conservative: migrate the application to a compatible release before restoring an older
backup rather than silently transforming an untrusted archive.

The native launcher requires web/API processes to be stopped before restore because Windows does
not allow a live SQLite file to be replaced reliably.

## Restore and rollback

1. Fully inspect and verify source container and checksums.
2. Validate exact schema compatibility.
3. Extract regular members to a confined runtime staging directory and run `PRAGMA quick_check`.
4. Create and verify an automatic `pre-restore` safety backup of current data. If the source was
   encrypted, the safety backup uses the same supplied password.
5. Copy the candidate database to the data filesystem, retain current database/attachment rollback
   copies, then atomically rename staged attachments and database into place.
6. Run `PRAGMA quick_check` on the activated database.
7. Remove rollback files only after success.

Any exception after activation begins swaps the preserved original database and attachments back.
The safety backup remains in `data/backups` whether restore succeeds or fails.

## Manual recovery

If LocalLife OS reports `restore_recovery_required`, stop both services and do not delete any
`.restore-current-*` paths listed in the error.

1. Copy the entire `data/` directory to another local directory before changing anything.
2. Identify the preserved `.restore-current-<id>.db` and
   `.restore-current-<id>-attachments` paths from the error.
3. Move the current `locallife.db` and `attachments/` aside; do not overwrite them.
4. Rename the preserved database to `locallife.db` and the preserved directory to `attachments/`.
5. Run `locallife doctor` and then create a new verified backup.
6. If preserved paths are incomplete, restore the automatic `pre-restore` `.llbackup` through the
   normal command.

Keep the failed source, safety backup, and copied `data/` directory until the workspace has been
opened and checked.
