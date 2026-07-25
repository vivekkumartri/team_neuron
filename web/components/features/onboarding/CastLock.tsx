"use client";

import { useState } from "react";

import { apiFetch } from "../../../lib/api-client";

/**
 * Family-tree/cast summary and a real cast-lock endpoint don't exist in the
 * backend yet (only `POST /api/v1/stories` with a bare `title` does) — see
 * task.md Task 4H.2 status note. This view creates the story with the seed
 * as its title so the flow is real end-to-end against what exists today,
 * and is the seam where a dedicated cast/family-tree payload would attach
 * once that endpoint exists.
 */
export function CastLock({
  seed,
  onLocked,
}: {
  seed: string;
  onLocked: (storyId: string) => void;
}) {
  const [locking, setLocking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lockCast = async () => {
    setLocking(true);
    setError(null);
    try {
      const story = await apiFetch<{ id: string }>("/stories", {
        method: "POST",
        body: { title: seed.slice(0, 200), personalization_enabled: true },
      });
      onLocked(story.id);
    } catch {
      setError("Couldn't lock the cast — nothing was created. Try again.");
    } finally {
      setLocking(false);
    }
  };

  return (
    <div className="space-y-4 rounded-xl border border-stone-700 bg-[#191724] p-6">
      <h2 className="text-xl font-semibold">Lock your cast</h2>
      <p className="text-sm text-stone-300">
        Once locked, Chapter 1 begins generating immediately. You can still edit traits and
        branch later — locking starts the story, it doesn't fix it in place forever.
      </p>
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      <button
        type="button"
        onClick={lockCast}
        disabled={locking}
        className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:opacity-40"
      >
        {locking ? "Locking cast…" : "Lock cast & start Chapter 1"}
      </button>
    </div>
  );
}
