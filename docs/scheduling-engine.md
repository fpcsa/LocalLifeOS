# Scheduling and capacity engine

## Scope

The scheduling engine turns existing local tasks, calendar events, dependencies, commitment
deadlines, availability, and workload policy into proposed task intervals. It runs entirely on the
device with OR-Tools CP-SAT. A solve is advisory: creating or reading a preview never changes a task
or calendar record. Only the explicit apply action can write accepted placements.

The engine does not replace manual scheduling. Existing task patch and bulk-reschedule operations
remain available, and their intervals become hard constraints for later previews.

## Pipeline

```text
bounded request + local source rows
               |
               v
evidence collector -> revisions, dependencies, occurrences, preferences, commitment
               |
               v
availability/capacity -> eligible free intervals and daily headroom
               |
               v
CP-SAT model -> best placement set within explicit wall-time limit
               |
               v
persisted preview -> placements, reasons, conflicts, risks, fingerprint
               |
               v
explicit apply -> stale check + atomic revision-checked task updates + timeline
```

Calendar collection reuses the established occurrence service. Recurring and all-day events are
expanded in range, and timed occurrences use their preparation, travel, and recovery buffers.
Cancelled events are excluded by the calendar service.

## Request policy and availability

A request supplies one to 100 tasks, an aware half-open planning range of at most 30 days, and a
solver time limit from 0.001 to 30 seconds. The default is two seconds. Policy fields are:

- weekly working windows expressed as weekday plus local wall start/end;
- additional absolute personal-availability windows;
- minimum focus-capable interval, default 30 minutes;
- maximum scheduled workload per local day, default 480 minutes; and
- configurable non-negative objective weights.

Weekly and personal windows form a union. An overnight weekly window has an end wall time earlier
than its start, such as Monday 22:00 through Tuesday 02:00. The engine clips the union to the
planning horizon, subtracts the union of hard busy intervals, and discards free intervals shorter
than the focus minimum before constructing task options.

## CP-SAT model

Time is represented as integer UTC minutes from the request's planning start. Each eligible task
has one optional fixed-duration interval, one presence Boolean, and one Boolean selector for each
eligible free-window/local-start-day option. Tasks are not split.

Hard constraints are:

- task start is no earlier than the horizon or `earliest_start_at`;
- task end is no later than its due time, the commitment target end, or the horizon, whichever is
  earliest;
- a placement stays inside one eligible free interval;
- proposed task intervals do not overlap one another;
- existing scheduled task intervals do not become options because they have already been removed
  from free time;
- finish-to-start and start-to-start dependency order is enforced;
- a selected dependent requires its selected prerequisite, unless an external prerequisite is
  already completed, started, or manually scheduled as required by its dependency type; and
- the duration charged to a local start day cannot exceed that day's remaining workload headroom.

Calendar events, event buffers, all-day occurrences, and existing scheduled tasks are therefore
hard constraints. `morning` (08:00-12:00), `afternoon` (12:00-17:00), and `evening`
(17:00-21:00) are soft local-time bands. A placement outside its requested band remains legal and
is returned with `preference_satisfied=false` and a soft conflict explanation.

## Objective and solver status

The objective is a transparent weighted sum. Defaults are:

```text
+ 1,000,000 * number of scheduled tasks
+   100,000 * priority score (low=1, medium=2, high=4, urgent=8)
+    10,000 * satisfied time-of-day preferences
-         1 * start minute from the horizon
-         1 * unused minutes in the selected free window
```

The defaults strongly favor placing more work, then higher-priority work and preferences, while
using earlier and tighter windows as tie-breakers. Callers may change weights; this is a weighted
optimization rather than a hidden lexicographic policy.

The solver uses one worker and random seed zero to keep search configuration deterministic. Every
request has a wall-time limit. `optimal` means optimality was proven; `feasible` is the best solution
found before proof or timeout and is returned without claiming optimality. `unknown`, `infeasible`,
and `model_invalid` produce no fabricated placement. With `unknown`, otherwise eligible tasks carry
the `solver_timeout` reason. `not_run` means no task reached the model because inputs already
explained why each was ineligible.

