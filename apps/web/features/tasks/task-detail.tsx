"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Link2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { addTaskDependency, listTasks, suggestTaskSchedule, updateTask } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { Task } from "@/lib/api/types";
import { formatDateTime, formatDuration } from "@/lib/format";
import { defaultSchedulingScope } from "@/lib/scheduling-defaults";
import { useUiStore } from "@/stores/ui-store";

export function TaskDetail({ task, allTasks, timezone, onClose }: { task: Task | null; allTasks: Task[]; timezone: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const [dependencyId, setDependencyId] = useState("");
  const subtasks = useQuery({ queryKey: queryKeys.tasks.list({ parent_task_id: task?.id }), queryFn: () => listTasks({ parent_task_id: task?.id, page_size: 100 }), enabled: !!task });
  const update = useMutation({ mutationFn: (status: Task["status"]) => updateTask(task!.id, { revision: task!.revision, status }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }); pushToast({ title: "Task updated", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't update task", description: error instanceof Error ? error.message : "Reload and try again.", tone: "error" }) });
  const dependency = useMutation({ mutationFn: () => addTaskDependency(task!.id, { depends_on_task_id: dependencyId, dependency_type: "finish_to_start" }), onSuccess: async () => { setDependencyId(""); await queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }); pushToast({ title: "Dependency added", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't add dependency", description: error instanceof Error ? error.message : "Try another task.", tone: "error" }) });
  const suggestion = useMutation({ mutationFn: () => { const start = new Date(); const end = new Date(start.getTime() + 7 * 86_400_000); return suggestTaskSchedule(task!.id, defaultSchedulingScope(start.toISOString(), end.toISOString())); }, onError: (error) => pushToast({ title: "Couldn't calculate a schedule", description: error instanceof Error ? error.message : "Try again.", tone: "error" }) });
  if (!task) return null;
  const taskById = new Map(allTasks.map((item) => [item.id, item]));
  return (
    <Modal description="Review state, timing, subtasks, dependencies, and schedule advice." onClose={onClose} open={!!task} title={task.title} wide>
      <div className="space-y-6">
        <div className="flex flex-wrap gap-2"><Badge tone={task.overdue ? "danger" : "neutral"}>{task.status}</Badge><Badge tone={task.blocked ? "warning" : "neutral"}>{task.priority}</Badge>{task.blocked ? <Badge tone="warning">Blocked</Badge> : null}{task.recurrence_rrule ? <Badge>Recurring</Badge> : null}</div>
        {task.description_markdown ? <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{task.description_markdown}</p> : null}
        <dl className="grid gap-4 rounded-lg bg-muted p-4 sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Estimate</dt><dd className="mt-1 text-sm font-medium">{formatDuration(task.estimated_duration_minutes)}</dd></div><div><dt className="text-xs text-muted-foreground">Deadline</dt><dd className="mt-1 text-sm font-medium">{formatDateTime(task.due_at, timezone)}</dd></div><div><dt className="text-xs text-muted-foreground">Scheduled</dt><dd className="mt-1 text-sm font-medium">{task.scheduled_start_at ? `${formatDateTime(task.scheduled_start_at, timezone)} – ${formatDateTime(task.scheduled_end_at, timezone)}` : "Not scheduled"}</dd></div><div><dt className="text-xs text-muted-foreground">Preference</dt><dd className="mt-1 text-sm font-medium">{task.preferred_time_of_day}</dd></div></dl>
        <div className="flex flex-wrap items-end gap-3"><Field id="detail-status" label="Status"><Select id="detail-status" onChange={(event) => update.mutate(event.target.value as Task["status"])} value={task.status}><option value="todo">To do</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></Select></Field><Button loading={suggestion.isPending} onClick={() => suggestion.mutate()} type="button" variant="secondary"><CalendarClock aria-hidden="true" className="h-4 w-4" />Suggest schedule</Button></div>
        {suggestion.data ? <section aria-labelledby="suggestion-title" className="rounded-lg border border-border p-4"><h3 className="text-sm font-semibold" id="suggestion-title">Schedule suggestion</h3>{suggestion.data.placements.length ? suggestion.data.placements.map((placement) => <p className="mt-2 text-sm" key={placement.task_id}>{formatDateTime(placement.starts_at, timezone)} – {formatDateTime(placement.ends_at, timezone)}</p>) : <p className="mt-2 text-sm text-muted-foreground">{suggestion.data.unscheduled_tasks.flatMap((item) => item.reasons.map((reason) => reason.message)).join(" ")}</p>}</section> : null}
        <section aria-labelledby="subtasks-title"><h3 className="text-sm font-semibold" id="subtasks-title">Subtasks</h3><div className="mt-2 divide-y divide-border rounded-lg border border-border">{subtasks.data?.data.length ? subtasks.data.data.map((item) => <div className="flex min-h-12 items-center justify-between gap-3 px-4 py-2" key={item.id}><span className="text-sm">{item.title}</span><Badge>{item.status}</Badge></div>) : <p className="p-4 text-sm text-muted-foreground">No subtasks.</p>}</div></section>
        <section aria-labelledby="dependencies-title" className="space-y-3"><h3 className="text-sm font-semibold" id="dependencies-title">Dependencies</h3>{task.dependencies.map((item) => <div className="flex items-center gap-2 text-sm" key={item.id}><Link2 aria-hidden="true" className="h-4 w-4" />{taskById.get(item.depends_on_task_id)?.title || item.depends_on_task_id}<Badge>{item.dependency_type}</Badge></div>)}<div className="flex items-end gap-2"><Field id="dependency-task" label="Add prerequisite"><Select id="dependency-task" onChange={(event) => setDependencyId(event.target.value)} value={dependencyId}><option value="">Select task</option>{allTasks.filter((item) => item.id !== task.id).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></Field><Button disabled={!dependencyId} loading={dependency.isPending} onClick={() => dependency.mutate()} type="button" variant="secondary">Add</Button></div></section>
      </div>
    </Modal>
  );
}
