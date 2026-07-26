"use client";

import { useState } from "react";

import { useClientRouter } from "../../lib/client-router";
import { DEFAULT_ROUTE } from "../../lib/routes";
import { ErrorBoundary } from "./ErrorBoundary";
import { MobileDrawer } from "./MobileDrawer";
import { ProtectedRoute } from "./ProtectedRoute";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname, route, navigate } = useClientRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const redirectToOnboarding = () => navigate(DEFAULT_ROUTE.path);
  const body = route?.protected ? (
    <ProtectedRoute onRedirect={redirectToOnboarding}>{children}</ProtectedRoute>
  ) : (
    children
  );

  return (
    <div className="min-h-screen bg-[#11101a] text-stone-100">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-md focus:bg-teal-300 focus:px-3 focus:py-2 focus:text-stone-950"
      >
        Skip to main content
      </a>
      <div className="flex">
        <Sidebar pathname={pathname} onNavigate={navigate} />
        <MobileDrawer
          open={drawerOpen}
          pathname={pathname}
          onNavigate={navigate}
          onClose={() => setDrawerOpen(false)}
        />
        <div className="flex-1">
          <header className="flex items-center justify-between border-b border-stone-700 p-4 md:hidden">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-teal-300">
              Brahma
            </p>
            <button
              type="button"
              aria-label="Open navigation"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
              className="rounded-md border border-stone-700 px-3 py-2 text-sm"
            >
              Menu
            </button>
          </header>
          <main id="main-content" className="p-4 md:p-8">
            <ErrorBoundary>{body}</ErrorBoundary>
          </main>
        </div>
      </div>
    </div>
  );
}
