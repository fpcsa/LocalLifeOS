import type { components } from "@locallife/shared-types";

import { apiRequest, getApiBaseUrl, jsonBody } from "./client";
import type {
  AutomationExecution,
  AutomationPreview,
  AutomationRule,
  AutomationRuleCreate,
  AutomationRuleUpdate,
  CsvMapping,
  CsvMappingProfile,
  DataEnvelope,
  ImportBatch,
  ImportPreview,
  ListEnvelope,
  LocalNotification,
  SchedulerStatus,
} from "./types";

type AutomationPreviewRequest = components["schemas"]["AutomationPreviewRequest"];

function uploadBody(file: File): FormData {
  const body = new FormData();
  body.append("file", file);
  return body;
}

export async function listImportHistory(): Promise<ListEnvelope<ImportBatch>> {
  return apiRequest<ListEnvelope<ImportBatch>>("/imports?page_size=100");
}

export async function listMappingProfiles(): Promise<CsvMappingProfile[]> {
  return (await apiRequest<DataEnvelope<CsvMappingProfile[]>>("/imports/mapping-profiles")).data;
}

export async function previewCalendarImport(file: File): Promise<ImportPreview> {
  return (
    await apiRequest<DataEnvelope<ImportPreview>>("/imports/calendar/preview", {
      method: "POST",
      body: uploadBody(file),
    })
  ).data;
}

export async function previewCsvImport(file: File): Promise<ImportPreview> {
  return (
    await apiRequest<DataEnvelope<ImportPreview>>("/imports/csv/preview", {
      method: "POST",
      body: uploadBody(file),
    })
  ).data;
}

export async function mapCsvImport(batchId: string, mapping: CsvMapping): Promise<ImportPreview> {
  return (
    await apiRequest<DataEnvelope<ImportPreview>>(`/imports/csv/${batchId}/map`, {
      method: "POST",
      ...jsonBody(mapping),
    })
  ).data;
}

export async function applyImport(
  kind: "calendar" | "csv",
  batchId: string,
  includedRowIds: string[],
): Promise<ImportBatch> {
  return (
    await apiRequest<DataEnvelope<ImportBatch>>(`/imports/${kind}/${batchId}/apply`, {
      method: "POST",
      ...jsonBody({ included_row_ids: includedRowIds }),
    })
  ).data;
}

export function downloadCalendarExport(): void {
  window.location.assign(`${getApiBaseUrl()}/imports/calendar/export.ics`);
}

export async function listAutomationRules(): Promise<AutomationRule[]> {
  return (await apiRequest<DataEnvelope<AutomationRule[]>>("/automation/rules")).data;
}

export async function createAutomationRule(
  payload: AutomationRuleCreate,
): Promise<AutomationRule> {
  return (
    await apiRequest<DataEnvelope<AutomationRule>>("/automation/rules", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function updateAutomationRule(
  ruleId: string,
  payload: AutomationRuleUpdate,
): Promise<AutomationRule> {
  return (
    await apiRequest<DataEnvelope<AutomationRule>>(`/automation/rules/${ruleId}`, {
      method: "PATCH",
      ...jsonBody(payload),
    })
  ).data;
}

export async function deleteAutomationRule(ruleId: string, revision: number): Promise<void> {
  await apiRequest(`/automation/rules/${ruleId}?revision=${revision}`, { method: "DELETE" });
}

export async function previewAutomationRule(
  ruleId: string,
  payload: AutomationPreviewRequest,
): Promise<AutomationPreview> {
  return (
    await apiRequest<DataEnvelope<AutomationPreview>>(`/automation/rules/${ruleId}/test`, {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function listAutomationExecutions(): Promise<ListEnvelope<AutomationExecution>> {
  return apiRequest<ListEnvelope<AutomationExecution>>("/automation/executions?page_size=100");
}

export async function listLocalNotifications(): Promise<LocalNotification[]> {
  return (
    await apiRequest<DataEnvelope<LocalNotification[]>>("/automation/notifications")
  ).data;
}

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  return (await apiRequest<DataEnvelope<SchedulerStatus>>("/automation/scheduler")).data;
}
