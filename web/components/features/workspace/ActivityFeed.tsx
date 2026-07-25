"use client";

import { useEffect, useRef, useState } from "react";

import type { GenerationActivityEvent } from "../../../lib/generation-stream";

/**
 * Ordered agent activity feed with a "jump to latest" affordance once the
 * reader has scrolled up, and `prefers-reduced-motion` respected (no
 * auto-scroll animation when the user has that preference set).
 */
export function ActivityFeed({ events }: { events: GenerationActivityEvent[] }) {
  const listRef = useRef<HTMLOListElement>(null);
  const [pinnedToLatest, setPinnedToLatest] = useState(true);

  useEffect(() => {
    if (!pinnedToLatest || !listRef.current) return;
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    listRef.current.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }, [events, pinnedToLatest]);

  return (
    <div aria-live="polite" className="relative">
      <ol
        ref={listRef}
        onScroll={(event) => {
          const el = event.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
          setPinnedToLatest(atBottom);
        }}
        className="max-h-96 space-y-3 overflow-y-auto"
      >
        {events.map((event) => (
          <li key={event.sequence} className="rounded-lg border border-stone-700 p-3">
            <strong className="capitalize">{event.agent}</strong>
            <span className="mt-1 block text-sm text-stone-300">{event.summary}</span>
          </li>
        ))}
      </ol>
      {!pinnedToLatest && events.length > 0 && (
        <button
          type="button"
          onClick={() => setPinnedToLatest(true)}
          className="absolute bottom-2 right-2 rounded-full border border-teal-300 bg-[#191724] px-3 py-1 text-xs text-teal-200"
        >
          Jump to latest
        </button>
      )}
    </div>
  );
}
