"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Check, Columns3, FolderPlus, List, Plus, Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences } from "@/lib/api/connected";
import { bulkCompleteTasks, bulkRescheduleTasks, createProject, listProjects, listTasks } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { Project, Task } from "@/lib/api/types";
import { formatDateTime, formatDuration, fromDateTimeLocal } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

import { TaskDetail } from "./task-detail";
import { TaskForm } from "./task-form";

const boardColumns: Array<{ status: Task["status"]; label: string }> = [
  { status: "todo", label: "To do" },
  { status: "in_progress", label: "In progress" },
  { status: "completed", label: "Completed" },
];

export function canBulkSelectTask(task: Pick<Task, "status">) {
  return task.status === "todo" || task.status === "in_progress";
}

export function TaskRow({ task, selected, onSelect, onOpen, timezone }: { task: Task; selected: boolean; onSelect: () => void; onOpen: () => void; timezone: string }) {
  const bulkSelectable = canBulkSelectTask(task);
  const selectionLabel = bulkSelectable
    ? `Select ${task.title}`
    : `${task.title} is ${task.status} and unavailable for bulk actions`;

  return (
    <div className="flex min-h-16 items-center gap-3 border-b border-border px-4 py-3 last:border-0">
      <input aria-label={selectionLabel} checked={bulkSelectable && selected} className="h-5 w-5 rounded border-border accent-current focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40" disabled={!bulkSelectable} onChange={bulkSelectable ? onSelect : undefined} title={bulkSelectable ? undefined : "Completed and cancelled tasks cannot receive bulk actions."} type="checkbox" />
      <button className="min-w-0 flex-1 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={onOpen} type="button"><span className="block truncate text-sm font-medium">{task.title}</span><span className="mt-1 block text-xs text-muted-foreground">{task.due_at ? formatDateTime(task.due_at, timezone) : "No deadline"} · {formatDuration(task.estimated_duration_minutes)}</span></button>
      {task.blocked ? <Badge tone="warning">Blocked</Badge> : null}{task.overdue ? <Badge tone="danger">Overdue</Badge> : null}<Badge>{task.priority}</Badge>
    </div>
  );
}

function ProjectForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const { register, handleSubmit, reset, formState: { errors } } = useForm<{ name: string; targetEnd: string }>();
  const create = useMutation({ mutationFn: (values: { name: string; targetEnd: string }) => createProject({ name: values.name, status: "active", target_end_date: values.targetEnd || null }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.projects.all }); pushToast({ title: "Project created", tone: "success" }); reset(); onClose(); }, onError: (error) => pushToast({ title: "Couldn't create project", description: error instanceof Error ? error.message : "Try again.", tone: "error" }) });
  return <Modal onClose={onClose} open={open} title="Create project"><form className="space-y-4" onSubmit={handleSubmit((values) => create.mutate(values))}><Field error={errors.name?.message} id="project-name" label="Name" required><Input id="project-name" {...register("name", { required: "Enter a project name." })} /></Field><Field id="project-target" label="Target date"><Input id="project-target" type="date" {...register("targetEnd")} /></Field><div className="flex justify-end gap-2"><Button onClick={onClose} type="button" variant="ghost">Cancel</Button><Button loading={create.isPending} type="submit">Create project</Button></div></form></Modal>;
}

