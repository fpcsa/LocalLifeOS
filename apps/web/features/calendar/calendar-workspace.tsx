"use client";

import type { DatesSetArg, EventClickArg, EventDropArg } from "@fullcalendar/core";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import listPlugin from "@fullcalendar/list";
import FullCalendar from "@fullcalendar/react";
import type { EventResizeDoneArg } from "@fullcalendar/interaction";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarPlus, CheckCircle2, Clock3, MapPin, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import {
  listCalendarConflicts,
  listCalendarEvents,
  moveCalendarEvent,
  resizeCalendarEvent,
} from "@/lib/api/calendar";
import { applySchedule, getPreferences } from "@/lib/api/connected";
import { listTasks, suggestTaskSchedule } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { CalendarEvent, ListEnvelope } from "@/lib/api/types";
import { defaultSchedulingScope } from "@/lib/scheduling-defaults";
import { formatDateTime, formatDuration } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

interface CalendarRangeState {
  start: string;
  end: string;
}

type CalendarSnapshot = Array<[readonly unknown[], ListEnvelope<CalendarEvent> | undefined]>;

function defaultRange(): CalendarRangeState {
  const now = new Date();
  return {
    start: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString(),
    end: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)).toISOString(),
  };
}

function eventStart(event: CalendarEvent): string {
  return event.all_day ? event.all_day_start || "" : event.starts_at || "";
}

function eventEnd(event: CalendarEvent): string {
  return event.all_day ? event.all_day_end || "" : event.ends_at || "";
}

function EventDetails({ event, timezone, onClose }: { event: CalendarEvent | null; timezone: string; onClose: () => void }) {
  return (
    <Modal description={event?.category || "Calendar event"} onClose={onClose} open={!!event} title={event?.title || "Event details"}>
      {event ? (
        <div className="space-y-5">
          <div className="space-y-2 text-sm">
            <p className="flex items-center gap-2"><Clock3 aria-hidden="true" className="h-4 w-4 text-muted-foreground" />{event.all_day ? `${event.all_day_start} – ${event.all_day_end}` : `${formatDateTime(event.starts_at, timezone)} – ${formatDateTime(event.ends_at, timezone)}`}</p>
            {event.location ? <p className="flex items-center gap-2"><MapPin aria-hidden="true" className="h-4 w-4 text-muted-foreground" />{event.location}</p> : null}
          </div>
          {event.description_markdown ? <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{event.description_markdown}</p> : null}
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-muted p-3"><p className="text-xs text-muted-foreground">Preparation</p><p className="mt-1 text-sm font-semibold">{formatDuration(event.preparation_buffer_minutes)}</p></div>
            <div className="rounded-lg bg-muted p-3"><p className="text-xs text-muted-foreground">Travel</p><p className="mt-1 text-sm font-semibold">{formatDuration(event.travel_buffer_minutes)}</p></div>
            <div className="rounded-lg bg-muted p-3"><p className="text-xs text-muted-foreground">Recovery</p><p className="mt-1 text-sm font-semibold">{formatDuration(event.recovery_buffer_minutes)}</p></div>
          </div>
          {event.recurrence_rrule ? <p className="rounded-lg border border-border p-3 font-mono text-xs">{event.recurrence_rrule}</p> : null}
        </div>
      ) : null}
    </Modal>
  );
}

