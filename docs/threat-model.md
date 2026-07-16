# Threat model

## Scope and system model

LocalLife OS is a local, single-user browser application. A Next.js process on loopback port 3000
calls a FastAPI process on loopback port 8000. FastAPI stores data in SQLite and confined local
directories. There is no remote identity provider, cloud synchronization, collaboration boundary,
or public deployment in scope.

## Protected assets

- Notes, tasks, projects, calendar details, commitments, scenarios, and timeline history
- Financial accounts, transaction descriptions, amounts, budgets, subscriptions, and goals
- Attachment and original import bytes
- Preferences, timezone, and local workflow metadata
- Backup plaintext, backup passwords, and derived encryption keys
- Database integrity, backup/restore integrity, and deletion intent
- Availability of the local workspace and launcher processes

## Trust boundaries

```text
Public Internet (untrusted and unnecessary)
          X
          |
Browser origin :3000 ---- loopback HTTP ---- FastAPI :8000
     |                                          |
Cache Storage (shell only)              SQLite + local files
                                                |
                                      Imported files / backups
                                             (untrusted)
```

The browser/backend boundary is not an authentication boundary. CORS, Origin enforcement, CSP,
trusted Host values, and loopback binding reduce drive-by browser and DNS-rebinding attacks, but a
same-user process can call the API directly. Imported ICS/CSV files, attachment filenames, and
backup containers cross untrusted parsing/file boundaries and are validated before use.

## Local attacker assumptions

The application assumes the operating-system user account, Python/Node installations, repository
code, installed dependencies, and browser profile are trusted. An attacker who can execute as the
same OS user can read the unencrypted live database and files, inject requests into loopback,
replace code, inspect process memory, or tamper with unencrypted backups. LocalLife OS cannot defend
against an administrator/root attacker, compromised kernel, malicious browser extension with broad
permissions, or physical disk acquisition without OS/device encryption.

The privacy screen covers casual unattended-screen access only. It is deliberately not described
as login, authorization, or OS-grade credential protection.

## Threat analysis

| Component / threat | Risk | Mitigations | Residual limitation |
| --- | --- | --- | --- |
| Browser spoofing a trusted origin | Medium | Exact loopback CORS and Origin allowlist; no credentials; CSP | Same-user code can omit Origin and call the API |
| DNS rebinding / hostile Host | Medium | trusted-host allowlist and fixed loopback API base URL | Compromised local DNS/browser remains in the local trust base |
| Public/LAN exposure | High | native host validation, launcher fixed to `127.0.0.1`, Compose host mappings | Container listens on all interfaces only inside its private network |
| Outbound data exfiltration | High | no integrations; CSP; external URL scans; Python socket audit guard on by default | Explicit development override or compromised dependency can weaken policy |
| Service-worker disclosure | High | only shell/static GETs cached; cross-origin, API, and non-GET requests bypass cache | Browser HTTP cache behavior outside application Cache Storage is browser-controlled |
| Sensitive logging | Medium | access log disabled; record-factory redaction; no request bodies; exception type only | Third-party/native crash tooling outside this app is not controlled |
| Path traversal in attachments/imports | High | plain filename rules, resolved-child checks, generated storage names, database constraints | File content may still be malicious when opened by another application |
| Malicious import parser payload | Medium | byte/row limits, strict encodings/delimiters/types, no macro execution, preview before apply | Pandas/icalendar/parser vulnerabilities remain supply-chain risks |
| CSV formula injection | High on export/open | Review CSV prefixes `=`, `+`, `-`, `@`, tab, and carriage return with an apostrophe | Original bank CSV remains unmodified and untrusted |
| Backup path traversal / zip bomb | High | member-name, symlink, duplicate, entry-count, size, and resolved-path validation; no `extractall` | Configured 2 GiB container limit still consumes local resources |
| Backup tampering | High | SHA-256 per file; manifest/member equality; AES-GCM authentication when encrypted | An unencrypted attacker can replace data and recalculate the manifest |
| Wrong backup password | Medium | generic AES-GCM authentication failure; no partial restore | Password recovery is impossible by design |
| Restore interruption/corruption | High | full verify and schema check first; automatic safety backup; staged files; atomic rename; rollback | Power loss across multiple filesystem renames is not a single atomic transaction |
| Database theft | High | local-only location documentation; OS permissions | Live SQLite is not application-encrypted; use full-disk encryption |
| Destructive deletion spoofing | High | exact typed phrase and separate backup-deletion checkbox; staged file rollback | Same-user direct API callers can still send the exact request |
| Denial of service | Medium | size/row/entry limits, loopback scope, bounded Argon2 parameters | Same-user process can fill disk, consume CPU, or kill processes |

## Malicious imports

ICS and CSV are treated as untrusted data. Filenames must be simple local names with the expected
extension. Files are read only up to the configured limit; CSV rejects binary NUL data, unsupported
encoding/delimiter, excessive rows, duplicate/empty headers, invalid dates/currencies/amounts, and
unsafe mappings. Import is previewed before an explicit selected apply. Automation actions remain a
fixed allowlist and cannot run shell, SQL, network, or arbitrary code. The original files are not
sanitized; opening them externally remains the user's responsibility.

## Backup and restore recovery

Encrypted backup headers are authenticated as AES-GCM associated data. The payload is not accepted
until decryption, manifest parsing, member validation, and every size/checksum comparison succeeds.
Restore accepts only the exact Alembic schema head supported by the running version. It then creates
a verified safety backup and stages both database and attachments. If activation fails, preserved
database and attachment paths are swapped back. If automatic rollback itself fails, the error
returns preserved paths and the operator follows [backup-format.md](backup-format.md#manual-recovery).

## Limitations and non-goals

- No multi-user authentication, authorization, collaboration, remote access, or public hosting
- No encryption of the live SQLite database, live attachments, imports, or launcher logs
- No OS keychain integration, secure enclave, memory locking, or password recovery
- No malware scanning, attachment content disarm, parser sandbox, or signed software update system
- No forensic secure erase guarantee
- No defense against same-user malware, administrator/root, compromised browser/extension,
  compromised dependency, physical memory attack, or stolen unlocked device
- No claim that HTTP on loopback provides transport encryption; local TLS is not required for this
  single-device design

Security depends on keeping the device, OS user account, browser profile, dependencies, and
repository trustworthy and on using OS screen lock plus full-disk encryption.
