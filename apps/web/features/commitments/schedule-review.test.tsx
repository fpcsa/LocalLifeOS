import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { applySchedule, previewCommitmentSchedule } from "@/lib/api/connected";

import { ScheduleReview } from "./schedule-review";

vi.mock("@/lib/api/connected", () => ({ applySchedule: vi.fn(), previewCommitmentSchedule: vi.fn() }));

function Wrapper({ children }: { children: ReactNode }) { const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }

describe("ScheduleReview", () => {
  beforeEach(() => { vi.mocked(applySchedule).mockReset(); vi.mocked(previewCommitmentSchedule).mockReset(); });
  it("requires explicit review before applying proposed placements", async () => {
    vi.mocked(previewCommitmentSchedule).mockResolvedValue({ preview_id: "33333333-3333-4333-8333-333333333333", solver_status: "optimal", placements: [{ task_id: "task-1", title: "Prepare talk", starts_at: "2026-08-01T09:00:00Z", ends_at: "2026-08-01T10:00:00Z", duration_minutes: 60, preference_satisfied: true }], unscheduled_tasks: [], conflicts: [] } as unknown as Awaited<ReturnType<typeof previewCommitmentSchedule>>); vi.mocked(applySchedule).mockResolvedValue({ preview_id: "33333333-3333-4333-8333-333333333333", applied_at: "2026-07-15T12:00:00Z", placements: [] });
    render(<ScheduleReview commitmentId="commitment-1" timezone="UTC" />, { wrapper: Wrapper }); fireEvent.click(screen.getByRole("button", { name: "Calculate preview" })); expect(await screen.findByText("Prepare talk")).toBeInTheDocument(); const apply = screen.getByRole("button", { name: "Apply reviewed schedule" }); expect(apply).toBeDisabled(); fireEvent.click(screen.getByLabelText(/I reviewed every proposed placement/)); expect(apply).toBeEnabled(); fireEvent.click(apply); await waitFor(() => expect(applySchedule).toHaveBeenCalledWith({ preview_id: "33333333-3333-4333-8333-333333333333" }));
  });
});
