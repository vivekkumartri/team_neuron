/**
 * Thin fetch wrapper for the FastAPI REST surface under `/api/v1`.
 *
 * Identity is asserted by Databricks Apps via `x-forwarded-user`/
 * `x-forwarded-email` request headers set at the proxy layer, not by this
 * client — the browser never needs to attach an auth header itself, only
 * `credentials: "include"` so the platform's session cookie rides along.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  idempotencyKey?: string;
}

const API_BASE = "/api/v1";

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    credentials: "include",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `Request to ${path} failed with ${response.status}`;
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

/** True once the current session has an authenticated, provisioned user. */
export async function isAuthenticated(): Promise<boolean> {
  try {
    await apiFetch("/me/preferences");
    return true;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return false;
    }
    // Any other failure (network, 5xx) is not an auth decision — surface it
    // as "not authenticated" for routing purposes only, never swallow it.
    return false;
  }
}
