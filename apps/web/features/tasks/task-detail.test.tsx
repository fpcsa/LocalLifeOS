import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { applySchedule } from "@/lib/api/connected";
import { deleteTask, listTasks, suggestTaskSchedule } from "@/lib/api/productivity";
import type { Task } from "@/lib/api/types";

import { TaskDetail } from "./task-detail";

vi.mock("@/lib/api/productivity", () => ({
  addTaskDependency: vi.fn(),
  deleteTask: vi.fn(),
  listTasks: vi.fn(),
  suggestTaskSchedule: vi.fn(),
  updateTask: vi.fn(),
}));

vi.mock("@/lib/api/connected", () => ({
  applySchedule: vi.fn(),
}));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function task(): Task {
  return {
    actual_duration_minutes: null,
    blocked: false,
    child_count: 1,
    commitment_ids: ["12000000-0000-4000-8000-000000000003"],
    completed_at: null,
    created_at: "2026-07-18T07:00:00Z",
    dependencies: [],
    description_markdown: "A task with linked records.",
    due_at: "2026-07-20T10:00:00Z",
    earliest_start_at: null,
    estimated_duration_minutes: 30,
    id: "12000000-0000-4000-8000-000000000001",
    overdue: false,
    parent_task_id: null,
    preferred_time_of_day: "any",
    priority: "medium",
    project_id: "12000000-0000-4000-8000-000000000004",
    recurrence_rrule: null,
    revision: 7,
    schedulable: true,
    scheduled_end_at: null,
    scheduled_start_at: null,
    status: "todo",
    tag_ids: [],
    title: "Prepare Berlin brief",
    updated_at: "2026-07-18T08:00:00Z",
    workspace_id: "12000000-0000-4000-8000-000000000002",
  };
}

function schedulingPreview(placements = [{
  duration_minutes: 30,
  ends_at: "2026-07-19T09:30:00Z",
  preference_satisfied: true,
  starts_at: "2026-07-19T09:00:00Z",
  task_id: "12000000-0000-4000-8000-000000000001",
  title: "Prepare Berlin brief",
}]) {
  return {
    placements,
    preview_id: "12000000-0000-4000-8000-000000000099",
    unscheduled_tasks: [],
  } as unknown as Awaited<ReturnType<typeof suggestTaskSchedule>>;
}

describe("TaskDetail deletion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listTasks).mockResolvedValue({
      data: [],
      meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 },
    });
    vi.mocked(deleteTask).mockResolvedValue(undefined);
  });

  it("requires confirmation and deletes with the current revision", async () => {
    const currentTask = task();
    const onClose = vi.fn();
    render(
      <TaskDetail allTasks={[currentTask]} onClose={onClose} task={currentTask} timezone="UTC" />,
      { wrapper: Wrapper },
    );

    const detail = await screen.findByRole("dialog", { name: currentTask.title });
    fireEvent.click(within(detail).getByRole("button", { name: "Delete task" }));

    const confirmation = await screen.findByRole("dialog", {
      name: `Delete “${currentTask.title}”?`,
    });
    expect(within(confirmation).getByText(/subtasks will become top-level tasks/i)).toBeVisible();
    expect(deleteTask).not.toHaveBeenCalled();

    fireEvent.click(within(confirmation).getByRole("button", { name: "Delete task" }));

    await waitFor(() => expect(deleteTask).toHaveBeenCalledWith(currentTask.id, 7));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });

  it("keeps the confirmation open and announces a deletion conflict", async () => {
    vi.mocked(deleteTask).mockRejectedValueOnce(
      new Error("The task changed. Reload it before deleting."),
    );
    const currentTask = task();
    render(
      <TaskDetail allTasks={[currentTask]} onClose={vi.fn()} task={currentTask} timezone="UTC" />,
      { wrapper: Wrapper },
    );

    const detail = await screen.findByRole("dialog", { name: currentTask.title });
    fireEvent.click(within(detail).getByRole("button", { name: "Delete task" }));
    const confirmation = await screen.findByRole("dialog", {
      name: `Delete “${currentTask.title}”?`,
    });
    fireEvent.click(within(confirmation).getByRole("button", { name: "Delete task" }));

    const alert = await within(confirmation).findByRole("alert");
    expect(alert).toHaveTextContent("Couldn’t delete this task");
    expect(alert).toHaveTextContent("The task changed. Reload it before deleting.");
    expect(confirmation).toBeVisible();
  });
});

describe("TaskDetail scheduling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listTasks).mockResolvedValue({
      data: [],
      meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 },
    });
    vi.mocked(suggestTaskSchedule).mockResolvedValue(schedulingPreview());
    vi.mocked(applySchedule).mockResolvedValue({
      applied_at: "2026-07-18T10:00:00Z",
      placements: schedulingPreview().placements,
      preview_id: "12000000-0000-4000-8000-000000000099",
    });
  });

  it("requires review before applying the suggested task placement", async () => {
    const currentTask = task();
    render(
      <TaskDetail allTasks={[currentTask]} onClose={vi.fn()} task={currentTask} timezone="UTC" />,
      { wrapper: Wrapper },
    );

    const detail = await screen.findByRole("dialog", { name: currentTask.title });
    fireEvent.click(within(detail).getByRole("button", { name: "Suggest schedule" }));

    const apply = await within(detail).findByRole("button", { name: "Apply reviewed schedule" });
    expect(apply).toBeDisabled();
    fireEvent.click(within(detail).getByLabelText(/I reviewed this proposed placement/));
    expect(apply).toBeEnabled();
    fireEvent.click(apply);

    await waitFor(() => expect(applySchedule).toHaveBeenCalledWith({
      preview_id: "12000000-0000-4000-8000-000000000099",
    }));
  });

  it("keeps a failed preview visible and offers a fresh calculation", async () => {
    vi.mocked(applySchedule).mockRejectedValueOnce(
      new Error("The preview is stale because the task changed."),
    );
    const currentTask = task();
    render(
      <TaskDetail allTasks={[currentTask]} onClose={vi.fn()} task={currentTask} timezone="UTC" />,
      { wrapper: Wrapper },
    );

    const detail = await screen.findByRole("dialog", { name: currentTask.title });
    fireEvent.click(within(detail).getByRole("button", { name: "Suggest schedule" }));
    const apply = await within(detail).findByRole("button", { name: "Apply reviewed schedule" });
    fireEvent.click(within(detail).getByLabelText(/I reviewed this proposed placement/));
    fireEvent.click(apply);

    const alert = await within(detail).findByRole("alert");
    expect(alert).toHaveTextContent("The preview is stale because the task changed.");
    expect(apply).toBeDisabled();
    fireEvent.click(within(alert).getByRole("button", { name: "Generate new suggestion" }));
    await waitFor(() => expect(suggestTaskSchedule).toHaveBeenCalledTimes(2));
  });

  it("does not offer an apply action when no placement is available", async () => {
    vi.mocked(suggestTaskSchedule).mockResolvedValueOnce(schedulingPreview([]));
    const currentTask = task();
    render(
      <TaskDetail allTasks={[currentTask]} onClose={vi.fn()} task={currentTask} timezone="UTC" />,
      { wrapper: Wrapper },
    );

    const detail = await screen.findByRole("dialog", { name: currentTask.title });
    fireEvent.click(within(detail).getByRole("button", { name: "Suggest schedule" }));

    expect(await within(detail).findByText(/There is nothing to apply/)).toBeVisible();
    expect(within(detail).queryByRole("button", { name: "Apply reviewed schedule" })).toBeNull();
  });
});
