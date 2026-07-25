"use client";

import { useState } from "react";

import { apiFetch, ApiError } from "../../../lib/api-client";

/**
 * Archive/unarchive and blocked-generation retry, against the real routes
 * added in `api/routes/archive.py` (Track 6): `PATCH /chapters/:id/archive`,
 * `.../unarchive`, and `POST /generation-jobs/:id/retry`. Archiving is a
 * reversible flag, never a delete; retry creates a fresh job rather than
 * resetting the failed one in place.
 */
export function RecoveryControls({
  chapterId,
  archived,
  blockedJobId,
  onChanged,
}: {
  chapterId: string;
  archived: boolean;
  blockedJobId?: string;
  onChanged?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retried, setRetried] = useState<string | null>(null);

  const toggleArchive = async () => {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/chapters/${chapterId}/${archived ? "unarchive" : "archive"}`, {
        method: "PATCH",
      });
      onChanged?.();
    } catch {
      setError("Couldn't update the archive state. Nothing changed.");
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!blockedJobId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await apiFetch<{ job_id: string }>(
        `/generation-jobs/${blockedJobId}/retry`,
        { method: "POST" },
      );
      setRetried(response.job_id);
      onChanged?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This job isn't in a retryable state anymore.");
      } else {
        setError("Couldn't retry — nothing changed.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        disabled={busy}
        onClick={toggleArchive}
        className="rounded-lg border border-stone-600 px-3 py-2 text-sm text-stone-200 disabled:opacity-40"
      >
        {archived ? "Unarchive" : "Archive"}
      </button>
      {blockedJobId && (
        <button
          type="button"
          disabled={busy || retried !== null}
          onClick={retry}
          className="rounded-lg bg-amber-300 px-3 py-2 text-sm font-medium text-stone-950 disabled:opacity-40"
        >
          {retried ? "Retry queued" : "Retry generation"}
        </button>
      )}
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}
