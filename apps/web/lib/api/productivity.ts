import type { components } from "@locallife/shared-types";

import { apiRequest, getApiBaseUrl, jsonBody, withQuery } from "./client";
import type {
  Attachment,
  DataEnvelope,
  ListEnvelope,
  Note,
  NoteCreate,
  NoteUpdate,
  PageParams,
  Project,
  ProjectCreate,
  Task,
  TaskCreate,
  TaskUpdate,
  Tag,
} from "./types";

type Schemas = components["schemas"];

export interface ProjectFilters extends PageParams {
  status?: Schemas["ProjectStatus"];
  target_before?: string;
  sort?: "created_at" | "name" | "target_end_date" | "updated_at";
  order?: "asc" | "desc";
}

export interface TaskFilters extends PageParams {
  project_id?: string;
  parent_task_id?: string;
  status?: Schemas["TaskStatus"];
  priority?: Schemas["TaskPriority"];
  tag_id?: string;
  due_before?: string;
  due_after?: string;
  overdue?: boolean;
  blocked?: boolean;
  schedulable?: boolean;
  sort?: "created_at" | "due_at" | "priority" | "title" | "updated_at";
  order?: "asc" | "desc";
}

export interface NoteFilters extends PageParams {
  daily_note_date?: string;
  tag_id?: string;
  sort?: "created_at" | "daily_note_date" | "relevance" | "title" | "updated_at";
  order?: "asc" | "desc";
}

export async function listProjects(filters: ProjectFilters = {}): Promise<ListEnvelope<Project>> {
  return apiRequest<ListEnvelope<Project>>(withQuery("/projects", filters));
}

export async function createProject(payload: ProjectCreate): Promise<Project> {
  return (await apiRequest<DataEnvelope<Project>>("/projects", { method: "POST", ...jsonBody(payload) })).data;
}

export async function listTasks(filters: TaskFilters = {}): Promise<ListEnvelope<Task>> {
  return apiRequest<ListEnvelope<Task>>(withQuery("/tasks", filters));
}

export async function getTask(taskId: string): Promise<Task> {
  return (await apiRequest<DataEnvelope<Task>>(`/tasks/${taskId}`)).data;
}

export async function createTask(payload: TaskCreate): Promise<Task> {
  return (await apiRequest<DataEnvelope<Task>>("/tasks", { method: "POST", ...jsonBody(payload) })).data;
}

export async function updateTask(taskId: string, payload: TaskUpdate): Promise<Task> {
  return (
    await apiRequest<DataEnvelope<Task>>(`/tasks/${taskId}`, {
      method: "PATCH",
      ...jsonBody(payload),
    })
  ).data;
}

export async function bulkCompleteTasks(
  items: Schemas["BulkCompleteItem"][],
): Promise<Task[]> {
  return (
    await apiRequest<DataEnvelope<Task[]>>("/tasks/actions/bulk-complete", {
      method: "POST",
      ...jsonBody({ items }),
    })
  ).data;
}

export async function bulkRescheduleTasks(
  items: Schemas["BulkRescheduleItem"][],
): Promise<Task[]> {
  return (
    await apiRequest<DataEnvelope<Task[]>>("/tasks/actions/bulk-reschedule", {
      method: "POST",
      ...jsonBody({ items }),
    })
  ).data;
}

export async function addTaskDependency(
  taskId: string,
  payload: Schemas["TaskDependencyRequest"],
): Promise<Schemas["TaskDependencyResponse"]> {
  return (
    await apiRequest<DataEnvelope<Schemas["TaskDependencyResponse"]>>(
      `/tasks/${taskId}/dependencies`,
      { method: "POST", ...jsonBody(payload) },
    )
  ).data;
}

export async function suggestTaskSchedule(
  taskId: string,
  payload: Schemas["SchedulingScopeInput"],
): Promise<Schemas["SchedulingPreviewResponse"]> {
  return (
    await apiRequest<DataEnvelope<Schemas["SchedulingPreviewResponse"]>>(
      `/tasks/${taskId}/schedule-suggestions`,
      { method: "POST", ...jsonBody(payload) },
    )
  ).data;
}

export async function listNotes(filters: NoteFilters = {}): Promise<ListEnvelope<Note>> {
  return apiRequest<ListEnvelope<Note>>(withQuery("/notes", filters));
}

export async function getNote(noteId: string): Promise<Note> {
  return (await apiRequest<DataEnvelope<Note>>(`/notes/${noteId}`)).data;
}

export async function createNote(payload: NoteCreate): Promise<Note> {
  return (await apiRequest<DataEnvelope<Note>>("/notes", { method: "POST", ...jsonBody(payload) })).data;
}

export async function updateNote(noteId: string, payload: NoteUpdate): Promise<Note> {
  return (
    await apiRequest<DataEnvelope<Note>>(`/notes/${noteId}`, {
      method: "PATCH",
      ...jsonBody(payload),
    })
  ).data;
}

export async function addNoteLink(
  noteId: string,
  payload: Schemas["NoteLinkRequest"],
): Promise<Schemas["NoteLinkResponse"]> {
  return (
    await apiRequest<DataEnvelope<Schemas["NoteLinkResponse"]>>(`/notes/${noteId}/links`, {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function removeNoteLink(noteId: string, linkId: string): Promise<void> {
  await apiRequest(`/notes/${noteId}/links/${linkId}`, { method: "DELETE" });
}

export async function listTags(): Promise<ListEnvelope<Tag>> {
  return apiRequest<ListEnvelope<Tag>>(withQuery("/tags", { page_size: 100, sort: "name" }));
}

export async function listAttachments(entityId?: string): Promise<ListEnvelope<Attachment>> {
  return apiRequest<ListEnvelope<Attachment>>(
    withQuery("/attachments", {
      entity_type: entityId ? "note" : undefined,
      entity_id: entityId,
      page_size: 100,
    }),
  );
}

export async function uploadAttachment(
  file: File,
  entityType: Schemas["DomainEntityType"],
  entityId: string,
): Promise<Attachment> {
  const body = new FormData();
  body.append("file", file);
  body.append("entity_type", entityType);
  body.append("entity_id", entityId);
  return (
    await apiRequest<DataEnvelope<Attachment>>("/attachments", {
      method: "POST",
      body,
    })
  ).data;
}

export function attachmentDownloadUrl(attachmentId: string): string {
  return `${getApiBaseUrl()}/attachments/${attachmentId}/download`;
}
