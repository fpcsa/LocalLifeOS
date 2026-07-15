"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { createTask } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { Project, Task } from "@/lib/api/types";
import { fromDateTimeLocal } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

interface Values {
  title: string;
  description: string;
  projectId: string;
  parentTaskId: string;
  priority: "high" | "low" | "medium" | "urgent";
  duration: string;
  earliest: string;
  due: string;
  preferred: "afternoon" | "any" | "evening" | "morning";
  scheduledStart: string;
  scheduledEnd: string;
  rrule: string;
}

export function TaskForm({ open, onClose, projects, tasks }: { open: boolean; onClose: () => void; projects: Project[]; tasks: Task[] }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Values>({ defaultValues: { title: "", description: "", projectId: "", parentTaskId: "", priority: "medium", duration: "30", earliest: "", due: "", preferred: "any", scheduledStart: "", scheduledEnd: "", rrule: "" } });
  const create = useMutation({
    mutationFn: (values: Values) => createTask({
      title: values.title,
      description_markdown: values.description || null,
      project_id: values.projectId || null,
      parent_task_id: values.parentTaskId || null,
      status: "todo",
      priority: values.priority,
      estimated_duration_minutes: values.duration ? Number(values.duration) : null,
      earliest_start_at: fromDateTimeLocal(values.earliest) || null,
      due_at: fromDateTimeLocal(values.due) || null,
      preferred_time_of_day: values.preferred,
      scheduled_start_at: fromDateTimeLocal(values.scheduledStart) || null,
      scheduled_end_at: fromDateTimeLocal(values.scheduledEnd) || null,
      recurrence: values.rrule ? { interval: 1, rrule: values.rrule } : null,
    }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }); pushToast({ title: "Task created", tone: "success" }); reset(); onClose(); },
    onError: (error) => pushToast({ title: "Couldn't create task", description: error instanceof Error ? error.message : "Try again.", tone: "error" }),
  });
  return (
    <Modal description="Add work, timing, recurrence, and project context." onClose={onClose} open={open} title="Create task" wide>
      <form className="space-y-5" onSubmit={handleSubmit((values) => create.mutate(values))}>
        <Field error={errors.title?.message} id="task-title" label="Title" required><Input aria-invalid={!!errors.title} autoComplete="off" id="task-title" {...register("title", { required: "Enter a task title." })} /></Field>
        <Field id="task-description" label="Description"><Textarea id="task-description" {...register("description")} /></Field>
        <div className="grid gap-4 md:grid-cols-2"><Field id="task-project" label="Project"><Select id="task-project" {...register("projectId")}><option value="">No project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select></Field><Field id="task-parent" label="Parent task"><Select id="task-parent" {...register("parentTaskId")}><option value="">No parent</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</Select></Field></div>
        <div className="grid gap-4 sm:grid-cols-3"><Field id="task-priority" label="Priority"><Select id="task-priority" {...register("priority")}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></Select></Field><Field id="task-duration" label="Estimate" hint="Minutes"><Input id="task-duration" inputMode="numeric" pattern="[0-9]*" {...register("duration")} /></Field><Field id="task-preferred" label="Preferred time"><Select id="task-preferred" {...register("preferred")}><option value="any">Any time</option><option value="morning">Morning</option><option value="afternoon">Afternoon</option><option value="evening">Evening</option></Select></Field></div>
        <div className="grid gap-4 md:grid-cols-2"><Field id="task-earliest" label="Earliest start"><Input id="task-earliest" type="datetime-local" {...register("earliest")} /></Field><Field id="task-due" label="Deadline"><Input id="task-due" type="datetime-local" {...register("due")} /></Field></div>
        <fieldset className="rounded-lg border border-border p-4"><legend className="px-2 text-sm font-medium">Manual schedule</legend><div className="grid gap-4 md:grid-cols-2"><Field id="task-scheduled-start" label="Starts"><Input id="task-scheduled-start" type="datetime-local" {...register("scheduledStart")} /></Field><Field id="task-scheduled-end" label="Ends"><Input id="task-scheduled-end" type="datetime-local" {...register("scheduledEnd")} /></Field></div></fieldset>
        <Field id="task-rrule" label="Recurrence rule" hint="iCalendar RRULE, for example FREQ=WEEKLY;BYDAY=MO"><Input autoCapitalize="characters" id="task-rrule" placeholder="FREQ=WEEKLY;BYDAY=MO" spellCheck={false} {...register("rrule")} /></Field>
        <div className="flex justify-end gap-2"><Button onClick={onClose} type="button" variant="ghost">Cancel</Button><Button loading={create.isPending} type="submit">Create task</Button></div>
      </form>
    </Modal>
  );
}
