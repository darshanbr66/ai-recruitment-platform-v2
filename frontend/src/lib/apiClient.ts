/**
 * Thin fetch wrapper — the one place that knows the backend base URL and
 * how to turn a non-2xx response into a typed error. Feature code calls
 * through this (or a feature-specific service built on top of it), never
 * `fetch` directly, so audience base paths and error handling stay
 * consistent (see docs/api.md).
 *
 * `credentials: "include"` on every call so the recruiter refresh-token
 * cookie (httpOnly, set by the backend) is sent/received automatically —
 * see docs/architecture.md § 4.
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

interface RequestOptions {
  accessToken?: string;
  body?: unknown;
}

async function request<T>(path: string, method: string, options?: RequestOptions): Promise<T> {
  const headers: Record<string, string> = {};
  if (options?.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options?.accessToken) {
    headers.Authorization = `Bearer ${options.accessToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers,
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
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

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    body: formData,
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

async function requestBlob(
  path: string,
  accessToken: string,
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new ApiError("Could not download the file.", response.status, "download_failed");
  }

  const disposition = response.headers.get("content-disposition");
  const match = disposition ? /filename="([^"]+)"/.exec(disposition) : null;
  return { blob: await response.blob(), filename: match?.[1] ?? null };
}

export const apiClient = {
  get: <T>(path: string, accessToken?: string) => request<T>(path, "GET", { accessToken }),
  post: <T>(path: string, body?: unknown, accessToken?: string) =>
    request<T>(path, "POST", { body, accessToken }),
  patch: <T>(path: string, body?: unknown, accessToken?: string) =>
    request<T>(path, "PATCH", { body, accessToken }),
  /** For multipart/form-data submissions (e.g. a resume upload) — the
   * browser sets the Content-Type boundary itself, so this deliberately
   * skips the JSON headers/serialization `request()` always applies. */
  postForm: <T>(path: string, formData: FormData) => requestForm<T>(path, formData),
  getBlob: (path: string, accessToken: string) => requestBlob(path, accessToken),
};
