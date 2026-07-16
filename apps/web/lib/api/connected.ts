import type { components } from "@locallife/shared-types";

import { apiRequest, jsonBody, withQuery } from "./client";
import type {
  CapacityReport,
  Commitment,
  CommitmentAssessment,
  CommitmentCreate,
  CommitmentImpact,
  CommitmentLink,
  CommitmentUpdate,
  CommitmentWarnings,
  DataEnvelope,
  DemoDataSummary,
  Goal,
  GoalCreate,
  ListEnvelope,
  Preferences,
  PreferencesUpdate,
  Project,
  Task,
  TimelineItem,
  Transaction,
  Note,
  Scenario,
  ScenarioChange,
  ScenarioCompare,
  ScenarioPreview,
  SchedulingApply,
  SchedulingPreview,
} from "./types";

type Schemas = components["schemas"];

export async function loadDemoData(): Promise<DemoDataSummary> {
  return (
    await apiRequest<DataEnvelope<DemoDataSummary>>("/demo/load", { method: "POST" })
  ).data;
}

export async function getPreferences(): Promise<Preferences> {
  return (await apiRequest<DataEnvelope<Preferences>>("/preferences")).data;
}

export async function updatePreferences(payload: PreferencesUpdate): Promise<Preferences> {
  return (
    await apiRequest<DataEnvelope<Preferences>>("/preferences", {
      method: "PATCH",
      ...jsonBody(payload),
    })
  ).data;
}

export async function listGoals(): Promise<ListEnvelope<Goal>> {
  return apiRequest<ListEnvelope<Goal>>(withQuery("/goals", { page_size: 100 }));
}

export async function createGoal(payload: GoalCreate): Promise<Goal> {
  return (await apiRequest<DataEnvelope<Goal>>("/goals", { method: "POST", ...jsonBody(payload) })).data;
}

export interface CommitmentFilters {
  q?: string;
  status?: Schemas["CommitmentStatus"];
  target_before?: string;
  page_size?: number;
}

export async function listCommitments(
  filters: CommitmentFilters = {},
): Promise<ListEnvelope<Commitment>> {
  return apiRequest<ListEnvelope<Commitment>>(
    withQuery("/commitments", { page_size: 100, ...filters }),
  );
}

export async function getCommitment(id: string): Promise<Commitment> {
  return (await apiRequest<DataEnvelope<Commitment>>(`/commitments/${id}`)).data;
}

export async function createCommitment(payload: CommitmentCreate): Promise<Commitment> {
  return (await apiRequest<DataEnvelope<Commitment>>("/commitments", { method: "POST", ...jsonBody(payload) })).data;
}

export async function updateCommitment(id: string, payload: CommitmentUpdate): Promise<Commitment> {
  return (await apiRequest<DataEnvelope<Commitment>>(`/commitments/${id}`, { method: "PATCH", ...jsonBody(payload) })).data;
}

export async function getCommitmentAssessment(id: string): Promise<CommitmentAssessment> {
  return (await apiRequest<DataEnvelope<CommitmentAssessment>>(`/commitments/${id}/assessment`)).data;
}

export async function getCommitmentImpact(id: string): Promise<CommitmentImpact> {
  return (await apiRequest<DataEnvelope<CommitmentImpact>>(`/commitments/${id}/impact`)).data;
}

export async function listCommitmentLinks(id: string): Promise<CommitmentLink[]> {
  return (await apiRequest<DataEnvelope<CommitmentLink[]>>(`/commitments/${id}/links`)).data;
}

export async function addCommitmentLink(
  id: string,
  payload: Schemas["CommitmentLinkCreateRequest"],
): Promise<CommitmentLink> {
  return (await apiRequest<DataEnvelope<CommitmentLink>>(`/commitments/${id}/links`, { method: "POST", ...jsonBody(payload) })).data;
}

export async function removeCommitmentLink(id: string, linkId: string): Promise<void> {
  await apiRequest(`/commitments/${id}/links/${linkId}`, { method: "DELETE" });
}

