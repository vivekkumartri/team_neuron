"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch, ApiError } from "../../lib/api-client";

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
  lines: CharacterAudioLine[] | null;
}

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
 * server because a full chapter's worth of IndicF5 zero-shot lines
 * realistically takes several minutes, so this polls status instead of
 * blocking a single request.
 */
export function ChapterNarrationTab({ chapterId }: { chapterId: string }) {
  const [state, setState] = useState<NarrationStatusResponse | null>(null);
  const [lines, setLines] = useState<CharacterAudioLine[]>([]);
  const [audioUrls, setAudioUrls] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyResponse = useCallback(
    (response: NarrationStatusResponse) => {
      setState(response);
      if (response.status === "ready" && response.lines) {
        audioUrls.forEach((url) => URL.revokeObjectURL(url));
        setLines(response.lines);
        setAudioUrls(response.lines.map((line) => base64ToObjectUrl(line.audio_base64)));
        stopPolling();
      }
      if (response.status === "failed") {
        stopPolling();
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stopPolling],
  );

  const checkStatus = useCallback(async () => {
    try {
      const response = await apiFetch<NarrationStatusResponse>(
        `/voice/chapters/${chapterId}/narration`,
      );
      applyResponse(response);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't check narration status.");
    }
  }, [chapterId, applyResponse]);

  useEffect(() => {
    void checkStatus();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId]);

  const startGeneration = async () => {
    setError(null);
    try {
      const response = await apiFetch<NarrationStatusResponse>(
        `/voice/chapters/${chapterId}/narration`,
        { method: "POST" },
      );
      applyResponse(response);
      if (response.status === "generating") {
        stopPolling();
        pollRef.current = setInterval(() => void checkStatus(), 10_000);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start narration generation.");
    }
  };

  useEffect(() => {
    if (state?.status === "generating" && !pollRef.current) {
      pollRef.current = setInterval(() => void checkStatus(), 10_000);
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
          <p>It's generating — this can take {formatEstimate(state.estimated_seconds)}.</p>
          <p className="mt-1 text-xs text-teal-300/80">
            You can leave this tab and come back; it keeps generating in the background.
          </p>
        </div>
      )}

      {state.status === "failed" && (
        <div className="rounded-lg border border-rose-400/50 bg-rose-950/20 p-4 text-sm text-rose-100">
          <p>Narration generation failed{state.error ? `: ${state.error}` : "."}</p>
          <button
            type="button"
            onClick={() => void startGeneration()}
            className="mt-3 rounded-lg border border-rose-300/60 px-3 py-2 text-xs text-rose-200"
          >
            Try again
          </button>
        </div>
      )}

      {state.status === "ready" && lines.length > 0 && (
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
