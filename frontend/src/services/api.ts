// Minimal typed API client. In local development, requests are proxied to the
// FastAPI backend by Vite (see vite.config.ts). The base URL can be overridden
// via VITE_API_BASE_URL for deployed environments.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export interface ApiError {
  code: string;
  message: string;
  request_id?: string | null;
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = error.code;
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    let error: ApiError = { code: "HTTP_ERROR", message: response.statusText };
    try {
      const body = (await response.json()) as { error?: ApiError };
      if (body.error) {
        error = body.error;
      }
    } catch {
      // Non-JSON error body; keep the default.
    }
    throw new ApiRequestError(response.status, error);
  }

  return (await response.json()) as T;
}
