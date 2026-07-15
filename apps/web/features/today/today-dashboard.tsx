"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CalendarDays, CheckSquare2, Clock3, Plus } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Progress } from "@/components/ui/progress";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { listCalendarEvents } from "@/lib/api/calendar";
import { getCapacity, getCommitmentWarnings, getPreferences, listCommitments, listGoals } from "@/lib/api/connected";
import { listPlannedTransactions, listSavingsGoals } from "@/lib/api/finance";
import { listTasks } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import { localDayRange, localDateKey } from "@/lib/date-range";
import { formatDateTime, formatDuration, formatMoney } from "@/lib/format";
import { useUiStore, type QuickCreateKind } from "@/stores/ui-store";

function QuickAction({ kind, label }: { kind: QuickCreateKind; label: string }) {
  const open = useUiStore((state) => state.openQuickCreate);
  return <Button onClick={() => open(kind)} type="button" variant="secondary"><Plus aria-hidden="true" className="h-4 w-4" />{label}</Button>;
}

export function TodayDashboard() {
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const timezone = preferences.data?.timezone || "UTC";
  const range = localDayRange(timezone);
  const todayKey = localDateKey(new Date(), timezone);
  const events = useQuery({ queryKey: queryKeys.calendar.events(range), queryFn: () => listCalendarEvents({ ...range, timezone }), enabled: preferences.isSuccess });
  const tasks = useQuery({ queryKey: queryKeys.tasks.list({ due_before: range.end }), queryFn: () => listTasks({ due_before: range.end, page_size: 100, sort: "due_at", order: "asc" }), enabled: preferences.isSuccess });
  const planned = useQuery({ queryKey: queryKeys.finance.planned(range), queryFn: () => listPlannedTransactions({ start: range.start, end: range.end, page_size: 100 }), enabled: preferences.isSuccess });
  const commitments = useQuery({ queryKey: queryKeys.commitments.list({ active: true }), queryFn: () => listCommitments({ page_size: 20 }), enabled: preferences.isSuccess });
  const warnings = useQueries({ queries: (commitments.data?.data || []).filter((item) => item.status === "active" || item.status === "planned").map((item) => ({ queryKey: queryKeys.commitments.warnings(item.id), queryFn: () => getCommitmentWarnings(item.id) })) });
  const goals = useQuery({ queryKey: queryKeys.goals.list, queryFn: listGoals });
  const savings = useQuery({ queryKey: queryKeys.finance.savingsGoals, queryFn: listSavingsGoals });
  const capacity = useQuery({ queryKey: queryKeys.scheduling.capacity(range), queryFn: () => getCapacity(range.start, range.end), enabled: preferences.isSuccess });

  const activeTasks = (tasks.data?.data || []).filter((task) => !["cancelled", "completed"].includes(task.status));
  const overdue = activeTasks.filter((task) => task.overdue);
  const dueToday = activeTasks.filter((task) => task.due_at && !task.overdue);
  const commitmentWarnings = warnings.flatMap((query) => query.data?.warnings || []);
  const deadlineItems = [
    ...activeTasks.filter((task) => task.due_at).map((task) => ({ id: task.id, title: task.title, at: task.due_at!, href: `/tasks?task=${task.id}` })),
    ...(commitments.data?.data || []).filter((item) => item.target_end_at).map((item) => ({ id: item.id, title: item.title, at: item.target_end_at!, href: `/commitments?commitment=${item.id}` })),
  ].sort((a, b) => a.at.localeCompare(b.at)).slice(0, 5);

  const loading = [events, tasks, planned, commitments, goals, savings, capacity].some((query) => query.isLoading);
  const failed = [events, tasks, planned, commitments, goals, savings, capacity].some((query) => query.isError);

  if (loading) return <div className="space-y-6"><PageHeader title="Today" description="Your local day is coming into focus." /><SkeletonList rows={7} /></div>;
  if (failed) return <ErrorState retry={() => { void events.refetch(); void tasks.refetch(); void planned.refetch(); }} />;

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={new Intl.DateTimeFormat(preferences.data?.locale || "en", { dateStyle: "full", timeZone: timezone }).format(new Date())} title="Today" description="The work, time, money, and commitments that need attention now." actions={<><QuickAction kind="task" label="Task" /><QuickAction kind="event" label="Event" /><QuickAction kind="transaction" label="Transaction" /></>} />
      <section aria-label="Today summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Panel className="p-5"><CalendarDays aria-hidden="true" className="h-5 w-5 text-muted-foreground" /><p className="mt-4 text-2xl font-semibold">{events.data?.data.length || 0}</p><p className="mt-1 text-sm text-muted-foreground">events today</p></Panel>
        <Panel className="p-5"><CheckSquare2 aria-hidden="true" className="h-5 w-5 text-muted-foreground" /><p className="mt-4 text-2xl font-semibold">{dueToday.length}</p><p className="mt-1 text-sm text-muted-foreground">tasks due · {overdue.length} overdue</p></Panel>
        <Panel className="p-5"><Clock3 aria-hidden="true" className="h-5 w-5 text-muted-foreground" /><p className="mt-4 text-2xl font-semibold">{formatDuration(capacity.data?.remaining_capacity_minutes || 0)}</p><p className="mt-1 text-sm text-muted-foreground">focus capacity remaining</p></Panel>
        <Panel className="p-5"><AlertTriangle aria-hidden="true" className="h-5 w-5 text-muted-foreground" /><p className="mt-4 text-2xl font-semibold">{commitmentWarnings.length}</p><p className="mt-1 text-sm text-muted-foreground">commitment warnings</p></Panel>
      </section>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel><PanelHeader title="Schedule" description="Events and their protected time today." action={<Link className="text-sm font-medium underline-offset-4 hover:underline" href="/calendar">Open calendar</Link>} /><div className="divide-y divide-border">{events.data?.data.length ? events.data.data.map((event) => <article className="flex items-start gap-3 px-5 py-4" key={event.id}><div className="mt-1 h-2.5 w-2.5 rounded-full bg-primary" /><div className="min-w-0"><h3 className="text-sm font-medium">{event.title}</h3><p className="mt-1 text-xs text-muted-foreground">{event.all_day ? "All day" : formatDateTime(event.starts_at, timezone)}{event.location ? ` · ${event.location}` : ""}</p></div></article>) : <EmptyState title="A clear calendar" description="No events are scheduled today." action={<QuickAction kind="event" label="Add event" />} />}</div></Panel>
        <Panel><PanelHeader title="Tasks" description="Due and overdue work, ordered by deadline." action={<Link className="text-sm font-medium underline-offset-4 hover:underline" href="/tasks">Open tasks</Link>} /><div className="divide-y divide-border">{activeTasks.length ? activeTasks.slice(0, 6).map((task) => <Link className="flex min-h-14 items-center gap-3 px-5 py-3 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" href={`/tasks?task=${task.id}`} key={task.id}><span className="min-w-0 flex-1 truncate text-sm font-medium">{task.title}</span>{task.blocked ? <Badge tone="warning">Blocked</Badge> : null}{task.overdue ? <Badge tone="danger">Overdue</Badge> : <span className="text-xs text-muted-foreground">{formatDuration(task.estimated_duration_minutes)}</span>}</Link>) : <EmptyState title="Nothing due" description="There are no active tasks due today." action={<QuickAction kind="task" label="Add task" />} />}</div></Panel>
        <Panel><PanelHeader title="Money today" description="Planned income and expenses in your local day." action={<Link className="text-sm font-medium underline-offset-4 hover:underline" href="/finance">Open finance</Link>} /><div className="divide-y divide-border">{planned.data?.length ? planned.data.map((item) => <div className="flex items-center justify-between gap-4 px-5 py-4" key={item.id}><div><p className="text-sm font-medium">{item.payee || item.note || "Planned transaction"}</p><Badge className="mt-2" tone={item.transaction_type === "income" ? "success" : "neutral"}>{item.transaction_type}</Badge></div><p className="text-sm font-semibold tabular-nums">{formatMoney(item.amount_minor, item.currency_code, preferences.data?.locale)}</p></div>) : <EmptyState title="No planned movement" description="No planned income or expense falls today." action={<QuickAction kind="transaction" label="Add transaction" />} />}</div></Panel>
        <Panel><PanelHeader title="Goals" description="General and savings progress." action={<Link className="text-sm font-medium underline-offset-4 hover:underline" href="/goals">Open goals</Link>} /><div className="space-y-5 p-5">{[...(goals.data?.data || []).map((goal) => ({ id: goal.id, name: goal.title, progress: goal.progress_basis_points / 100 })), ...(savings.data?.data || []).map((goal) => ({ id: goal.id, name: goal.name, progress: goal.progress_basis_points / 100 }))].slice(0, 5).map((goal) => <div className="space-y-2" key={goal.id}><div className="flex justify-between gap-4 text-sm"><span className="font-medium">{goal.name}</span><span className="tabular-nums text-muted-foreground">{goal.progress.toFixed(0)}%</span></div><Progress label={`${goal.name} progress`} value={goal.progress} /></div>)}{!(goals.data?.data.length || savings.data?.data.length) ? <EmptyState title="No active goals" description="Create a goal to make progress visible here." /> : null}</div></Panel>
      </div>
      <Panel><PanelHeader title="Upcoming deadlines" description={`Next task and commitment deadlines after ${todayKey}.`} /><div className="divide-y divide-border">{deadlineItems.length ? deadlineItems.map((item) => <Link className="flex min-h-14 items-center gap-4 px-5 py-3 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" href={item.href} key={`${item.href}-${item.id}`}><span className="min-w-0 flex-1 truncate text-sm font-medium">{item.title}</span><span className="text-xs text-muted-foreground">{formatDateTime(item.at, timezone)}</span><ArrowRight aria-hidden="true" className="h-4 w-4" /></Link>) : <EmptyState title="No upcoming deadlines" description="Nothing with a deadline needs planning yet." />}</div></Panel>
    </div>
  );
}
