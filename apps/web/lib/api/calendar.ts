import type { components } from "@locallife/shared-types";

import { apiRequest, jsonBody, withQuery } from "./client";
import type {
  CalendarConflict,
  CalendarEvent,
  CalendarEventCreate,
  CalendarMove,
  CalendarResize,
  DataEnvelope,
  ListEnvelope,
} from "./types";

type CalendarEventUpdate = components["schemas"]["CalendarEventUpdateRequest"];

export interface CalendarRange {
  start: string;
  end: string;
  timezone?: string;
  q?: string;
  category?: string;
  status?: components["schemas"]["CalendarEventStatus"];
}

export async function listCalendarEvents(range: CalendarRange): Promise<ListEnvelope<CalendarEvent>> {
  return apiRequest<ListEnvelope<CalendarEvent>>(
    withQuery("/calendar/events", { ...range, page_size: 100 }),
  );
}

export async function listCalendarConflicts(range: CalendarRange): Promise<CalendarConflict[]> {
  return (
    await apiRequest<DataEnvelope<CalendarConflict[]>>(
      withQuery("/calendar/conflicts", range),
    )
  ).data;
}

export async function createCalendarEvent(payload: CalendarEventCreate): Promise<CalendarEvent> {
  return (
    await apiRequest<DataEnvelope<CalendarEvent>>("/calendar/events", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function updateCalendarEvent(
  eventId: string,
  payload: CalendarEventUpdate,
): Promise<CalendarEvent> {
  return (
    await apiRequest<DataEnvelope<CalendarEvent>>(`/calendar/events/${eventId}`, {
      method: "PATCH",
      ...jsonBody(payload),
    })
  ).data;
}

export async function moveCalendarEvent(eventId: string, payload: CalendarMove): Promise<CalendarEvent> {
  return (
    await apiRequest<DataEnvelope<CalendarEvent>>(`/calendar/events/${eventId}/move`, {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function resizeCalendarEvent(
  eventId: string,
  payload: CalendarResize,
): Promise<CalendarEvent> {
  return (
    await apiRequest<DataEnvelope<CalendarEvent>>(`/calendar/events/${eventId}/resize`, {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}
