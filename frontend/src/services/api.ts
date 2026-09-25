// Typed API client. In local development, requests are proxied to the FastAPI
// backend by Vite (see vite.config.ts). The base URL can be overridden via
// VITE_API_BASE_URL for deployed environments.
//
// A token provider can be registered by the auth layer; when it returns a
// token, requests include it as a Bearer credential. In local-dev mode it
// returns null and the backend's local auth bypass handles the request.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

type TokenProvider = () => Promise<string | null>;

let tokenProvider: TokenProvider = async () => null;

export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

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
  const token = await tokenProvider();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (response.status === 204) {
    return undefined as T;
  }

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
