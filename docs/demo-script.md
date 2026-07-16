# LocalLife OS demo script — 2 minutes 55 seconds

## Before the clock

1. Run `docker compose up --build` and wait for both services to become healthy.
2. Run `curl -X POST http://127.0.0.1:8000/api/v1/demo/load`.
3. Open `http://127.0.0.1:3000`, then visit each demo route once so the shell is cached.
4. Keep browser developer tools ready on the Network panel for the final offline proof.
5. Confirm the screen says **Local service online** and that no personal workspace is in use.

All names, merchants, money, notes, attachments, and events shown below are synthetic. There are no
demo credentials and no API key.

## 0:00–0:20 — One local picture of life

Screen action: open **Today**.

Narrate exactly:

> “LocalLife OS connects work, time, money, notes, goals, and commitments in one private local
> workspace. This Next.js interface and FastAPI service run on loopback; the data lives in local
> SQLite and files. There is no login, cloud database, telemetry, API key, or runtime AI request.”

Point to the system-status indicator, today sections, and textual warning/capacity summaries.

## 0:20–0:42 — Conflicts include the hidden time

Screen action: open **Calendar**, switch to **Agenda**, and show 20–21 July 2026.

Narrate exactly:

> “The synthetic calendar has at least two conflicts. The prototype block touches a dentist visit,
> but preparation, travel, and recovery buffers turn that boundary into a real conflict. A Berlin
> briefing also overlaps the household review. The agenda is the accessible text alternative to the
> visual calendar.”

Point to **Prototype deep work**, **Dentist appointment**, **Berlin travel briefing**, and
**Weekly household review**. Do not claim that color alone conveys their status.

## 0:42–1:02 — Money keeps its assumptions visible

Screen action: open **Finance** and show the July budget and savings summary.

Narrate exactly:

> “The workspace contains a fictional 3,200-euro salary, ordinary household expenses, two example
> subscriptions, and an Emergency fund goal. July Food spending is 410 euros against a 350-euro
> limit, so the budget report exposes a 60-euro shortfall. Amounts stay in integer minor units and
> currencies are never silently converted.”

These are the exact canonical demo facts: salary `€3,200.00`, Food actual `€410.00`, Food limit
`€350.00`, Emergency fund `€2,500.00 / €6,000.00`.

## 1:02–1:27 — A commitment is traceable evidence

Screen action: open **Commitments**, choose **Berlin conference**, and open **Review impact**. Briefly
show **overview**, then **graph**.

Narrate exactly:

> “A commitment is not another opaque record. Berlin links to its decision task and planning note.
> The deterministic assessment separates time, financial buffer, dependencies, calendar conflicts,
> goals, and deadline risk. Every warning names contributing records and assumptions; there is no
> black-box life score.”

Point to the ordinary record links beneath the relationship graph as its keyboard/text alternative.

## 1:27–2:02 — Compare first; mutate only after review

Screen action: open **Scenarios** and click **Prepare signature demo** if the comparison is not already
visible. Show the three Berlin cards, then open **Berlin · remote attendance**.

Narrate exactly:

> “Scenario mode overlays typed changes without touching primary records. Physical attendance asks
> for 1,450 euros and 1,200 minutes; remote asks for 120 euros and 360 minutes; skip asks for zero of
> both. Separate August and October laptop scenarios are also ready. Comparison stays responsive on
> the local demo dataset.”

Screen action: scroll to **Exact acceptance plan**, point to the before/after fields, check **I
reviewed the exact before-and-after plan**, then click **Accept and apply exact plan**.

Narrate exactly:

> “Acceptance sends the reviewed revision and fingerprint. The server applies the exact plan in one
> transaction or rejects it if any source record changed.”

## 2:02–2:28 — Backup is local and claims only what it does

Screen action: open **Settings**, go to **Backup**, enter label `judge-demo`, enter and confirm a
temporary password, then click **Create and verify backup**.

Narrate exactly:

> “A password-protected backup contains a consistent SQLite snapshot, attachments, preferences,
> schema metadata, and checksums. It uses Argon2id and AES-256-GCM and verifies itself before success.
> The live database is still plaintext—LocalLife does not mislabel the privacy screen or ordinary
> storage as encryption.”

Point to **Backup created and verified**. Do not reveal or reuse the temporary password.

## 2:28–2:47 — Offline proof

Screen action: in browser developer tools set Network to **Offline**, reload the page, and leave the
offline banner visible.

Narrate exactly:

> “The shell reloads offline because its local service worker caches only application shell and
> static assets. API responses, uploads, non-GET requests, and cross-origin resources are never
> cached. The banner is honest: the interface is available, but server-backed actions wait for the
> local service to return.”

Restore Network to **Online** after the proof.

## 2:47–2:55 — Impact and Codex/GPT-5.6

Screen action: return to **Today** or leave the offline proof visible.

Narrate exactly:

> “Codex and GPT-5.6 accelerated the typed architecture, migrations, UI, deterministic fixtures,
> adversarial tests, and verification scripts. Humans reviewed the privacy boundary, explainability,
> currency rules, mutation safety, and encryption claims. LocalLife’s impact is simple: see whether
> a commitment fits your real time and money before it becomes an irreversible problem—without
> giving your life data to a cloud service.”

Stop at 2:55. Do not open an untested feature or improvise a cloud/AI claim.
