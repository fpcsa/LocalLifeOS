import { describe, expect, it } from "vitest";

import { localDateKey, localDayRange } from "./date-range";

describe("timezone-aware date ranges", () => {
  it("uses the configured timezone for date keys", () => {
    expect(localDateKey(new Date("2026-07-15T22:30:00Z"), "Europe/Rome")).toBe("2026-07-16");
  });

  it("preserves the 23-hour daylight-saving transition day", () => {
    const range = localDayRange("Europe/Rome", new Date("2026-03-29T12:00:00Z"));
    expect(range.start).toBe("2026-03-28T23:00:00.000Z");
    expect(range.end).toBe("2026-03-29T22:00:00.000Z");
    expect(new Date(range.end).getTime() - new Date(range.start).getTime()).toBe(23 * 60 * 60 * 1000);
  });
});
