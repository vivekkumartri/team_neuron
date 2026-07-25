"use client";

import { useCallback, useEffect, useState } from "react";

import { DEFAULT_ROUTE, matchRoute, type RouteDefinition } from "./routes";

function currentPathname(): string {
  if (typeof window === "undefined") {
    return DEFAULT_ROUTE.path;
  }
  return window.location.pathname;
}

/** Minimal client-side router: tracks `pathname`, exposes `navigate`. */
export function useClientRouter(): {
  pathname: string;
  route: RouteDefinition | undefined;
  navigate: (path: string) => void;
} {
  const [pathname, setPathname] = useState<string>(currentPathname);

  useEffect(() => {
    const onPopState = () => setPathname(currentPathname());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((path: string) => {
    window.history.pushState({}, "", path);
    setPathname(path);
  }, []);

  return { pathname, route: matchRoute(pathname), navigate };
}
