import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addCommitmentLink, createCommitment, getCommitmentAssessment } from "@/lib/api/connected";

import { CommitmentWizard } from "./commitment-wizard";

vi.mock("@/lib/api/connected", () => ({
  addCommitmentLink: vi.fn(), createCommitment: vi.fn(), createGoal: vi.fn(), getCommitment: vi.fn(), getCommitmentAssessment: vi.fn(), getPreferences: vi.fn().mockResolvedValue({ timezone: "Europe/Rome" }), listGoals: vi.fn().mockResolvedValue({ data: [], meta: {} }), updateCommitment: vi.fn(),
}));
vi.mock("@/lib/api/productivity", () => ({ createNote: vi.fn(), createTask: vi.fn(), listNotes: vi.fn().mockResolvedValue({ data: [], meta: {} }), listTasks: vi.fn().mockResolvedValue({ data: [{ id: "11111111-1111-4111-8111-111111111111", title: "Existing task" }], meta: {} }) }));
vi.mock("@/lib/api/calendar", () => ({ createCalendarEvent: vi.fn(), listCalendarEvents: vi.fn().mockResolvedValue({ data: [], meta: {} }) }));
vi.mock("@/lib/api/finance", () => ({ createPlannedTransaction: vi.fn(), listAccounts: vi.fn().mockResolvedValue({ data: [], meta: {} }), listPlannedTransactions: vi.fn().mockResolvedValue([]), listTransactions: vi.fn().mockResolvedValue({ data: [], meta: {} }) }));

const commitmentId = "22222222-2222-4222-8222-222222222222";
const assessment = {
  commitment: { id: commitmentId }, overall_status: "warning", warnings: [{ code: "time", message: "Some work remains unscheduled." }],
  time_capacity_status: { status: "warning", summary: "Review time." }, financial_capacity_status: { status: "ok", summary: "Within buffer." }, dependency_status: { status: "ok", summary: "No blockers." }, schedule_conflict_status: { status: "ok", summary: "No conflicts." }, goal_impact_status: { status: "not_applicable", summary: "No goals." }, deadline_status: { status: "ok", summary: "On time." },
};

function Wrapper({ children }: { children: ReactNode }) { const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }

describe("CommitmentWizard", () => {
  beforeEach(() => { vi.mocked(createCommitment).mockReset(); vi.mocked(addCommitmentLink).mockReset(); vi.mocked(getCommitmentAssessment).mockReset(); });
  it("creates a commitment, links selected evidence, and shows component assessment", async () => {
    vi.mocked(createCommitment).mockResolvedValue({ id: commitmentId } as Awaited<ReturnType<typeof createCommitment>>); vi.mocked(addCommitmentLink).mockResolvedValue({} as Awaited<ReturnType<typeof addCommitmentLink>>); vi.mocked(getCommitmentAssessment).mockResolvedValue(assessment as Awaited<ReturnType<typeof getCommitmentAssessment>>);
    render(<CommitmentWizard onClose={vi.fn()} onComplete={vi.fn()} open />, { wrapper: Wrapper });
    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: "Berlin conference" } }); fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(await screen.findByText("Existing task")).toBeInTheDocument(); fireEvent.click(screen.getByText("Existing task")); fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    fireEvent.click(screen.getByRole("button", { name: "Preview assessment" }));
    await waitFor(() => expect(createCommitment).toHaveBeenCalledTimes(1)); expect(addCommitmentLink).toHaveBeenCalledWith(commitmentId, expect.objectContaining({ entity_type: "task", entity_id: "11111111-1111-4111-8111-111111111111" })); expect(await screen.findByText("The plan has visible trade-offs")).toBeInTheDocument(); expect(screen.getByText("Some work remains unscheduled.")).toBeInTheDocument();
  });
});