export function CalendarWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedEventId = searchParams.get("event");
  const [range, setRange] = useState<CalendarRangeState>(defaultRange);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [suggestionTaskId, setSuggestionTaskId] = useState("");
  const [scheduleReviewed, setScheduleReviewed] = useState(false);
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const openQuickCreate = useUiStore((state) => state.openQuickCreate);
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const timezone = preferences.data?.timezone || "UTC";
  const rangeQuery = { ...range, timezone };
  const events = useQuery({ queryKey: queryKeys.calendar.events(rangeQuery), queryFn: () => listCalendarEvents(rangeQuery) });
  const conflicts = useQuery({ queryKey: queryKeys.calendar.conflicts(rangeQuery), queryFn: () => listCalendarConflicts(rangeQuery) });
  const tasks = useQuery({ queryKey: queryKeys.tasks.list({ schedulable: true }), queryFn: () => listTasks({ schedulable: true, page_size: 100, sort: "due_at", order: "asc" }) });

  const conflictIds = useMemo(() => new Set((conflicts.data || []).flatMap((conflict) => [conflict.first.event_id, conflict.second.event_id])), [conflicts.data]);
  const calendarEvents = useMemo(() => (events.data?.data || []).map((event) => ({ id: event.id, title: event.title, start: eventStart(event), end: eventEnd(event), allDay: event.all_day, classNames: conflictIds.has(event.id) ? ["ll-calendar-conflict"] : [], extendedProps: { record: event } })), [conflictIds, events.data]);
  const routedEvent = events.data?.data.find((event) => event.id === requestedEventId) || null;

  const takeSnapshots = async (): Promise<CalendarSnapshot> => {
    await queryClient.cancelQueries({ queryKey: queryKeys.calendar.eventsRoot });
    return queryClient.getQueriesData<ListEnvelope<CalendarEvent>>({ queryKey: queryKeys.calendar.eventsRoot });
  };
  const updateCachedEvent = (eventId: string, patch: Partial<CalendarEvent>) => {
    queryClient.setQueriesData<ListEnvelope<CalendarEvent>>({ queryKey: queryKeys.calendar.eventsRoot }, (current) => current ? { ...current, data: current.data.map((event) => event.id === eventId ? { ...event, ...patch } : event) } : current);
  };
  const restoreSnapshots = (snapshots?: CalendarSnapshot) => snapshots?.forEach(([key, data]) => queryClient.setQueryData(key, data));
  const settleCalendar = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.eventsRoot }),
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.conflictsRoot }),
    ]);
  };

  const move = useMutation({
    mutationFn: ({ event, start }: { event: CalendarEvent; start: string; revert: () => void }) => moveCalendarEvent(event.id, event.all_day ? { revision: event.revision, all_day_start: start.slice(0, 10), timezone } : { revision: event.revision, starts_at: new Date(start).toISOString(), timezone }),
    onMutate: async ({ event, start }) => { const snapshots = await takeSnapshots(); updateCachedEvent(event.id, event.all_day ? { all_day_start: start.slice(0, 10) } : { starts_at: new Date(start).toISOString() }); return { snapshots }; },
    onError: (error, variables, context) => { restoreSnapshots(context?.snapshots); variables.revert(); pushToast({ title: "Couldn't move event", description: error instanceof Error ? error.message : "The original time was restored.", tone: "error" }); },
    onSuccess: () => pushToast({ title: "Event moved", tone: "success" }),
    onSettled: settleCalendar,
  });
  const resize = useMutation({
    mutationFn: ({ event, end }: { event: CalendarEvent; end: string; revert: () => void }) => resizeCalendarEvent(event.id, event.all_day ? { revision: event.revision, all_day_end: end.slice(0, 10) } : { revision: event.revision, ends_at: new Date(end).toISOString() }),
    onMutate: async ({ event, end }) => { const snapshots = await takeSnapshots(); updateCachedEvent(event.id, event.all_day ? { all_day_end: end.slice(0, 10) } : { ends_at: new Date(end).toISOString() }); return { snapshots }; },
    onError: (error, variables, context) => { restoreSnapshots(context?.snapshots); variables.revert(); pushToast({ title: "Couldn't resize event", description: error instanceof Error ? error.message : "The original duration was restored.", tone: "error" }); },
    onSuccess: () => pushToast({ title: "Event resized", tone: "success" }),
    onSettled: settleCalendar,
  });
  const suggest = useMutation({ mutationFn: () => suggestTaskSchedule(suggestionTaskId, defaultSchedulingScope(range.start, range.end)), onSuccess: () => setScheduleReviewed(false), onError: (error) => pushToast({ title: "Couldn't calculate a suggestion", description: error instanceof Error ? error.message : "Try a different range.", tone: "error" }) });
  const applySuggestion = useMutation({
    mutationFn: () => {
      if (!suggest.data) throw new Error("Calculate a schedule suggestion first.");
      return applySchedule({ preview_id: suggest.data.preview_id });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.scheduling.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.commitments.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.timeline.all }),
      ]);
      setScheduleReviewed(false);
      suggest.reset();
      pushToast({ title: `${result.placements.length} task placement${result.placements.length === 1 ? "" : "s"} applied`, tone: "success" });
    },
    onError: (error) => pushToast({ title: "Schedule wasn't applied", description: error instanceof Error ? error.message : "The task changed. Calculate a fresh suggestion.", tone: "error" }),
  });

  const onDatesSet = (value: DatesSetArg) => setRange((current) => current.start === value.startStr && current.end === value.endStr ? current : { start: value.startStr, end: value.endStr });
  const onEventClick = (value: EventClickArg) => setSelectedEvent(value.event.extendedProps.record as CalendarEvent);
  const onEventDrop = (value: EventDropArg) => { const event = value.event.extendedProps.record as CalendarEvent; if (!value.event.startStr) return value.revert(); move.mutate({ event, start: value.event.startStr, revert: value.revert }); };
  const onEventResize = (value: EventResizeDoneArg) => { const event = value.event.extendedProps.record as CalendarEvent; if (!value.event.endStr) return value.revert(); resize.mutate({ event, end: value.event.endStr, revert: value.revert }); };

  if (preferences.isLoading) return <SkeletonList rows={7} />;
  if (preferences.isError) return <ErrorState retry={() => void preferences.refetch()} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Calendar" description={`Local calendar in ${timezone}. Month, week, day, and agenda views share the same event data.`} actions={<Button onClick={() => openQuickCreate("event")} type="button"><CalendarPlus aria-hidden="true" className="h-4 w-4" />New event</Button>} />
      {events.isError ? <ErrorState retry={() => void events.refetch()} /> : (
        <Panel className="calendar-surface overflow-hidden p-3 sm:p-5">
          {events.isLoading ? <SkeletonList rows={7} /> : <FullCalendar allDayText="All day" datesSet={onDatesSet} dayMaxEvents editable eventClick={onEventClick} eventDrop={onEventDrop} eventResize={onEventResize} events={calendarEvents} firstDay={1} headerToolbar={{ left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek" }} height="auto" initialView="timeGridWeek" nowIndicator plugins={[dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin]} slotMinTime="06:00:00" views={{ listWeek: { buttonText: "Agenda" }, timeGridWeek: { buttonText: "Week" }, timeGridDay: { buttonText: "Day" }, dayGridMonth: { buttonText: "Month" } }} />}
        </Panel>
      )}
      <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        <Panel>
          <PanelHeader title="Conflicts" description="Preparation, travel, and recovery buffers are included." />
          {conflicts.isLoading ? <div className="p-4"><SkeletonList rows={2} /></div> : conflicts.isError ? <div className="p-4"><ErrorState retry={() => void conflicts.refetch()} /></div> : !conflicts.data?.length ? <EmptyState title="No conflicts in view" description="Your visible events and their buffers do not overlap." /> : <ul className="divide-y divide-border">{conflicts.data.map((conflict) => <li className="flex gap-3 p-4" key={`${conflict.first.event_id}-${conflict.second.event_id}`}><AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-warning" /><div><p className="text-sm font-medium">{conflict.first.title} overlaps {conflict.second.title}</p><p className="mt-1 text-xs text-muted-foreground">Effective windows: {formatDateTime(conflict.first.effective_starts_at, timezone)} – {formatDateTime(conflict.first.effective_ends_at, timezone)}</p></div></li>)}</ul>}
        </Panel>
        <Panel>
          <PanelHeader title="Task schedule suggestion" description="Ask the local constraint solver for a placement in the visible range." />
          <div className="space-y-4 p-4">
            <label className="block text-sm font-medium" htmlFor="suggestion-task">Unscheduled task</label>
            {tasks.isLoading ? <SkeletonList rows={2} /> : tasks.isError ? <ErrorState retry={() => void tasks.refetch()} /> : !tasks.data?.data.length ? <EmptyState title="No schedulable tasks" description="Create an unscheduled task with an estimate before requesting a placement." /> : <><select className="min-h-10 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" id="suggestion-task" onChange={(event) => { setSuggestionTaskId(event.target.value); setScheduleReviewed(false); suggest.reset(); applySuggestion.reset(); }} value={suggestionTaskId}><option value="">Choose a task</option>{tasks.data.data.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select>
            <Button disabled={!suggestionTaskId} loading={suggest.isPending} onClick={() => suggest.mutate()} type="button" variant="secondary"><Sparkles aria-hidden="true" className="h-4 w-4" />Suggest a time</Button></>}
            {suggest.data ? suggest.data.placements.length ? <div className="space-y-4 rounded-lg bg-muted p-4"><div><Badge tone="success">{suggest.data.solver_status}</Badge><p className="mt-3 text-sm font-semibold">{formatDateTime(suggest.data.placements[0].starts_at, timezone)}</p><p className="mt-1 text-xs text-muted-foreground">{formatDuration(suggest.data.placements[0].duration_minutes)} · proposed placement</p></div><label className="flex cursor-pointer items-start gap-3 rounded-md border border-border bg-background p-3 text-sm"><input checked={scheduleReviewed} className="mt-0.5 h-4 w-4 accent-foreground" onChange={(event) => setScheduleReviewed(event.target.checked)} type="checkbox" /><span><span className="font-medium">I reviewed this proposed placement</span><span className="mt-1 block text-xs text-muted-foreground">Apply stops if the task changed after this preview.</span></span></label><Button disabled={!scheduleReviewed} loading={applySuggestion.isPending} onClick={() => applySuggestion.mutate()} type="button"><CheckCircle2 aria-hidden="true" className="h-4 w-4" />Apply reviewed schedule</Button></div> : <p className="text-sm text-muted-foreground">No placement was found. {suggest.data.unscheduled_tasks[0]?.reasons[0]?.message}</p> : null}
          </div>
        </Panel>
      </div>
      <Panel>
        <details>
          <summary className="min-h-11 cursor-pointer px-5 py-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">Accessible event list for this view ({events.data?.data.length || 0})</summary>
          {!events.data?.data.length ? <EmptyState title="No events in view" description="Create an event or navigate to a different range." /> : <ol className="divide-y divide-border">{events.data.data.map((event) => <li className="p-4" key={event.id}><button className="w-full rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setSelectedEvent(event)} type="button"><span className="text-sm font-medium">{event.title}</span><span className="mt-1 block text-xs text-muted-foreground">{event.all_day ? `${event.all_day_start} – ${event.all_day_end}` : `${formatDateTime(event.starts_at, timezone)} – ${formatDateTime(event.ends_at, timezone)}`}</span></button></li>)}</ol>}
        </details>
      </Panel>
      <EventDetails event={selectedEvent || routedEvent} onClose={() => { setSelectedEvent(null); if (requestedEventId) router.replace("/calendar"); }} timezone={timezone} />
    </div>
  );
}
