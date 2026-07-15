import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTask } from "@/lib/api/productivity";

import { TaskForm } from "./task-form";

vi.mock("@/lib/api/productivity", () => ({ createTask: vi.fn() }));

const mockedCreateTask = vi.mocked(createTask);

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("TaskForm", () => {
  beforeEach(() => mockedCreateTask.mockReset());

  it("announces required-field errors and submits recurrence/timing fields", async () => {
    mockedCreateTask.mockResolvedValue({} as Awaited<ReturnType<typeof createTask>>);
    const close = vi.fn();
    render(<TaskForm onClose={close} open projects={[]} tasks={[]} />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole("button", { name: "Create task" }));
    expect(await screen.findByText("Enter a task title.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Title/)).toHaveAttribute("aria-describedby", "task-title-error");

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: "Prepare local demo" } });
    fireEvent.change(screen.getByLabelText("Estimate"), { target: { value: "45" } });
    fireEvent.change(screen.getByLabelText("Recurrence rule"), { target: { value: "FREQ=WEEKLY;BYDAY=MO" } });
    fireEvent.click(screen.getByRole("button", { name: "Create task" }));

    await waitFor(() => expect(mockedCreateTask).toHaveBeenCalledTimes(1));
    expect(mockedCreateTask).toHaveBeenCalledWith(expect.objectContaining({
      title: "Prepare local demo",
      estimated_duration_minutes: 45,
      recurrence: { interval: 1, rrule: "FREQ=WEEKLY;BYDAY=MO" },
      status: "todo",
    }));
    await waitFor(() => expect(close).toHaveBeenCalled());
  });
});
