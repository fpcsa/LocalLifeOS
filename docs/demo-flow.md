# Signature demo flow

This walkthrough uses only the local browser application and public loopback APIs. Start LocalLife
OS, open `http://127.0.0.1:3000`, and confirm the top-bar status reads **Local service online**.

## Prepare the deterministic demo

1. Choose **Scenarios** in the left navigation.
2. Choose **Prepare signature demo**.
3. Wait for **Deterministic demo loaded locally**. The one local API call refreshes only records
   with reserved demo UUIDs and never deletes unrelated records.
4. The physical, remote, and skip Berlin options are selected automatically. If needed, select all
   three in the comparison picker and choose **Compare selected**.

Expected result: three calm side-by-side columns show projected cash flow, lowest balance, buffer
violations, required time, schedule conflicts, goal impact, unscheduled tasks, and commitment state.
The difference rows make the physical travel/cost trade-off visible without an aggregate score or
advisory claim. Repeating **Prepare signature demo** restores the canonical `2026.07` dataset.

## Inspect and safely accept a scenario

1. Select **Berlin · remote attendance** and inspect **Typed changes**.
2. Open its preview and review **Before / after** metrics.
3. Read **Exact acceptance plan** and every before/after field.
4. Observe that acceptance remains disabled until **I reviewed the exact before-and-after plan** is
   checked.
5. For a non-destructive judge demo, leave the review box unchecked. To demonstrate acceptance,
   check it and choose **Accept and apply exact plan**; acceptance revalidates the displayed fingerprint and all
   captured source revisions atomically.

Expected result: a changed source marks the branch **Stale** and blocks acceptance. A current branch
can only be accepted after the exact plan review. Preview and comparison never change workspace data.

## Follow the connected commitment story

1. Choose **Commitments**, search for **Berlin**, and open the conference commitment.
2. On **Overview**, inspect target, planned cost, required time, component states, warnings,
   assumptions, and deterministic actions.
3. Follow any warning contributor link to its underlying task, event, transaction, or goal.
4. Choose **Relationship graph**. Pan or select the keyboard-focusable nodes; the same linked
   records remain available as ordinary links around the graph.
5. Choose **Time**, then **Calculate schedule**. Review each proposed placement and unscheduled
   reason. Applying requires the explicit review checkbox.
6. Return to **Commitments** and open **OpenAI Build Week** and **Laptop purchase** to contrast a
   time-heavy plan with a finance-heavy plan.

Expected result: the detail never hides feasibility behind one score. Time, finance, conflicts,
dependencies, warning sources, assumptions, and actions are separately inspectable.

## Read capacity and history

1. Choose **Capacity**. Switch between daily and weekly ranges.
2. Compare raw free time, eligible focus time, already committed time, and remaining capacity in
   both the chart and its adjacent text table. Inspect committed balance and financial buffer.
3. Choose **Timeline**. Set the commitment filter to **Berlin conference**, optionally narrow entity
   types, and choose **Apply filters**.
4. Choose **Load older** to demonstrate reliable incremental pagination.

Expected result: activity is grouped by local date, and note/financial summaries stay compact and
privacy-limited until their record is opened. No step requires developer tools, a remote service,
an API key, or runtime AI.
