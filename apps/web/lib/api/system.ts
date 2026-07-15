import type {
  HealthResponse,
  SystemInfoResponse,
} from "@locallife/shared-types";

import { apiRequest } from "./client";

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health", { signal });
}

export function getSystemInfo(signal?: AbortSignal): Promise<SystemInfoResponse> {
  return apiRequest<SystemInfoResponse>("/system/info", { signal });
}
