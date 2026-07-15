export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  timestamp: string;
}

export interface SystemInfoResponse {
  application: string;
  version: string;
  environment: "development" | "test" | "production";
  storage: "sqlite";
  timezone: string;
  telemetry_enabled: false;
  external_requests_enabled: false;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  request_id: string;
  details?: unknown;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export type { components, operations, paths } from "./openapi";