function BulkRescheduleForm({ open, onClose, tasks }: { open: boolean; onClose: () => void; tasks: Task[] }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const { register, handleSubmit, reset, formState: { errors } } = useForm<{ start: string; end: string }>();
  const reschedule = useMutation({ mutationFn: (values: { start: string; end: string }) => { const start = fromDateTimeLocal(values.start); const end = fromDateTimeLocal(values.end); if (!start || !end || new Date(end) <= new Date(start)) throw new Error("The end must be after the start."); return bulkRescheduleTasks(tasks.map((task) => ({ id: task.id, revision: task.revision, scheduled_start_at: start, scheduled_end_at: end }))); }, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }); pushToast({ title: "Tasks rescheduled", tone: "success" }); reset(); onClose(); }, onError: (error) => pushToast({ title: "Couldn't reschedule tasks", description: error instanceof Error ? error.message : "Reload and try again.", tone: "error" }) });
  return <Modal description={`Apply one explicit schedule window to ${tasks.length} selected task${tasks.length === 1 ? "" : "s"}.`} onClose={onClose} open={open} title="Bulk reschedule"><form className="space-y-4" onSubmit={handleSubmit((values) => reschedule.mutate(values))}><div className="grid gap-4 sm:grid-cols-2"><Field error={errors.start?.message} id="bulk-start" label="Starts" required><Input id="bulk-start" type="datetime-local" {...register("start", { required: "Choose a start time." })} /></Field><Field error={errors.end?.message} id="bulk-end" label="Ends" required><Input id="bulk-end" type="datetime-local" {...register("end", { required: "Choose an end time." })} /></Field></div><p className="text-xs leading-5 text-muted-foreground">Every selected task receives this same explicit window. Use task suggestions when you want the local constraint solver to find distinct placements.</p><div className="flex justify-end gap-2"><Button onClick={onClose} type="button" variant="ghost">Cancel</Button><Button loading={reschedule.isPending} type="submit">Reschedule</Button></div></form></Modal>;
}