## Capacity calculations

Capacity is reported per local day, per local week, and for the whole horizon:

```text
raw free              = real local-day elapsed minutes - union(hard busy)
eligible free         = availability union - union(hard busy)
focus capable         = eligible-free intervals at least the focus minimum
daily workload room   = max daily minutes - hard busy minutes
available today       = min(focus-capable minutes, daily workload room)
remaining today       = max(0, available today - suggested task minutes)
required gap          = max(0, active unscheduled estimates - available horizon minutes)
```

Overlapping hard records count once in interval capacity. The report separately identifies existing
scheduled-task minutes and all already committed hard time. Weekly values are aggregates; there is
currently a daily cap, not a separate weekly cap.

Local day boundaries use the workspace IANA timezone and are converted to UTC, so a daylight-saving
day contributes its real 23 or 25 elapsed hours. A task may cross midnight when an eligible interval
does. For the current workload rule, its full duration is charged to its local start day; the
capacity response states this assumption explicitly.

## Explainability

Every requested task appears exactly once in either `placements` or `unscheduled_tasks`. Reasons
distinguish inactive/already-scheduled work, missing duration, horizon/deadline bounds, unavailable
or infeasible dependencies, hard conflicts, insufficient contiguous or total capacity, daily
limits, objective trade-offs, solver timeout, and invalid models. Each reason can include
contributing entity references and calculation details.

The preview also returns:

- hard calendar/existing-task conflicts and violated soft preferences;
- deadline risk with deadline, placement end, slack, and a stable level;
- daily/weekly capacity with required-minus-available minutes;
- solver status, proof flag, duration, objective components, and best bound; and
- explicit model and capacity assumptions.

For example, an all-day event that removes an otherwise eligible day yields both
`hard_calendar_conflict` and `insufficient_contiguous_capacity`. If two equal-duration tasks compete
for one remaining window, the higher priority can be placed while the other reports capacity or
objective trade-off reasons. A morning-preferred task placed in afternoon-only personal
availability is legal but returns a soft conflict.

## Preview consistency and atomic apply

The preview stores its request, complete response, expiry, and a canonical SHA-256 fingerprint over
the constraint-defining source snapshot. The snapshot covers selected task revisions and schedule
fields, dependency rows and prerequisite revisions, overlapping manual task schedules, calendar
event revisions, workspace timezone/week-start preferences, and the optional commitment revision
and target end.

Apply recollects the same sources. A different fingerprint returns
`stale_scheduling_preview` (HTTP 409); expired and already-applied previews have separate conflict
codes. A caller may accept every placement or an explicit non-empty subset. Each task update matches
the revision captured by its placement. All task intervals, `task_schedule_applied` timeline events,
and the preview applied timestamp commit together. Any failure rolls the complete operation back.

The default preview lifetime is 60 minutes and can be changed from one minute to one day with
`LOCALLIFE_SCHEDULING_PREVIEW_TTL_MINUTES`.

## API surface and bounded fixtures

| Method and path | Purpose |
| --- | --- |
| `POST /api/v1/scheduling/preview` | Multi-task preview |
| `POST /api/v1/scheduling/apply` | Atomic placement acceptance |
| `GET /api/v1/scheduling/capacity` | Workspace or commitment capacity report |
| `GET /api/v1/scheduling/explanations/{preview_id}` | Persisted explanation projection |
| `POST /api/v1/tasks/{task_id}/schedule-suggestions` | Single-task preview |
| `POST /api/v1/commitments/{commitment_id}/schedule-preview` | Linked-task commitment preview |

Acceptance fixtures include conference and hackathon commitments. The benchmark catalog defines
10-task/20-event, 50-task/100-event, and 100-task/200-event scenarios, culminating in the full
30-day supported horizon. The automated maximum fixture uses a one-second solver limit and verifies
that all 100 tasks are accounted for even when optimality is not proven.

## Deferred work

There is no automatic calendar mutation, background rescheduler, task splitting, location-aware
travel calculation, learned duration estimate, probabilistic forecast, or runtime AI. Weekly
capacity limits and user-interface workflows require later product goals.
