"use client";

import { useState } from "react";

import { ApiError, apiFetch } from "../../../lib/api-client";
import type { CastCharacter } from "./CastEditor";
import type { StoryLanguageCode } from "./LanguagePicker";

/**
 * Locking creates the story's first arc, branch, and focal character, then
 * immediately queues Chapter 1. No sample chapter is shown as real output.
 */
export function CastLock({
  seed,
  language,
  cast,
  onLocked,
}: {
  seed: string;
  language: StoryLanguageCode;
  cast: CastCharacter[];
  onLocked: (storyId: string) => void;
}) {
  const [locking, setLocking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lockCast = async () => {
    setLocking(true);
    setError(null);
    try {
      const story = await apiFetch<{
        id: string;
        language: string;
        initial_branch_id: string | null;
        initial_focal_entity_id: string | null;
      }>("/stories", {
        method: "POST",
        body: {
          title: seed.slice(0, 200),
          personalization_enabled: true,
          language,
          cast,
        },
      });
      if (!story.initial_branch_id || !story.initial_focal_entity_id) {
        throw new Error("The story did not receive its initial branch.");
      }
      // `POST /stories` creates the character `entities` but never touches
      // `cast_members` — locking the cast is a separate step
      // (`POST /stories/:id/cast-lock`, `api/routes/cast.py`) that this
      // screen's "Lock cast" button never actually called. Without it,
      // `cast_members` stayed empty for every story created through this
      // flow, which is why the workspace's "Focal character" dropdown (and
      // the Cast panel) always showed no options despite characters existing.
      await apiFetch(`/stories/${story.id}/cast-lock`, { method: "POST" });
      // Stored so `VoiceInputButton` instances elsewhere in the app (which
      // don't otherwise have the current story object in scope) can pass a
      // language hint to `WS /api/v1/voice/transcribe` — the same
      // localStorage-for-cross-flow-state convention already used for
      // `story-engine-active-branch`/`story-engine-active-job` below.
      window.localStorage.setItem("story-engine-story-language", story.language);
      const job = await apiFetch<{ job_id: string }>(
        `/branches/${story.initial_branch_id}/progression`,
        {
          method: "POST",
          idempotencyKey: `chapter-1-${story.id}`,
          body: {
            chapter_id: null,
            focal_entity_id: story.initial_focal_entity_id,
            mode: "CONTINUE",
            trait_change: null,
            rewind_to_chapter_id: null,
          },
        },
      );
      window.localStorage.setItem("story-engine-active-branch", story.initial_branch_id);
      window.localStorage.setItem("story-engine-active-job", job.job_id);
      // So `WorkspaceView` can prefill "Focal entity ID" for this branch
      // instead of requiring the author to hand-type a raw UUID (which,
      // left blank, sent "" and produced a 422 the UI rendered unreadably).
      window.localStorage.setItem(
        `story-engine-focal-entity-${story.initial_branch_id}`,
        story.initial_focal_entity_id,
      );
      onLocked(story.id);
    } catch (caught) {
      // Surface the real backend reason instead of a generic message — a
      // silent catch-all here is exactly what hid the duplicate-cast-name
      // 500 (`entities` has UNIQUE (story_id, name)) from the author.
      if (caught instanceof ApiError) {
        setError(
          caught.status === 409
            ? "Two characters in your cast have the same name — give each a unique name and try again."
            : `Couldn't lock the cast: ${caught.message}`,
        );
      } else if (caught instanceof Error) {
        setError(`Couldn't lock the cast: ${caught.message}`);
      } else {
        setError("Couldn't lock the cast — nothing was created. Try again.");
      }
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
