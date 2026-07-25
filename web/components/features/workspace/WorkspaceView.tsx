"use client";

import { useEffect, useState } from "react";

import { apiFetch, ApiError } from "../../../lib/api-client";
import { useGenerationStream } from "../../../lib/generation-stream";
import { ActivityFeed } from "./ActivityFeed";
import { AgentCoordinationCanvas } from "./AgentCoordinationCanvas";
import { BranchControls, type ProgressionMode } from "./BranchControls";

interface ProgressionResponse {
  job_id: string;
  branch_id: string;
  status: string;
}

const MODE_TO_API: Record<ProgressionMode, "CONTINUE" | "EDIT_TRAITS" | "REWIND"> = {
  continue: "CONTINUE",
  "edit-traits": "EDIT_TRAITS",
  "jump-rewind": "REWIND",
};

/**
 * Replaces the earlier static `WorkspaceStudio` demo (whose three
 * progression buttons had no `onClick` at all) with the real, wired path:
 * `BranchControls` submits to `POST /branches/:id/progression`
 * (`api/routes/progression.py`), and once a job id comes back,
 * `useGenerationStream` opens the real SSE connection instead of the
 * `/api/v1/generation-events/demo` stand-in.
 */
export function WorkspaceView({ branchId }: { branchId: string }) {
  const [chapterId, setChapterId] = useState("");
  const [focalEntityId, setFocalEntityId] = useState("");
  const [traitChange, setTraitChange] = useState("");
  const [rewindTo, setRewindTo] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { events, connectionState, complete } = useGenerationStream(jobId);

  useEffect(() => {
    const activeBranch = window.localStorage.getItem("story-engine-active-branch");
    const activeJob = window.localStorage.getItem("story-engine-active-job");
    if (activeBranch === branchId && activeJob) {
      setJobId(activeJob);
    }
  }, [branchId]);

  const submit = async (mode: ProgressionMode) => {
    setError(null);
    setSubmitting(true);
    try {
      const response = await apiFetch<ProgressionResponse>(`/branches/${branchId}/progression`, {
        method: "POST",
        body: {
          chapter_id: chapterId,
          focal_entity_id: focalEntityId,
          mode: MODE_TO_API[mode],
          trait_change: mode === "edit-traits" ? traitChange || null : null,
          rewind_to_chapter_id: mode === "jump-rewind" ? rewindTo || null : null,
        },
      });
      setJobId(response.job_id);
      window.localStorage.setItem("story-engine-active-job", response.job_id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This branch already has an active generation job in progress.");
      } else if (err instanceof ApiError && err.status === 422) {
        setError(err.message);
      } else {
        setError("Couldn't submit that. Nothing changed.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[1fr_340px]">
      <article className="rounded-xl border border-stone-700 bg-[#191724] p-6">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
          Advance this branch
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            Chapter ID
            <input
              value={chapterId}
              onChange={(event) => setChapterId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 font-mono text-xs"
            />
          </label>
          <label className="block text-sm">
            Focal entity ID
            <input
              value={focalEntityId}
              onChange={(event) => setFocalEntityId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 font-mono text-xs"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            Trait change (only used for "Edit traits")
            <input
              value={traitChange}
              onChange={(event) => setTraitChange(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 text-sm"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            Rewind-to chapter ID (only used for "Jump / rewind")
            <input
              value={rewindTo}
              onChange={(event) => setRewindTo(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 font-mono text-xs"
            />
          </label>
        </div>
        {error && (
          <p role="alert" className="mt-3 text-sm text-rose-300">
            {error}
          </p>
        )}
        <div className="mt-6">
          <BranchControls onSelect={submit} disabled={submitting} />
        </div>
        {jobId && (
          <p className="mt-4 text-sm text-stone-400">
            Job <code>{jobId}</code> — {complete ? "complete" : connectionState}
          </p>
        )}
      </article>
      <aside aria-live="polite" className="rounded-xl border border-stone-700 bg-[#191724] p-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">
          Agent activity
        </p>
        <div className="mt-4">
          {jobId ? (
            <div className="space-y-4">
              <AgentCoordinationCanvas events={events} />
              <ActivityFeed events={events} />
            </div>
          ) : (
            <p className="text-sm text-stone-400">
              Submit a progression mode to start streaming activity.
            </p>
          )}
        </div>
      </aside>
    </section>
  );
}