export function TasksWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = searchParams.get("view") === "board" ? "board" : "list";
  const query = searchParams.get("q") || "";
  const status = searchParams.get("status") || "";
  const projectId = searchParams.get("project") || "";
  const selectedTaskId = searchParams.get("task");
  const [createOpen, setCreateOpen] = useState(false);
  const [projectOpen, setProjectOpen] = useState(false);
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const filters = { q: query || undefined, status: (status || undefined) as Task["status"] | undefined, project_id: projectId || undefined, page_size: 100, sort: "due_at" as const, order: "asc" as const };
  const tasks = useQuery({ queryKey: queryKeys.tasks.list(filters), queryFn: () => listTasks(filters) });
  const projects = useQuery({ queryKey: queryKeys.projects.list(), queryFn: () => listProjects({ page_size: 100, status: "active", sort: "name", order: "asc" }) });
  const complete = useMutation({ mutationFn: () => bulkCompleteTasks((tasks.data?.data || []).filter((task) => selected.has(task.id) && canBulkSelectTask(task)).map((task) => ({ id: task.id, revision: task.revision }))), onSuccess: async () => { setSelected(new Set()); await queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }); pushToast({ title: "Tasks completed", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't complete tasks", description: error instanceof Error ? error.message : "Reload and try again.", tone: "error" }) });
  const updateParams = (changes: Record<string, string | null>) => { const next = new URLSearchParams(searchParams.toString()); for (const [key, value] of Object.entries(changes)) { if (value) next.set(key, value); else next.delete(key); } router.replace(`/tasks?${next.toString()}`); };
  const projectById = useMemo(() => new Map((projects.data?.data || []).map((project) => [project.id, project])), [projects.data]);
  const selectedTask = (tasks.data?.data || []).find((task) => task.id === selectedTaskId) || null;
  const grouped = useMemo(() => { const groups = new Map<string, Task[]>(); for (const task of tasks.data?.data || []) { const key = task.project_id || "unassigned"; groups.set(key, [...(groups.get(key) || []), task]); } return groups; }, [tasks.data]);
  if (tasks.isLoading || projects.isLoading) return <SkeletonList rows={8} />;
  if (tasks.isError || projects.isError) return <ErrorState retry={() => { void tasks.refetch(); void projects.refetch(); }} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Tasks & projects" description="Plan work, dependencies, recurrence, estimates, and schedules without losing project context." actions={<><Button onClick={() => setProjectOpen(true)} type="button" variant="secondary"><FolderPlus aria-hidden="true" className="h-4 w-4" />Project</Button><Button onClick={() => setCreateOpen(true)} type="button"><Plus aria-hidden="true" className="h-4 w-4" />Task</Button></>} />
      <Panel className="p-4"><div className="grid gap-3 lg:grid-cols-[minmax(14rem,1fr)_12rem_14rem_auto]"><div className="relative"><Search aria-hidden="true" className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input aria-label="Search tasks" className="pl-9" defaultValue={query} onChange={(event) => updateParams({ q: event.target.value || null })} placeholder="Search tasks" type="search" /></div><Select aria-label="Filter by status" onChange={(event) => updateParams({ status: event.target.value || null })} value={status}><option value="">All statuses</option><option value="todo">To do</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></Select><Select aria-label="Filter by project" onChange={(event) => updateParams({ project: event.target.value || null })} value={projectId}><option value="">All projects</option>{projects.data?.data.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select><div className="flex gap-2"><Button aria-label="List view" onClick={() => updateParams({ view: "list" })} size="icon" type="button" variant={view === "list" ? "secondary" : "ghost"}><List aria-hidden="true" className="h-4 w-4" /></Button><Button aria-label="Board view" onClick={() => updateParams({ view: "board" })} size="icon" type="button" variant={view === "board" ? "secondary" : "ghost"}><Columns3 aria-hidden="true" className="h-4 w-4" /></Button></div></div></Panel>
      {selected.size ? <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3"><span className="text-sm font-medium">{selected.size} selected</span><Button loading={complete.isPending} onClick={() => complete.mutate()} type="button" variant="secondary"><Check aria-hidden="true" className="h-4 w-4" />Complete</Button><Button onClick={() => setRescheduleOpen(true)} type="button" variant="secondary"><CalendarClock aria-hidden="true" className="h-4 w-4" />Reschedule</Button></div> : null}
      {!tasks.data?.data.length ? <Panel><EmptyState title="No tasks match" description="Clear filters or create the first task in this workspace." action={<Button onClick={() => setCreateOpen(true)} type="button">Create task</Button>} /></Panel> : view === "board" ? <div className="grid gap-4 xl:grid-cols-3">{boardColumns.map((column) => <Panel key={column.status}><div className="flex items-center justify-between border-b border-border px-4 py-3"><h2 className="text-sm font-semibold">{column.label}</h2><Badge>{tasks.data!.data.filter((task) => task.status === column.status).length}</Badge></div>{tasks.data!.data.filter((task) => task.status === column.status).map((task) => <TaskRow key={task.id} onOpen={() => updateParams({ task: task.id })} onSelect={() => setSelected((current) => { const next = new Set(current); if (next.has(task.id)) next.delete(task.id); else next.add(task.id); return next; })} selected={selected.has(task.id)} task={task} timezone={preferences.data?.timezone || "UTC"} />)}</Panel>)}</div> : <div className="space-y-5">{Array.from(grouped.entries()).map(([groupId, groupTasks]) => <Panel key={groupId}><div className="flex items-baseline justify-between border-b border-border px-4 py-3"><h2 className="text-sm font-semibold">{groupId === "unassigned" ? "No project" : projectById.get(groupId)?.name || "Project"}</h2><span className="text-xs text-muted-foreground">{groupTasks.length} tasks{groupId !== "unassigned" && projectById.get(groupId) ? ` · ${(projectById.get(groupId)!.progress_basis_points / 100).toFixed(0)}% complete` : ""}</span></div>{groupTasks.map((task) => <TaskRow key={task.id} onOpen={() => updateParams({ task: task.id })} onSelect={() => setSelected((current) => { const next = new Set(current); if (next.has(task.id)) next.delete(task.id); else next.add(task.id); return next; })} selected={selected.has(task.id)} task={task} timezone={preferences.data?.timezone || "UTC"} />)}</Panel>)}</div>}
      <TaskForm onClose={() => setCreateOpen(false)} open={createOpen} projects={(projects.data?.data || []) as Project[]} tasks={tasks.data?.data || []} />
      <ProjectForm onClose={() => setProjectOpen(false)} open={projectOpen} />
      <BulkRescheduleForm onClose={() => setRescheduleOpen(false)} open={rescheduleOpen} tasks={(tasks.data?.data || []).filter((task) => selected.has(task.id))} />
      <TaskDetail allTasks={tasks.data?.data || []} onClose={() => updateParams({ task: null })} task={selectedTask} timezone={preferences.data?.timezone || "UTC"} />
    </div>
  );
}
