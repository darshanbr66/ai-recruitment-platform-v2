/**
 * Thin fetch wrapper — the one place that knows the backend base URL and
 * how to turn a non-2xx response into a typed error. Feature code calls
 * through this (or a feature-specific service built on top of it), never
 * `fetch` directly, so audience base paths and error handling stay
 * consistent (see docs/api.md).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string | null;
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let code = "unknown_error";
    let message = "Request failed.";
    try {
      const body = (await response.json()) as ErrorEnvelope;
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      // Non-JSON error body — fall back to the defaults above.
    }
    throw new ApiError(message, response.status, code);
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
};
