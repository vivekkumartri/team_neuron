"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiBase, apiFetch, ApiError } from "../../lib/api-client";

type NarrationStatus = "not_started" | "generating" | "ready" | "failed";

interface CharacterAudioLine {
  scene_index: number;
  kind: "scene_heading" | "action" | "dialogue";
  speaker: string | null;
  text: string;
  voice_id: string;
  audio_base64: string;
}

interface NarrationStatusResponse {
  status: NarrationStatus;
  estimated_seconds: number | null;
  error: string | null;
  // Only NEW lines since the `since` index this poll asked for — not the
  // full history. `total_lines` is the true running count.
  lines: CharacterAudioLine[] | null;
  total_lines: number;
}

const POLL_INTERVAL_MS = 4_000;

function base64ToObjectUrl(base64: string): string {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
}

function formatEstimate(seconds: number | null): string {
  if (!seconds) return "a few minutes";
  const minutes = Math.round(seconds / 60);
  return minutes <= 1 ? "about a minute" : `${minutes - 1}-${minutes} minutes`;
}

/**
 * Multi-voice narration for one chapter (`api/routes/character_voice.py`'s
 * `POST`/`GET .../narration`). Generation runs as a background job on the
 * server, and each character's line (3-4 seconds of audio) is pushed onto
 * the job the moment it finishes rather than batched until the whole
 * chapter is done (`services/narration_jobs.py`'s `on_line` callback) — this
 * polls status every few seconds and appends newly-finished lines to the
 * list as they show up, so playback can start well before generation ends.
 */
