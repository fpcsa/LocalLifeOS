import type { components } from "@locallife/shared-types";

export function defaultSchedulingScope(
  planningStartAt: string,
  planningEndAt: string,
): components["schemas"]["SchedulingScopeInput"] {
  return {
    planning_start_at: planningStartAt,
    planning_end_at: planningEndAt,
    solver_time_limit_seconds: 2,
    policy: {
      working_hours: Array.from({ length: 5 }, (_, weekday) => ({
        weekday,
        start_time: "09:00:00",
        end_time: "17:00:00",
      })),
      personal_availability_windows: [],
      minimum_focus_block_minutes: 30,
      maximum_scheduled_minutes_per_day: 480,
      objective_weights: {
        scheduled_task: 1_000_000,
        priority: 100_000,
        preferred_time: 10_000,
        earlier_start: 1,
        fragmentation: 1,
      },
    },
  };
}
