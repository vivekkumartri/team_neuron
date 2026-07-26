"use client";

import { useEffect, useRef, useState } from "react";

import { apiBase } from "../../lib/api-client";

/**
 * Plays back the narrator-voice reading of a published chapter via
 * `GET /api/v1/chapters/:id/narration` (`api/routes/narration.py`). Fetches
 * the audio as a blob (rather than pointing `<audio>` straight at the URL)
 * so the same `credentials: "include"` identity contract `api-client.ts`
 * documents still applies to this request.
 */
export function ChapterNarrationPlayer({ chapterId }: { chapterId: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "playing" | "error">("idle");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const loadAndPlay = async () => {
    if (audioUrl) {
      audioRef.current?.play();
      setStatus("playing");
      return;
    }
    setStatus("loading");
    try {
      const response = await fetch(`${apiBase()}/chapters/${chapterId}/narration`, {
        credentials: "include",
      });
      if (!response.ok) {
        setStatus("error");
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      setStatus("ready");
      requestAnimationFrame(() => {
        audioRef.current?.play();
        setStatus("playing");
      });
    } catch {
      setStatus("error");
    }
  };

  const pause = () => {
    audioRef.current?.pause();
    setStatus("ready");
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-stone-700 bg-[#11101a] p-3">
      <button
        type="button"
        onClick={status === "playing" ? pause : loadAndPlay}
        disabled={status === "loading"}
        className="rounded-lg bg-teal-300 px-3 py-1.5 text-sm font-medium text-stone-950 disabled:opacity-40"
      >
        {status === "loading" ? "Loading…" : status === "playing" ? "Pause narration" : "Play narration"}
      </button>
      {status === "error" && (
        <p role="alert" className="text-xs text-rose-300">
          Narration is unavailable for this chapter right now.
        </p>
      )}
      {audioUrl && (
        <audio
          ref={audioRef}
          src={audioUrl}
          onEnded={() => setStatus("ready")}
          className="hidden"
        />
      )}
    </div>
  );
}
