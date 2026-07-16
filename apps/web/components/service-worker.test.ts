import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

describe("service worker cache policy", () => {
  it("caches only local shell assets and leaves API traffic network-only", () => {
    const source = readFileSync(join(process.cwd(), "public", "sw.js"), "utf-8");
    expect(source).toContain('url.origin !== self.location.origin');
    expect(source).toContain('url.pathname.startsWith("/api/")');
    expect(source).toContain("request.method !== \"GET\"");
    expect(source).toContain("/_next/static/");
    expect(source).not.toMatch(/caches\.put\([^\n]*api/i);
  });
});
