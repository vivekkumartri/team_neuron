"use client";

import { useEffect, useRef } from "react";

import { ROUTES } from "../../lib/routes";

export function MobileDrawer({
  open,
  pathname,
  onNavigate,
  onClose,
}: {
  open: boolean;
  pathname: string;
  onNavigate: (path: string) => void;
  onClose: () => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      closeButtonRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
      <button
        type="button"
        aria-label="Close navigation"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <nav className="relative z-50 flex h-full w-80 flex-col bg-[linear-gradient(180deg,#181522_0%,#14111d_52%,#110f18_100%)] px-5 py-6 shadow-xl">
        <div className="rounded-[24px] border border-teal-300/12 bg-[radial-gradient(circle_at_top,rgba(45,212,191,0.14),transparent_55%),linear-gradient(180deg,rgba(28,24,39,0.96),rgba(21,19,30,0.9))] p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.28em] text-teal-300">Story Engine</p>
              <h2 className="mt-4 text-lg font-semibold tracking-[-0.02em] text-stone-50">
                Build your next branching story.
              </h2>
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className="rounded-xl border border-stone-700 px-3 py-2 text-sm text-stone-300 transition-colors hover:bg-stone-800"
            >
              Close
            </button>
          </div>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            Move through story setup, workspace, world, endings, and reports from one clean rail.
          </p>
        </div>
        <div className="mt-8 flex-1">
          <p className="px-3 text-[11px] font-medium uppercase tracking-[0.24em] text-stone-500">
            Navigation
          </p>
          <ul className="mt-3 space-y-2">
            {ROUTES.map((route, index) => {
              const isActive = pathname === route.path;
              return (
                <li key={route.id}>
                  <button
                    type="button"
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => {
                      onNavigate(route.path);
                      onClose();
                    }}
                    className={`flex w-full items-center gap-4 rounded-2xl border px-4 py-3 text-left transition-all duration-200 ${
                      isActive
                        ? "border-teal-300/30 bg-[linear-gradient(135deg,rgba(20,184,166,0.18),rgba(20,24,35,0.92))] text-teal-50 shadow-[0_10px_24px_rgba(13,148,136,0.16)]"
                        : "border-transparent text-stone-300 hover:border-stone-700 hover:bg-white/[0.03] hover:text-stone-100"
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-semibold ${
                        isActive
                          ? "bg-teal-300/14 text-teal-100"
                          : "bg-stone-900/70 text-stone-400"
                      }`}
                    >
                      0{index + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{route.label}</span>
                      <span className={`block text-xs ${isActive ? "text-teal-100/75" : "text-stone-500"}`}>
                        {route.id === "onboarding" && "Create the starting prompt"}
                        {route.id === "workspace" && "Continue the active branch"}
                        {route.id === "world" && "Review setting and canon"}
                        {route.id === "endings" && "Shape outcome directions"}
                        {route.id === "reports" && "Inspect story intelligence"}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="rounded-2xl border border-stone-800 bg-black/20 px-4 py-4">
          <p className="text-xs uppercase tracking-[0.2em] text-stone-500">Studio note</p>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            The drawer mirrors the full-height sidebar so the navigation feels consistent on mobile too.
          </p>
        </div>
      </nav>
    </div>
  );
}
