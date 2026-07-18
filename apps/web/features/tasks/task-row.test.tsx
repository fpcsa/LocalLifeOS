import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Task } from "@/lib/api/types";

import { TaskRow } from "./tasks-workspace";

function task(status: Task["status"]): Task {
  return {
    actual_duration_minutes: null,
    blocked: false,
    child_count: 0,
    commitment_ids: [],
    completed_at: status === "completed" ? "2026-07-18T08:00:00Z" : null,
    created_at: "2026-07-18T07:00:00Z",
    dependencies: [],
    description_markdown: null,
    due_at: null,
    earliest_start_at: null,
    estimated_duration_minutes: 30,
    id: "12000000-0000-4000-8000-000000000001",
    overdue: false,
    parent_task_id: null,
    preferred_time_of_day: "any",
    priority: "medium",
    project_id: null,
    recurrence_rrule: null,
    revision: 1,
    schedulable: status === "todo",
    scheduled_end_at: null,
    scheduled_start_at: null,
    status,
    tag_ids: [],
    title: "Review completed work",
    updated_at: "2026-07-18T08:00:00Z",
    workspace_id: "12000000-0000-4000-8000-000000000002",
  };
}

describe("TaskRow", () => {
  it("prevents completed tasks from becoming bulk-completion targets", () => {
    const onSelect = vi.fn();
    render(<TaskRow onOpen={vi.fn()} onSelect={onSelect} selected={false} task={task("completed")} timezone="UTC" />);

    const checkbox = screen.getByRole("checkbox", { name: /is completed and unavailable for bulk actions/i });
    expect(checkbox).toBeDisabled();
    fireEvent.click(checkbox);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("keeps active tasks selectable for bulk completion", () => {
    const onSelect = vi.fn();
    render(<TaskRow onOpen={vi.fn()} onSelect={onSelect} selected={false} task={task("todo")} timezone="UTC" />);

    const checkbox = screen.getByRole("checkbox", { name: "Select Review completed work" });
    expect(checkbox).toBeEnabled();
    fireEvent.click(checkbox);
    expect(onSelect).toHaveBeenCalledOnce();
  });
});
