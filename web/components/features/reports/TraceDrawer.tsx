"use client";

import { useState } from "react";

import { apiFetch, ApiError } from "../../../lib/api-client";

interface AgentRun {
  id: string;
  agent_label: string;
  status: string;
  redacted_summary: string;
}

/**
 * Trace drawer gated by `stories.agent_trace_enabled` — the backend enforces
 * this by returning 404 for a run whose story has tracing disabled (see
 * `get_agent_run` in `traces.py`), not just by hiding the UI affordance.
 *
 * Known backend gap: there's no "list runs for this job" endpoint yet, only
 * lookup by a known `run_id` — so this drawer takes a run id directly rather
 * than offering a picker. A future `GET /generation-jobs/:id/agent-runs`
 * would remove that limitation.
 */
export function TraceDrawer({ runId }: { runId: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "disabled" | "error" | "loaded">("idle");

  const open = async () => {
    setState("loading");
    try {
      const data = await apiFetch<AgentRun>(`/agent-runs/${runId}`);
      setRun(data);
      setState("loaded");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setState("disabled");
      } else {
        setState("error");
      }
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={open}
        className="rounded-lg border border-stone-600 px-3 py-2 text-sm text-stone-200"
      >
        View agent trace
      </button>
      {state === "loading" && <p className="mt-2 text-sm text-stone-400">Loading trace…</p>}
      {state === "disabled" && (
        <p className="mt-2 text-sm text-stone-400">
          Agent traces are off for this story, or this run isn't visible.
        </p>
      )}
      {state === "error" && (
        <p role="alert" className="mt-2 text-sm text-rose-300">
          Couldn't load the trace.
        </p>
      )}
      {state === "loaded" && run && (
        <div className="mt-3 rounded-lg border border-stone-700 p-3 text-sm">
          <p className="font-semibold capitalize">{run.agent_label}</p>
          <p className="text-stone-400">{run.status}</p>
          <p className="mt-2 text-stone-200">{run.redacted_summary}</p>
        </div>
      )}
    </div>
  );
}
