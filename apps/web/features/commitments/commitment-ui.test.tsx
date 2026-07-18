import { describe, expect, it } from "vitest";

import { entityHref } from "./commitment-ui";

describe("entityHref", () => {
  it("uses destinations that the target workspace can resolve", () => {
    expect(entityHref("calendar_event", "event-1")).toBe("/calendar?event=event-1");
    expect(entityHref("transaction", "transaction-1")).toBe("/finance#record-transaction-1");
    expect(entityHref("goal", "goal-1")).toBe("/goals#goal-goal-1");
    expect(entityHref("commitment", "commitment-1")).toBe("/commitments/commitment-1");
  });
});
