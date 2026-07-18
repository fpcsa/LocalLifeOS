import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "./query-keys";

/** Refresh every primary domain that a scenario acceptance can mutate atomically. */
export async function invalidateScenarioAppliedData(queryClient: QueryClient): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.projects.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.finance.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.goals.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.commitments.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.scheduling.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.timeline.all }),
  ]);
}

/** Demo loading replaces records across the entire local workspace. */
export async function invalidateDemoWorkspaceData(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries();
}
