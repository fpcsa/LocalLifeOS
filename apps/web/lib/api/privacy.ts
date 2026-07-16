import { apiRequest, jsonBody } from "./client";
import type { DataEnvelope } from "./types";

export interface BackupSummary {
  filename: string;
  path: string;
  created_at: string;
  schema_revision: string;
  encrypted: boolean;
  size_bytes: number;
  integrity_verified: boolean;
}

export interface PrivacyStatus {
  data_directory: string;
  database_path: string;
  attachments_directory: string;
  backups_directory: string;
  imports_directory: string;
  network_mode: "loopback-only";
  telemetry_enabled: false;
  external_requests_enabled: boolean;
  outbound_guard_active: boolean;
  max_attachment_bytes: number;
  max_import_bytes: number;
  max_backup_bytes: number;
  session_timeout_minutes: number;
  privacy_lock_scope: "casual-screen-privacy";
  last_backup: BackupSummary | null;
}

export interface BackupCreateResult {
  backup: BackupSummary;
  manifest: {
    format: "locallife-backup";
    format_version: 1;
    encrypted: boolean;
    files: Array<{ path: string; size_bytes: number; sha256: string }>;
  };
}

export interface DeleteAllResult {
  deleted_database_records: number;
  deleted_attachment_files: number;
  deleted_import_files: number;
  deleted_backup_files: number;
  preserved_backups: boolean;
}

export async function getPrivacyStatus(): Promise<PrivacyStatus> {
  return (await apiRequest<DataEnvelope<PrivacyStatus>>("/privacy/status")).data;
}

export async function createLocalBackup(payload: {
  label?: string;
  password?: string;
}): Promise<BackupCreateResult> {
  return (
    await apiRequest<DataEnvelope<BackupCreateResult>>("/privacy/backups", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function deleteAllLocalData(payload: {
  confirmation: "DELETE ALL LOCAL DATA";
  include_backups: boolean;
}): Promise<DeleteAllResult> {
  return (
    await apiRequest<DataEnvelope<DeleteAllResult>>("/privacy/delete-all", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}
