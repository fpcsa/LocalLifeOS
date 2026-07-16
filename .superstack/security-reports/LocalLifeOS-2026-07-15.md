# LocalLife OS security review — 2026-07-15

## Audit profile

- Mode: Comprehensive, focused on Prompt 11 offline/privacy/backup/launcher scope
- Confidence gate: 2/10
- Stack: Next.js/TypeScript browser UI, FastAPI/Python API, SQLite, local files, Docker Compose
- Exposure: loopback ports 3000 and 8000 only; no public service, cloud identity, runtime AI, or SaaS
- Protected data: productivity records, financial records, notes, attachments, imports, preferences,
  backup plaintext/passwords/derived keys, and database/restore integrity

## Executive summary

No open Critical, High, or Medium findings remain after the implementation and remediation pass.
Known-advisory scans returned zero npm and Python vulnerabilities, targeted working-tree and Git
history scans found no credentials/private keys, and live browser verification observed no external
HTTP requests. The residual findings below are either a defense-in-depth CSP limitation or explicit
single-user/local-storage boundaries already documented for users.

Prompt 11 added and actively tested loopback/Host/Origin enforcement, a default-deny Python outbound
guard, no-store API behavior, shell-only service-worker caching, sensitive log redaction, confined
file handling, authenticated optional backup encryption, transactional restore safeguards, and a
loopback-only launcher. During the audit, Docker base images were pinned to immutable digests and
the API/web application processes were moved to unprivileged runtime users.

## Attack surface and trust boundaries

```text
Browser :3000 -- loopback HTTP -- FastAPI :8000 -- SQLite + confined local directories
    |                                |
shell/static Cache Storage      untrusted imports, attachments, and backup containers

Public Internet: denied by design and not required
```

The browser/backend boundary is protected against ordinary cross-origin and Host-header drive-by
traffic, but deliberately is not an authentication boundary. Same-OS-user processes, the browser
profile, installed dependencies, and the operating system are trusted. Backup/import parsing and
filesystem activation are the principal untrusted-data boundaries.

## Findings

### LOW CSO-001: CSP permits inline scripts and styles

- Confidence: 8/10
- Evidence: `apps/web/next.config.ts` includes `'unsafe-inline'` for `script-src` and `style-src`.
- Data flow: server-rendered Next.js pages emit framework bootstrap/style content that is allowed by
  this directive. No application `dangerouslySetInnerHTML`, `eval`, or `new Function` use was found.
- Impact: a future HTML/script injection defect would receive less protection than a nonce- or
  hash-based policy provides.
- Existing controls: all sources and connections remain limited to self/loopback; objects and
  frames are denied; user Markdown is not injected as raw HTML; no external requests were observed.
- Remediation: migrate production rendering to per-request nonces or supported hashes when the
  framework/build path can do so without weakening static/offline-shell behavior.
- Status: accepted defense-in-depth follow-up; not an exposed exploit by itself.

### INFO CSO-002: Same-user callers can access the unauthenticated loopback API

- Confidence: 10/10
- Evidence: the product is intentionally single-user and has no authentication layer.
- Impact: malware or another process running as the same OS user can read or mutate workspace data.
- Controls: loopback binding, trusted Host values, strict browser Origin/CORS checks, and documented
  use of OS account security/full-disk encryption.
- Status: accepted architecture boundary; the privacy screen is explicitly not authentication.

### INFO CSO-003: Live data and optional unencrypted backups are plaintext

- Confidence: 10/10
- Evidence: SQLite, attachments, imports, runtime logs, and backups without a password are ordinary
  local files.
- Impact: an attacker with filesystem access can read live data or replace an unencrypted backup and
  recalculate its manifest.
- Controls: documented paths/limitations, OS permissions, checksums for accidental corruption, and
  optional Argon2id/AES-256-GCM authenticated backup encryption.
- Status: accepted and prominently documented; full-disk encryption is recommended.

### INFO CSO-004: API container performs a minimal root ownership bootstrap

- Confidence: 10/10
- Evidence: the API entrypoint repairs an existing named volume once, then launches Uvicorn through
  `runuser`; live `docker compose top api` showed the Python/Uvicorn child under the unprivileged
  system UID. The web runtime used UID 1000.
- Impact: PID 1 remains the small privilege-drop helper so it can migrate pre-existing root-owned
  volumes; application code does not run as root.
- Controls: fixed entrypoint, fixed command, no public ports, and a one-time ownership marker.
- Status: accepted compatibility tradeoff.

### INFO CSO-005: Security verification is local rather than CI-enforced

- Confidence: 10/10
- Evidence: no repository `.github` workflow or equivalent CI pipeline is present.
- Impact: dependency/security/offline checks rely on the documented local verification commands.
- Controls: exact scripts and tests are committed; package locks and Python direct dependencies are
  pinned; container bases are digest-pinned.
- Status: operational follow-up for a future distribution workflow, not a runtime exposure.

## Supply-chain and secret review

- `npm audit` and `npm audit --omit=dev`: zero known vulnerabilities.
- `pip-audit -r apps/api/requirements.txt`: no known vulnerabilities.
- `pip check`: no broken requirements.
- Package lock is committed; Python direct runtime dependencies are exact-pinned.
- API base: `python:3.12-slim` pinned to
  `sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28`.
- Web base: `node:22-alpine` pinned to
  `sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2`.
- No credential-like high-confidence tokens, private-key blocks, or secret-named files were found in
  the working tree or Git history search.
- No runtime plugin, MCP, model, prompt execution, or LLM data-flow surface exists.

## STRIDE summary

| Category | Principal concern | Verified control |
| --- | --- | --- |
| Spoofing | hostile browser origin / DNS rebinding | exact Origin/CORS and trusted Host tests |
| Tampering | backup/archive/database replacement | AEAD, checksums, exact members, schema check, safety backup, rollback tests |
| Repudiation | destructive local action ambiguity | exact delete phrase, explicit backup choice, request IDs |
| Information disclosure | cache/log/path leakage | API no-store, shell-only cache, redaction tests, confined filenames/paths |
| Denial of service | oversized import/archive/KDF work | byte/row/entry/expanded-size limits and bounded Argon2 parameters |
| Elevation of privilege | public bind/container root | loopback publishing, config rejection, unprivileged app processes |

## Active verification evidence

- Backend suite passed all 78 tests, including wrong password, tampering, restore rollback, traversal,
  malicious CSV formula handling, session timeout, redaction, outbound guard, Host/Origin, and launcher
  lifecycle coverage.
- Frontend suite passed 14 tests; strict TypeScript, ESLint, and production build passed.
- Browser smoke passed all 13 routes at 1280, 768, and 375 pixels, with no unexpected console errors
  or external requests and a successful offline service-worker reload.
- Required external-asset, offline-mode, backup, and restore scripts passed in source/live modes.
- Digest-pinned images built; both Compose services became healthy on loopback; the application
  processes were verified as unprivileged; the stack was stopped without deleting its data volume.

## Summary

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 1 (average confidence: 8/10)
- INFO: 4 (average confidence: 10/10)
- False positives filtered: 8
- Mode: Comprehensive (2/10 gate)
