import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "@/lib/api/system";

import { OfflineBanner } from "./offline-banner";

vi.mock("@/lib/api/system", () => ({ getHealth: vi.fn() }));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("OfflineBanner", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.mocked(getHealth).mockImplementation(() => new Promise(() => undefined));
  });

  it("preserves the browser offline event across a cached-shell reload", async () => {
    window.sessionStorage.setItem("locallife.browser-offline", "true");

    render(<OfflineBanner />, { wrapper: Wrapper });

    expect(await screen.findByText(/Local connection is offline/)).toBeInTheDocument();
  });
});
