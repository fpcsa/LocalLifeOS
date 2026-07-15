import { describe, expect, it } from "vitest";

import { currencyDigits, formatMoney, majorToMinor } from "./format";

describe("money formatting", () => {
  it("keeps exact minor-unit semantics for two-decimal currencies", () => {
    expect(majorToMinor("12.34", "EUR")).toBe(1234);
    expect(formatMoney(1234, "EUR", "en-IE")).toContain("12.34");
  });

  it("uses currency-specific fraction digits", () => {
    expect(currencyDigits("JPY")).toBe(0);
    expect(majorToMinor("1250", "JPY")).toBe(1250);
    expect(formatMoney(1250, "JPY", "ja-JP")).toContain("1,250");
  });

  it("rejects invalid amount input", () => {
    expect(() => majorToMinor("not money", "EUR")).toThrow("Enter a valid amount");
  });
});
