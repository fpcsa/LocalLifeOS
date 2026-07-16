# Local privacy and offline operation

LocalLife OS is a single-user, on-device application. Its supported configuration requires no
account, API key, cloud database, analytics service, error-reporting SaaS, runtime AI, CDN, or
public Internet connection. The browser talks to a FastAPI process over loopback HTTP.

## Data locations

Native commands resolve relative paths from the repository root. Defaults are:

| Data | Default native location |
| --- | --- |
| SQLite database | `data/locallife.db` |
| Attachments | `data/attachments/` |
| Original import files | `data/imports/` |
| Backup containers | `data/backups/` |
| Launcher PID state and logs | `data/runtime/` |

Docker Compose persists the same layout under `/workspace/data` in the named
`locallife-os-data` volume. Settings displays the resolved host data path. Operating-system account
permissions and full-disk encryption remain the protection for the live database, attachment,
import, and runtime files; LocalLife OS does not encrypt its live SQLite database.

## Network boundary

- Native frontend and backend commands bind to `127.0.0.1` only. The launcher always supplies that
  address and rejects occupied ports before starting.
- Compose publishes both ports on host `127.0.0.1`. Services listen on `0.0.0.0` only inside the
  private container network, enabled by the explicit `LOCALLIFE_CONTAINER_MODE=true` setting.
- CORS accepts only configured loopback origins. Browser requests carrying any other `Origin` are
  rejected even when the browser would otherwise send a simple request.
- trusted-host middleware rejects Host-header values other than loopback names. This limits DNS
  rebinding and host-header abuse.
- CSP allows scripts, styles, images, fonts, workers, manifests, and connections only from the
  application and loopback services. No external font, script, image, analytics, or telemetry host
  is required.
- The Python outbound socket audit guard blocks non-loopback DNS resolution and connections while
  `LOCALLIFE_EXTERNAL_REQUESTS_ENABLED=false`, the default. Explicitly enabling it is intended only
  for development tests and weakens the offline boundary.

`scripts/check-external-assets.py` scans runtime frontend source and can inspect live HTML, CSP,
asset URLs, and redirects. `scripts/verify-offline-mode.py` additionally verifies port mappings,
native bind commands, service-worker presence, and API cache exclusion.

## Service-worker strategy

`apps/web/public/sw.js` caches a versioned application shell, the offline route, the local icon,
same-origin Next.js static assets, and shell-route HTML. Navigation uses network-first behavior with
a cached shell/offline fallback. Static local assets use cache-first behavior.

The worker deliberately does not intercept cross-origin requests, non-GET requests, or any
same-origin `/api/` request. The browser API client also sends `cache: "no-store"`, and API responses
carry `Cache-Control: no-store`. Personal notes, tasks, finances, attachments, preferences, and
other API payloads are therefore not placed in Cache Storage by LocalLife OS. The shell can render
when browser networking is disabled; reading or changing current workspace data still requires the
local backend to be reachable.

## Privacy screen and session timeout

Settings provides an inactivity timeout and a manual **Lock now** action. The full-screen privacy
shield hides and makes the underlying interface inert until the local user selects **Unlock on this
device**. Last-activity time is stored in browser local storage; no personal content is stored there.

This control prevents casual shoulder-surfing on an unattended screen. It is not authentication,
does not use an OS credential store, and does not prevent another process running as the same user
from calling the unauthenticated loopback API or reading files. Use the operating system's screen
lock and device encryption for that threat.

## Logs and temporary files

Native API access logging is disabled. A process-wide logging record factory and logger filters
redact password, passphrase, token, note-content, Markdown, payee, and transaction-description
assignments, plus URL query strings. Unhandled exceptions record only their type and request ID,
not exception text or request bodies. Services do not normally log note bodies or transaction
descriptions.

Attachment uploads stream into generated exclusive `.upload` files under the confined attachment
root, enforce the configured byte limit, flush to disk, atomically rename on success, and delete
temporary and target files on failure. Imports use exclusive confined files and byte/row limits.
Backup and restore workspaces use random temporary directories under the configured backup/runtime
roots and context-managed cleanup. Archive members, symlinks, absolute paths, parent traversal,
duplicate names, expanded size, and checksums are validated before restore.

## Backups and deletion

Backups always contain a consistent SQLite snapshot, attachments, preferences metadata, the schema
revision, a manifest, sizes, and SHA-256 checksums. A password is optional. Password-protected
backups use Argon2id to derive a 256-bit key and AES-256-GCM for authenticated encryption; the
password and derived key are never logged. Unencrypted backups detect accidental or unsophisticated
tampering through checksums but do not provide cryptographic authenticity against an attacker who
can replace both data and manifest.

Settings requires the exact phrase `DELETE ALL LOCAL DATA` before deleting the current workspace,
attachments, and import files. Backups are preserved unless the user separately opts to delete
them. File directories are staged for rollback until the database reset succeeds. This workflow
does not guarantee forensic erasure on SSDs, journaling filesystems, backups, or snapshots.

See [backup-format.md](backup-format.md) for the container and recovery procedure and
[threat-model.md](threat-model.md) for covered and uncovered attacks.
