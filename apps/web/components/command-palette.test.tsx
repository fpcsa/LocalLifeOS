import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { globalSearch } from "@/lib/api/connected";
import { useUiStore } from "@/stores/ui-store";

import { CommandPalette } from "./command-palette";

const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/connected", () => ({ globalSearch: vi.fn() }));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("CommandPalette", () => {
  beforeEach(() => {
    push.mockReset();
    useUiStore.getState().setCommandPaletteOpen(true);
    vi.mocked(globalSearch).mockResolvedValue({ tasks: [], projects: [], notes: [], commitments: [], transactions: [] });
  });

  it("includes every application workspace in navigation", () => {
    render(<CommandPalette />, { wrapper: Wrapper });

    expect(screen.getByRole("button", { name: "Capacity" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Imports" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Automation" })).toBeInTheDocument();
  });

  it("opens a commitment search result at its real detail route", async () => {
    vi.mocked(globalSearch).mockResolvedValue({
      tasks: [],
      projects: [],
      notes: [],
      transactions: [],
      commitments: [{ id: "commitment-1", title: "Berlin conference" }] as Awaited<ReturnType<typeof globalSearch>>["commitments"],
    });
    render(<CommandPalette />, { wrapper: Wrapper });

    fireEvent.change(screen.getByLabelText("Search and navigate"), { target: { value: "Berlin" } });
    fireEvent.click(await screen.findByRole("button", { name: "Berlin conference" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/commitments/commitment-1"));
  });
});
