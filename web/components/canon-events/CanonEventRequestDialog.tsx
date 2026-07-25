"use client";

import { useState } from "react";

import { apiFetch } from "../../lib/api-client";
import { VoiceInputButton } from "../shared/VoiceInputButton";

/**
 * Requesting a canon event (including a "kill"/removal event) never changes
 * state on submit — it only ever creates a `DRAFT` row via
 * `POST /branches/:id/canon-event-requests` (Task 4G.2). The world agent's
 * commit/adjust/reject decision happens later, out of band; this dialog
 * shows the target, the branch, and an explicit permanent-record warning
 * before requesting, then a pending status after — never a kill/revive
 * handler that mutates immediately (the retired prototype pattern this must
 * not repeat).
 */
// Must match `story_engine.services.canon_events.CanonEventType` exactly —
// the backend's `canon_event_requests.event_type` CHECK constraint (migration
// 0009) only accepts these five values.
export type CanonEventType = "KILL" | "REVIVE" | "MOVE_REALM" | "INTRODUCE_ENTITY" | "EDIT_CANON";

const EVENT_TYPES_REQUIRING_TARGET: readonly CanonEventType[] = ["KILL", "REVIVE", "MOVE_REALM"];

interface Props {
  branchId: string;
  eventType: CanonEventType;
  targetEntityId?: string;
  targetLabel: string;
  onRequested: () => void;
}

export function CanonEventRequestDialog({
  branchId,
  eventType,
  targetEntityId,
  targetLabel,
  onRequested,
}: Props) {
  const [rationale, setRationale] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [status, setStatus] = useState<"idle" | "submitting" | "requested" | "error">("idle");

  const isPermanentLooking = eventType === "KILL";
  const requiresTarget = EVENT_TYPES_REQUIRING_TARGET.includes(eventType);

  const submit = async () => {
    if (requiresTarget && !targetEntityId) {
      setStatus("error");
      return;
    }
    setStatus("submitting");
    try {
      await apiFetch(`/branches/${branchId}/canon-event-requests`, {
        method: "POST",
        body: {
          event_type: eventType,
          target_entity_id: targetEntityId ?? null,
          proposed_payload: {},
          rationale: rationale || null,
        },
      });
      setStatus("requested");
      onRequested();
    } catch {
      setStatus("error");
    }
  };

  if (status === "requested") {
    return (
      <p role="status" className="rounded-lg border border-teal-300 bg-teal-950/20 p-3 text-sm">
        Request submitted for {targetLabel} on this branch. It's pending evaluator and world
        review — nothing has changed yet.
      </p>
    );
  }

  return (
    <div role="dialog" aria-label={`Request: ${eventType}`} className="space-y-3 rounded-lg border border-stone-700 p-4">
      <p className="text-sm text-stone-300">
        Target: <strong>{targetLabel}</strong> · Branch: <code>{branchId}</code>
      </p>
      {isPermanentLooking && (
        <p role="alert" className="text-sm text-amber-200">
          This becomes a permanent record if approved. It will not take effect immediately —
          the world agent reviews it first.
        </p>
      )}
      <label className="block text-sm">
        Why? (optional)
        <textarea
          value={rationale}
          onChange={(event) => setRationale(event.target.value)}
          rows={2}
          className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2"
        />
      </label>
      <VoiceInputButton
        label="Speak rationale"
        onTranscript={(text) =>
          setRationale((current) => (current.trim() ? `${current.trim()} ${text}` : text))
        }
      />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
        I understand this only submits a request for review.
      </label>
      {status === "error" && (
        <p role="alert" className="text-sm text-rose-300">
          Request failed. Nothing was submitted.
        </p>
      )}
      <button
        type="button"
        disabled={!confirmed || status === "submitting"}
        onClick={submit}
        className="rounded-lg bg-amber-300 px-4 py-2 font-medium text-stone-950 disabled:opacity-40"
      >
        {status === "submitting" ? "Submitting…" : "Submit request"}
      </button>
    </div>
  );
}
