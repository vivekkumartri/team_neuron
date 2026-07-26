/**
 * Thin fetch wrapper for the FastAPI REST surface under `/api/v1`.
 *
 * Identity is asserted by Databricks Apps via `x-forwarded-user`/
 * `x-forwarded-email` request headers set at the proxy layer, not by this
 * client — the browser never needs to attach an auth header itself, only
 * `credentials: "include"` so the platform's session cookie rides along.
 */

import { isDemoModeOn } from "./demo-mode";
import { DemoApiError, handleDemoRequest } from "./demo-runtime";

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

// In production (and for `npm run build` served by the FastAPI app itself)
// the frontend and API share one origin, so a relative path is correct.
// Running `npm run dev` on its own port (e.g. localhost:3000) has no such
// shared origin — there is no `/api/v1` route on the Next.js dev server
// itself, only on the separately-running FastAPI backend — which is why
// requests 404 unless this points at that backend directly. Set
// `NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1` in `web/.env.local`
// for that workflow (see LOCAL_DEV.md).
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

/**
 * Exported so every other place that talks to the API — the SSE
 * `EventSource` in `generation-stream.ts`, the raw `fetch` in
 * `ChapterNarrationPlayer.tsx`, the WebSocket in `voice-stream.ts` — resolves
 * against the same backend `apiFetch` uses, instead of each hardcoding
 * `/api/v1/...` (which 404s against the Next.js dev server on its own port;
 * see `NEXT_PUBLIC_API_BASE` in `LOCAL_DEV.md`).
 */
export function apiBase(): string {
  return API_BASE;
}

/** Same base, but as a `ws(s)://` URL, for `voice-stream.ts`'s WebSocket. */
export function apiWsBase(): string {
  if (/^https?:\/\//.test(API_BASE)) {
    return API_BASE.replace(/^http/, "ws");
  }
  const protocol =
    typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = typeof window !== "undefined" ? window.location.host : "";
  return `${protocol}//${host}${API_BASE}`;
}

/**
 * FastAPI's `detail` field isn't always a string: request-validation
 * failures (422s raised by Pydantic itself, before a route body even runs)
 * return `detail` as an ARRAY of `{loc, msg, type}` objects, and some routes
 * (e.g. content-policy rejections) return a plain object. A bare
 * `String(detail)` renders those as "[object Object]" (or, for an array of
 * two errors, the genuinely confusing "[object Object],[object Object]" —
 * this is exactly what an author saw when a required field was sent blank).
 * This extracts a readable message for every shape FastAPI actually sends.
 */
function formatErrorDetail(detail: unknown, path: string, status: number): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = "loc" in item && Array.isArray((item as { loc: unknown }).loc)
            ? (item as { loc: unknown[] }).loc.filter((part) => part !== "body").join(".")
            : undefined;
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .filter(Boolean);
    return messages.length ? messages.join("; ") : `Request to ${path} failed with ${status}`;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      return `Request to ${path} failed with ${status}`;
    }
  }
  return `Request to ${path} failed with ${status}`;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // Demo mode: every onboarding/workspace call gets answered from a saved
  // local bundle instead of the real backend — see `demo-runtime.ts` for
  // the full covered surface. `/demo/*` itself is excluded so the demo
  // picker and `demo-runtime.ts`'s own bundle loader can still reach the
  // real (unauthenticated, static-file) `/api/v1/demo/*` endpoints.
  if (isDemoModeOn() && !path.startsWith("/demo/")) {
    try {
      const result = await handleDemoRequest(path, options);
      if (result !== undefined) {
        return result as T;
      }
    } catch (error) {
      if (error instanceof DemoApiError) {
        throw new ApiError(error.status, error.message);
      }
      throw error;
    }
  }

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
        ? formatErrorDetail((payload as { detail: unknown }).detail, path, response.status)
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
