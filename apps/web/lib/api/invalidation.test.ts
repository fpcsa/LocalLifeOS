import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { queryKeys } from "./query-keys";
import { invalidateDemoWorkspaceData, invalidateScenarioAppliedData } from "./invalidation";

function seededClient() {
  const client = new QueryClient();
  client.setQueryData(queryKeys.tasks.list(), []);
  client.setQueryData(queryKeys.calendar.events({ month: "2026-07" }), []);
  client.setQueryData(queryKeys.finance.accounts, []);
  client.setQueryData(queryKeys.goals.list, []);
  client.setQueryData(queryKeys.commitments.list(), []);
  client.setQueryData(queryKeys.timeline.list(), []);
  client.setQueryData(queryKeys.system.preferences, { timezone: "UTC" });
  return client;
}

describe("cross-domain cache invalidation", () => {
  it("invalidates every primary domain affected by scenario acceptance", async () => {
    const client = seededClient();

    await invalidateScenarioAppliedData(client);

    for (const key of [queryKeys.tasks.list(), queryKeys.calendar.events({ month: "2026-07" }), queryKeys.finance.accounts, queryKeys.goals.list, queryKeys.commitments.list(), queryKeys.timeline.list()]) {
      expect(client.getQueryState(key)?.isInvalidated).toBe(true);
    }
    expect(client.getQueryState(queryKeys.system.preferences)?.isInvalidated).toBe(false);
  });

  it("invalidates all cached domains after the demo replaces workspace data", async () => {
    const client = seededClient();

    await invalidateDemoWorkspaceData(client);

    expect(client.getQueryCache().getAll().every((query) => query.state.isInvalidated)).toBe(true);
  });
});
