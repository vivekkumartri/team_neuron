"use client";

import { useEffect, useState } from "react";

import { isAuthenticated } from "../../lib/api-client";

type Status = "checking" | "authenticated" | "unauthenticated";

/**
 * Gates a protected route on a real `/me/preferences` auth check rather than
 * assuming a session is valid. Renders an unauthenticated redirect prompt
 * (rather than silently blanking the page) so Playwright can assert on it
 * without needing a live backend.
 */
export function ProtectedRoute({
  children,
  onRedirect,
}: {
  children: React.ReactNode;
  onRedirect: () => void;
}) {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    isAuthenticated().then((ok) => {
      if (cancelled) return;
      setStatus(ok ? "authenticated" : "unauthenticated");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (status === "unauthenticated") {
      onRedirect();
    }
  }, [status, onRedirect]);

  if (status === "checking") {
    return (
      <p role="status" className="p-6 text-stone-400">
        Checking your session…
      </p>
    );
  }

  if (status === "unauthenticated") {
    return (
      <p role="alert" className="p-6 text-stone-400">
        Redirecting to sign-in…
      </p>
    );
  }

  return <>{children}</>;
}
