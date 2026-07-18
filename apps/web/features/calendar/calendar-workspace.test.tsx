import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listCalendarConflicts, listCalendarEvents } from "@/lib/api/calendar";
import { applySchedule, getPreferences } from "@/lib/api/connected";
import { listTasks, suggestTaskSchedule } from "@/lib/api/productivity";

import { CalendarWorkspace } from "./calendar-workspace";

vi.mock("@fullcalendar/react", () => ({ default: () => <div>Calendar view</div> }));
vi.mock("@fullcalendar/daygrid", () => ({ default: {} }));
vi.mock("@fullcalendar/interaction", () => ({ default: {} }));
vi.mock("@fullcalendar/list", () => ({ default: {} }));
vi.mock("@fullcalendar/timegrid", () => ({ default: {} }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/api/calendar", () => ({
  listCalendarConflicts: vi.fn(),
  listCalendarEvents: vi.fn(),
  moveCalendarEvent: vi.fn(),
  resizeCalendarEvent: vi.fn(),
}));
vi.mock("@/lib/api/connected", () => ({ applySchedule: vi.fn(), getPreferences: vi.fn() }));
vi.mock("@/lib/api/productivity", () => ({ listTasks: vi.fn(), suggestTaskSchedule: vi.fn() }));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("CalendarWorkspace schedule suggestions", () => {
  beforeEach(() => {
    vi.mocked(getPreferences).mockResolvedValue({ timezone: "Europe/Rome", locale: "en-IE" } as Awaited<ReturnType<typeof getPreferences>>);
    vi.mocked(listCalendarEvents).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(listCalendarConflicts).mockResolvedValue([]);
    vi.mocked(listTasks).mockResolvedValue({
      data: [{ id: "task-1", title: "Prepare talk", revision: 1 }] as Awaited<ReturnType<typeof listTasks>>["data"],
      meta: { page: 1, page_size: 100, total_items: 1, total_pages: 1 },
    });
    vi.mocked(suggestTaskSchedule).mockResolvedValue({
      preview_id: "preview-1",
      solver_status: "optimal",
      placements: [{ task_id: "task-1", title: "Prepare talk", starts_at: "2026-07-20T08:00:00Z", ends_at: "2026-07-20T09:00:00Z", duration_minutes: 60, preference_satisfied: true }],
      unscheduled_tasks: [],
      conflicts: [],
    } as unknown as Awaited<ReturnType<typeof suggestTaskSchedule>>);
    vi.mocked(applySchedule).mockResolvedValue({ preview_id: "preview-1", applied_at: "2026-07-18T10:00:00Z", placements: [] });
  });

  it("requires review and applies the exact schedule preview", async () => {
    render(<CalendarWorkspace />, { wrapper: Wrapper });

    fireEvent.change(await screen.findByLabelText("Unscheduled task"), { target: { value: "task-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Suggest a time" }));
    expect(await screen.findByLabelText(/I reviewed this proposed placement/)).toBeInTheDocument();

    const apply = screen.getByRole("button", { name: "Apply reviewed schedule" });
    expect(apply).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I reviewed this proposed placement/));
    expect(apply).toBeEnabled();
    fireEvent.click(apply);

    await waitFor(() => expect(applySchedule).toHaveBeenCalledWith({ preview_id: "preview-1" }));
  });
});
