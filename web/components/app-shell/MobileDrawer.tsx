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
      <nav className="relative z-50 h-full w-72 bg-[#191724] p-4 shadow-xl">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-teal-300">Brahma</p>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-stone-300 hover:bg-stone-800"
          >
            Close
          </button>
        </div>
        <ul className="mt-6 space-y-1">
          {ROUTES.map((route) => {
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
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                    isActive ? "bg-teal-950/40 text-teal-200" : "text-stone-300 hover:bg-stone-800"
                  }`}
                >
                  {route.label}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
