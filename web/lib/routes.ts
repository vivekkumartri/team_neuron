/**
 * Client-side route table for the static-export SPA shell.
 *
 * FastAPI's `SPAStaticFiles` (see `src/story_engine/app.py`) serves
 * `index.html` for any path without a file extension that isn't a static
 * asset, so navigation here is client-side `pushState` matched against this
 * table — there is no Next.js dynamic routing at runtime.
 */

export type RouteId =
  | "onboarding"
  | "workspace"
  | "world"
  | "endings"
  | "reports";

export interface RouteDefinition {
  id: RouteId;
  path: string;
  label: string;
  /** Whether this route requires an authenticated session before rendering. */
  protected: boolean;
}

export const ROUTES: readonly RouteDefinition[] = [
  { id: "onboarding", path: "/onboarding", label: "Start a story", protected: false },
  { id: "workspace", path: "/workspace", label: "Workspace", protected: true },
  { id: "world", path: "/world", label: "World", protected: true },
  { id: "endings", path: "/endings", label: "Endings", protected: true },
  { id: "reports", path: "/reports", label: "Reports", protected: true },
];

export function matchRoute(pathname: string): RouteDefinition | undefined {
  return ROUTES.find((route) => pathname === route.path || pathname.startsWith(`${route.path}/`));
}

export const DEFAULT_ROUTE: RouteDefinition = ROUTES[0];
