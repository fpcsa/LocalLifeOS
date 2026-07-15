import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "@/lib/api/system";

import { SystemStatus } from "./system-status";

vi.mock("@/lib/api/system", () => ({
  getHealth: vi.fn(),
}));

const mockedGetHealth = vi.mocked(getHealth);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("SystemStatus", () => {
  beforeEach(() => {
    mockedGetHealth.mockReset();
  });

  it("shows the successful local service state", async () => {
    mockedGetHealth.mockResolvedValue({
      status: "ok",
      service: "LocalLife OS API",
      version: "0.1.0",
      timestamp: "2026-07-15T10:00:00Z",
    });

    render(<SystemStatus />, { wrapper: createWrapper() });

    expect(screen.getByText("Checking local service")).toBeInTheDocument();
    expect(await screen.findByText("Local service online")).toBeInTheDocument();
  });

  it("offers a retry and recovers after a local service error", async () => {
    mockedGetHealth
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
        status: "ok",
        service: "LocalLife OS API",
        version: "0.1.0",
        timestamp: "2026-07-15T10:00:00Z",
      });

    render(<SystemStatus />, { wrapper: createWrapper() });

    const retryButton = await screen.findByRole("button", {
      name: "Local service offline — retry",
    });
    fireEvent.click(retryButton);

    expect(await screen.findByText("Local service online")).toBeInTheDocument();
    expect(mockedGetHealth).toHaveBeenCalledTimes(2);
  });
});
