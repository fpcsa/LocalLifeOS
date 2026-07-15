import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listAccounts, listCategories } from "@/lib/api/finance";
import {
  applyImport,
  listImportHistory,
  listMappingProfiles,
  previewCalendarImport,
} from "@/lib/api/imports-automation";

import { ImportsWorkspace } from "./imports-workspace";

vi.mock("@/lib/api/finance", () => ({ listAccounts: vi.fn(), listCategories: vi.fn() }));
vi.mock("@/lib/api/imports-automation", () => ({
  applyImport: vi.fn(),
  downloadCalendarExport: vi.fn(),
  listImportHistory: vi.fn(),
  listMappingProfiles: vi.fn(),
  mapCsvImport: vi.fn(),
  previewCalendarImport: vi.fn(),
  previewCsvImport: vi.fn(),
}));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("ImportsWorkspace", () => {
  beforeEach(() => {
    vi.mocked(listImportHistory).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(listMappingProfiles).mockResolvedValue([]);
    vi.mocked(listAccounts).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(listCategories).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(previewCalendarImport).mockResolvedValue({
      batch: { id: "batch-1", status: "previewed", new_count: 1, changed_count: 0, duplicate_count: 0, invalid_count: 1 },
      columns: [],
      rows: [
        { id: "row-1", row_number: 1, status: "new", included: true, duplicate_kind: null, raw_data: { summary: "Weekly focus" }, normalized_data: { title: "Weekly focus", starts_at: "2026-07-20T07:00:00Z" }, issues: [] },
        { id: "row-2", row_number: 2, status: "invalid", included: false, duplicate_kind: null, raw_data: {}, normalized_data: {}, issues: [{ code: "invalid", message: "Missing title", field: null }] },
      ],
    } as unknown as Awaited<ReturnType<typeof previewCalendarImport>>);
    vi.mocked(applyImport).mockResolvedValue({ status: "applied", imported_count: 1 } as Awaited<ReturnType<typeof applyImport>>);
  });

  it("previews locally and applies only explicitly selected calendar rows", async () => {
    render(<ImportsWorkspace />, { wrapper: Wrapper });
    const file = new File(["BEGIN:VCALENDAR\r\nEND:VCALENDAR"], "calendar.ics", { type: "text/calendar" });
    fireEvent.change(screen.getByLabelText(/Choose an \.ics file/), { target: { files: [file] } });

    expect(await screen.findByText("Weekly focus")).toBeInTheDocument();
    expect(screen.getByLabelText("Include row 2")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Import 1" }));

    await waitFor(() => expect(applyImport).toHaveBeenCalledWith("calendar", "batch-1", ["row-1"]));
  });
});
