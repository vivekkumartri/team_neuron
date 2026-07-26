"use client";

import { useState } from "react";

import { apiFetch } from "../../lib/api-client";
import { VoiceInputButton } from "../shared/VoiceInputButton";

/**
 * "Edit as revision" never edits the published chapter in place — submitting
 * only creates a DRAFT `chapter_revisions` row (`POST /chapters/:id/revisions`).
 * Approval and the resulting replacement branch happen out of band; this
 * form's copy reflects that explicitly so the author isn't misled into
 * thinking their patch already applied.
 */
export function RevisionRequestForm({ chapterId }: { chapterId: string }) {
  const [patch, setPatch] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "submitted" | "error">("idle");

  const submit = async () => {
    setStatus("submitting");
    try {
      await apiFetch(`/chapters/${chapterId}/revisions`, {
        method: "POST",
        body: { author_patch: patch },
      });
      setStatus("submitted");
    } catch {
      setStatus("error");
    }
  };

  if (status === "submitted") {
    return (
      <p role="status" className="rounded-lg border border-teal-300 bg-teal-950/20 p-3 text-sm">
        Revision requested. The original chapter is unchanged — if approved, this creates a new
        branch with your patch applied.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm">
        What should change?
        <div className="relative mt-1">
          <textarea
            value={patch}
            onChange={(event) => setPatch(event.target.value)}
            rows={4}
            className="w-full rounded-lg border border-stone-700 bg-[#11101a] p-3 pr-12"
          />
          <VoiceInputButton
            label="Speak your patch"
            onTranscript={(text) => setPatch((current) => (current.trim() ? `${current.trim()} ${text}` : text))}
          />
        </div>
      </label>
      {status === "error" && (
        <p role="alert" className="text-sm text-rose-300">
          Couldn't submit the revision request. Nothing was changed.
        </p>
      )}
      <button
        type="button"
        disabled={patch.trim().length === 0 || status === "submitting"}
        onClick={submit}
        className="rounded-lg bg-amber-300 px-4 py-2 font-medium text-stone-950 disabled:opacity-40"
      >
        {status === "submitting" ? "Requesting…" : "Request revision"}
      </button>
    </div>
  );
}