export function ChapterNarrationTab({ chapterId }: { chapterId: string }) {
  const [state, setState] = useState<NarrationStatusResponse | null>(null);
  const [lines, setLines] = useState<CharacterAudioLine[]>([]);
  const [audioUrls, setAudioUrls] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [combinedAudioUrl, setCombinedAudioUrl] = useState<string | null>(null);
  const [combinedAudioError, setCombinedAudioError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const knownLineCount = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyResponse = useCallback((response: NarrationStatusResponse) => {
    setState(response);

    // The server already trims to just-new lines via `?since=`, so this is
    // a plain append — no re-decoding of earlier (potentially many MB of)
    // base64 audio on every poll, which is what made this look frozen/empty
    // on any chapter past a handful of lines.
    const newOnes = response.lines ?? [];
    if (newOnes.length > 0) {
      setLines((current) => [...current, ...newOnes]);
      setAudioUrls((current) => [
        ...current,
        ...newOnes.map((line) => base64ToObjectUrl(line.audio_base64)),
      ]);
    }
    knownLineCount.current = response.total_lines;

    if (response.status === "ready" || response.status === "failed") {
      stopPolling();
    }
  }, [stopPolling]);

  const checkStatus = useCallback(async () => {
    try {
      const response = await apiFetch<NarrationStatusResponse>(
        `/voice/chapters/${chapterId}/narration?since=${knownLineCount.current}`,
      );
      applyResponse(response);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't check narration status.");
    }
  }, [chapterId, applyResponse]);

  const resetLines = useCallback(() => {
    knownLineCount.current = 0;
    setLines([]);
    setAudioUrls((current) => {
      current.forEach((url) => URL.revokeObjectURL(url));
      return [];
    });
    setCombinedAudioUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    setCombinedAudioError(null);
  }, []);

  useEffect(() => {
    resetLines();
    void checkStatus();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId]);

  // Once the whole chapter is ready, fetch the single joined track exactly
  // once (not part of the polled JSON status, which stays small on purpose)
  // — every character's chunk, back to back, in script order.
  useEffect(() => {
    if (state?.status !== "ready" || combinedAudioUrl || combinedAudioError) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${apiBase()}/voice/chapters/${chapterId}/narration/audio`, {
          credentials: "include",
        });
        if (!response.ok) {
          if (!cancelled) setCombinedAudioError("Couldn't load the joined chapter audio.");
          return;
        }
        const blob = await response.blob();
        if (cancelled) return;
        setCombinedAudioUrl(URL.createObjectURL(blob));
      } catch {
        if (!cancelled) setCombinedAudioError("Couldn't load the joined chapter audio.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.status, chapterId]);

  const startGeneration = async () => {
    setError(null);
    // A POST always (re)starts from the beginning — either the very first
    // run, or a fresh job after a failure — so whatever's currently shown
    // belongs to a job this call is about to replace.
    resetLines();
    try {
      const response = await apiFetch<NarrationStatusResponse>(
        `/voice/chapters/${chapterId}/narration`,
        { method: "POST" },
      );
      applyResponse(response);
      if (response.status === "generating") {
        stopPolling();
        pollRef.current = setInterval(() => void checkStatus(), POLL_INTERVAL_MS);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start narration generation.");
    }
  };

  useEffect(() => {
    if (state?.status === "generating" && !pollRef.current) {
      pollRef.current = setInterval(() => void checkStatus(), POLL_INTERVAL_MS);
    }
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.status]);

  if (!state) {
    return <p className="text-sm text-stone-400">Checking narration status…</p>;
  }

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}

      {state.status === "not_started" && (
        <div className="rounded-lg border border-stone-700 bg-[#11101a] p-4 text-sm">
          <p className="text-stone-300">Narration hasn't been generated for this chapter yet.</p>
          <button
            type="button"
            onClick={() => void startGeneration()}
            className="mt-3 rounded-lg bg-teal-300 px-4 py-2 text-sm font-medium text-stone-950"
          >
            Generate narration
          </button>
        </div>
      )}

      {state.status === "generating" && (
        <div
          role="status"
          className="rounded-lg border border-teal-400/50 bg-teal-950/20 p-4 text-sm text-teal-100"
        >
          <p>
            It's generating — this can take {formatEstimate(state.estimated_seconds)}. Each
            character's line appears below as soon as it's ready.
          </p>
        </div>
      )}

      {state.status === "failed" && (
        <div className="rounded-lg border border-rose-400/50 bg-rose-950/20 p-4 text-sm text-rose-100">
          <p>Narration generation failed{state.error ? `: ${state.error}` : "."}</p>
          {lines.length > 0 && (
            <p className="mt-1 text-xs text-rose-200/80">
              The {lines.length} line{lines.length === 1 ? "" : "s"} it finished before stopping
              are still playable below.
            </p>
          )}
          <button
            type="button"
            onClick={() => void startGeneration()}
            className="mt-3 rounded-lg border border-rose-300/60 px-3 py-2 text-xs text-rose-200"
          >
            Try again
          </button>
        </div>
      )}

      {state.status === "ready" && (
        <div className="rounded-lg border border-teal-400/50 bg-teal-950/20 p-3 text-sm">
          <p className="font-medium text-teal-200">Full chapter (all lines joined)</p>
          {combinedAudioUrl && <audio controls src={combinedAudioUrl} className="mt-2 w-full" />}
          {combinedAudioError && (
            <p className="mt-1 text-xs text-rose-300">{combinedAudioError}</p>
          )}
          {!combinedAudioUrl && !combinedAudioError && (
            <p className="mt-1 text-xs text-teal-300/80">Loading joined track…</p>
          )}
        </div>
      )}

      {lines.length > 0 && (
        <ol className="space-y-3">
          {lines.map((line, index) => (
            <li key={index} className="rounded-lg border border-stone-700 bg-[#11101a] p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-teal-200">
                  {line.speaker ?? (line.kind === "scene_heading" ? "Scene" : "Narrator")}
                </span>
                <span className="text-xs text-stone-500">{line.voice_id}</span>
              </div>
              <p className="mt-1 text-stone-300">{line.text}</p>
              <audio controls src={audioUrls[index]} className="mt-2 w-full" />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
