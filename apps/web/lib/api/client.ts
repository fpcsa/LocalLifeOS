import type { ApiErrorResponse } from "@locallife/shared-types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1";
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
    readonly code?: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function getApiBaseUrl(): string {
  const configuredUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  const parsedUrl = new URL(configuredUrl);

  if (!LOOPBACK_HOSTS.has(parsedUrl.hostname)) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must use a loopback host");
  }

  return configuredUrl.replace(/\/$/, "");
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    typeof error.message === "string" &&
    "request_id" in error &&
    typeof error.request_id === "string"
  );
}

export async function apiRequest<T>(
  path: `/${string}`,
  init: RequestInit = {},
): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "X-Request-ID": crypto.randomUUID(),
      ...(init.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    if (isApiErrorResponse(payload)) {
      throw new ApiClientError(
        payload.error.message,
        response.status,
        payload.error.request_id,
        payload.error.code,
        payload.error.details,
      );
    }
    throw new ApiClientError(
      "The local service returned an unexpected response.",
      response.status,
    );
  }

  return (await response.json()) as T;
}

type QueryValue = boolean | number | string | null | undefined;

export function withQuery<T extends object>(
  path: `/${string}`,
  values: T,
): `/${string}` {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values) as Array<[string, QueryValue]>) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const suffix = query.toString();
  return `${path}${suffix ? `?${suffix}` : ""}` as `/${string}`;
}

export function jsonBody(value: unknown): Pick<RequestInit, "body"> {
  return { body: JSON.stringify(value) };
}
