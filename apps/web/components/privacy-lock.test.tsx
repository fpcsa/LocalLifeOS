import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PrivacyLock } from "@/components/privacy-lock";
import { getPreferences } from "@/lib/api/connected";
import { useUiStore } from "@/stores/ui-store";

vi.mock("@/lib/api/connected", () => ({
  getPreferences: vi.fn(),
}));

describe("PrivacyLock", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useUiStore.setState({ privacyLocked: false });
    vi.mocked(getPreferences).mockResolvedValue({
      id: "00000000-0000-4000-8000-000000000002",
      workspace_id: "00000000-0000-4000-8000-000000000001",
      timezone: "UTC",
      locale: "en",
      currency_code: "EUR",
      week_starts_on: 1,
      theme: "system",
      session_timeout_minutes: 1,
      revision: 1,
      created_at: "2026-07-16T00:00:00Z",
      updated_at: "2026-07-16T00:00:00Z",
    });
  });

  it("expires an inactive session and explains the privacy boundary", async () => {
    window.localStorage.setItem("locallife.last-activity", String(Date.now() - 61_000));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PrivacyLock>
          <main>Private workspace</main>
        </PrivacyLock>
      </QueryClientProvider>,
    );

    const dialog = await screen.findByRole("dialog", { name: "Privacy screen locked" });
    expect(dialog).toHaveTextContent("not user authentication");
    fireEvent.click(screen.getByRole("button", { name: "Unlock on this device" }));
    expect(screen.queryByRole("dialog", { name: "Privacy screen locked" })).not.toBeInTheDocument();
    expect(screen.getByText("Private workspace")).toBeVisible();
  });
});
