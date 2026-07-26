"use client";

import { ROUTES } from "../../lib/routes";

export function Sidebar({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate: (path: string) => void;
}) {
  return (
    <nav
      aria-label="Primary"
      className="sticky top-0 hidden h-screen w-72 shrink-0 border-r border-stone-700/80 bg-[linear-gradient(180deg,#181522_0%,#14111d_52%,#110f18_100%)] md:block"
    >
      <div className="flex h-full flex-col px-5 py-6">
        <div className="rounded-[24px] border border-teal-300/12 bg-[radial-gradient(circle_at_top,rgba(45,212,191,0.14),transparent_55%),linear-gradient(180deg,rgba(28,24,39,0.96),rgba(21,19,30,0.9))] p-5 shadow-[0_18px_38px_rgba(0,0,0,0.28)]">
          <p className="font-mono text-xs uppercase tracking-[0.28em] text-teal-300">Story Engine</p>
          <h2 className="mt-4 text-lg font-semibold tracking-[-0.02em] text-stone-50">
            Build your next branching story.
          </h2>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            Start with a seed, then shape the world, cast, endings, and reports from one place.
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
                    onClick={() => onNavigate(route.path)}
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
            Voice, drafting, and story controls all stay in this rail-driven flow, so the layout now stretches edge to edge.
          </p>
        </div>
      </div>
    </nav>
  );
}
