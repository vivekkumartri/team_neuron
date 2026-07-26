"use client";

import { ROUTES } from "../../lib/routes";
import { useDemoMode } from "../../lib/demo-mode";

export function Sidebar({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate: (path: string) => void;
}) {
  const [demoMode, setDemoMode] = useDemoMode();

  return (
    <nav
      aria-label="Primary"
      className="hidden w-60 shrink-0 border-r border-stone-700 bg-[#191724] p-4 md:block"
    >
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-teal-300">Brahma</p>
      <ul className="mt-6 space-y-1">
        {ROUTES.map((route) => {
          const isActive = pathname === route.path;
          return (
            <li key={route.id}>
              <button
                type="button"
                aria-current={isActive ? "page" : undefined}
                onClick={() => onNavigate(route.path)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  isActive
                    ? "bg-teal-950/40 text-teal-200"
                    : "text-stone-300 hover:bg-stone-800"
                }`}
              >
                {route.label}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-8 border-t border-stone-800 pt-4">
        <label className="flex items-center justify-between gap-2 text-xs text-stone-400">
          <span>
            Demo mode
            <span className="mt-0.5 block text-[11px] text-stone-500">
              Replay saved stories, no live generation
            </span>
          </span>
          <input
            type="checkbox"
            checked={demoMode}
            onChange={(event) => setDemoMode(event.target.checked)}
            className="h-4 w-4 accent-violet-400"
          />
        </label>
      </div>
    </nav>
  );
}