export async function listCommitmentTimeline(
  id: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<ListEnvelope<TimelineItem>> {
  return apiRequest<ListEnvelope<TimelineItem>>(withQuery(`/commitments/${id}/timeline`, filters));
}

export async function getCommitmentWarnings(id: string): Promise<CommitmentWarnings> {
  return (
    await apiRequest<DataEnvelope<CommitmentWarnings>>(`/commitments/${id}/warnings`)
  ).data;
}

export async function getCapacity(
  start: string,
  end: string,
  commitmentId?: string,
): Promise<CapacityReport> {
  return (
    await apiRequest<DataEnvelope<CapacityReport>>(
      withQuery("/scheduling/capacity", { start, end, commitment_id: commitmentId }),
    )
  ).data;
}

export async function previewCommitmentSchedule(
  commitmentId: string,
  payload: Schemas["SchedulingScopeInput"],
  signal?: AbortSignal,
): Promise<SchedulingPreview> {
  return (await apiRequest<DataEnvelope<SchedulingPreview>>(`/commitments/${commitmentId}/schedule-preview`, { method: "POST", signal, ...jsonBody(payload) })).data;
}

export async function previewSchedule(
  payload: Schemas["SchedulingPreviewRequest"],
  signal?: AbortSignal,
): Promise<SchedulingPreview> {
  return (await apiRequest<DataEnvelope<SchedulingPreview>>("/scheduling/preview", { method: "POST", signal, ...jsonBody(payload) })).data;
}

export async function applySchedule(
  payload: Schemas["SchedulingApplyRequest"],
): Promise<SchedulingApply> {
  return (await apiRequest<DataEnvelope<SchedulingApply>>("/scheduling/apply", { method: "POST", ...jsonBody(payload) })).data;
}

export async function listTimeline(filters: {
  page?: number;
  page_size?: number;
  start?: string;
  end?: string;
  entity_type?: Schemas["UnifiedTimelineEntityType"];
  commitment_id?: string;
  order?: "asc" | "desc";
} = {}): Promise<ListEnvelope<TimelineItem>> {
  return apiRequest<ListEnvelope<TimelineItem>>(
    withQuery("/timeline/unified", { page_size: 100, ...filters }),
  );
}

export async function listScenarios(): Promise<Scenario[]> {
  return (await apiRequest<DataEnvelope<Scenario[]>>("/scenarios")).data;
}

export async function createScenario(payload: Schemas["ScenarioCreateRequest"]): Promise<Scenario> {
  return (await apiRequest<DataEnvelope<Scenario>>("/scenarios", { method: "POST", ...jsonBody(payload) })).data;
}

export async function getScenario(id: string): Promise<Scenario> {
  return (await apiRequest<DataEnvelope<Scenario>>(`/scenarios/${id}`)).data;
}

export async function listScenarioChanges(id: string): Promise<ScenarioChange[]> {
  return (await apiRequest<DataEnvelope<ScenarioChange[]>>(`/scenarios/${id}/changes`)).data;
}

export async function addScenarioChange(
  id: string,
  payload: Schemas["ScenarioChangeCreateRequest"],
): Promise<ScenarioChange> {
  return (await apiRequest<DataEnvelope<ScenarioChange>>(`/scenarios/${id}/changes`, { method: "POST", ...jsonBody(payload) })).data;
}

export async function updateScenarioChange(
  id: string,
  changeId: string,
  payload: Schemas["ScenarioChangeUpdateRequest"],
): Promise<ScenarioChange> {
  return (await apiRequest<DataEnvelope<ScenarioChange>>(`/scenarios/${id}/changes/${changeId}`, { method: "PATCH", ...jsonBody(payload) })).data;
}

export async function removeScenarioChange(id: string, changeId: string): Promise<void> {
  await apiRequest(`/scenarios/${id}/changes/${changeId}`, { method: "DELETE" });
}

export async function getScenarioPreview(id: string): Promise<ScenarioPreview> {
  return (await apiRequest<DataEnvelope<ScenarioPreview>>(`/scenarios/${id}/preview`)).data;
}

export async function compareScenarios(ids: string[]): Promise<ScenarioCompare> {
  return (await apiRequest<DataEnvelope<ScenarioCompare>>("/scenarios/compare", { method: "POST", ...jsonBody({ scenario_ids: ids }) })).data;
}

export async function acceptScenario(
  id: string,
  payload: Schemas["ScenarioAcceptRequest"],
): Promise<Schemas["ScenarioAcceptResponse"]> {
  return (await apiRequest<DataEnvelope<Schemas["ScenarioAcceptResponse"]>>(`/scenarios/${id}/accept`, { method: "POST", ...jsonBody(payload) })).data;
}

export async function discardScenario(id: string, revision: number): Promise<Scenario> {
  return (await apiRequest<DataEnvelope<Scenario>>(`/scenarios/${id}/discard`, { method: "POST", ...jsonBody({ revision }) })).data;
}

export interface GlobalSearchResults {
  tasks: Task[];
  projects: Project[];
  notes: Note[];
  commitments: Commitment[];
  transactions: Transaction[];
}

export async function globalSearch(query: string): Promise<GlobalSearchResults> {
  const q = query.trim();
  if (q.length < 2) {
    return { tasks: [], projects: [], notes: [], commitments: [], transactions: [] };
  }
  const [tasks, projects, notes, commitments, transactions] = await Promise.all([
    apiRequest<ListEnvelope<Task>>(withQuery("/tasks", { q, page_size: 8 })),
    apiRequest<ListEnvelope<Project>>(withQuery("/projects", { q, page_size: 8 })),
    apiRequest<ListEnvelope<Note>>(withQuery("/notes", { q, page_size: 8, sort: "relevance" })),
    apiRequest<ListEnvelope<Commitment>>(withQuery("/commitments", { q, page_size: 8 })),
    apiRequest<ListEnvelope<Transaction>>(
      withQuery("/finance/transactions", { q, page_size: 8 }),
    ),
  ]);
  return {
    tasks: tasks.data,
    projects: projects.data,
    notes: notes.data,
    commitments: commitments.data,
    transactions: transactions.data,
  };
}
