"use client";

import { useEffect, useRef } from "react";

import { useVoiceTranscription } from "../../lib/voice-stream";

/**
 * Drop-in mic control for any free-text field. Shows a recording indicator,
 * live partial transcript while speaking, and calls `onTranscript` once with
 * the final, content-policy-checked text (see `api/routes/voice.py` —
 * a `rejected` transcript never reaches `onTranscript`, only `onRejected`).
 *
 * This button never submits anything on its own; the caller decides what to
 * do with the returned text (usually append/replace into its own textarea
 * state), matching every other form on this frontend's "never mutate on
 * user input alone" convention.
 */
/**
 * `language` is an optional explicit override (`en`/`hi`/`te`) forwarded as
 * a hint to Whisper for this recording. When omitted, this falls back to
 * whatever `story-engine-story-language` was last written by `CastLock.tsx`
 * at story-creation time — the same localStorage-for-cross-flow-state
 * pattern `story-engine-active-branch`/`story-engine-active-job` already
 * use, since most callers of this button (trait edits, canon-event
 * rationale, revision patches) don't have the current story object in
 * scope to pass one explicitly.
 */
export function VoiceInputButton({
  onTranscript,
  onRejected,
  label = "Voice input",
  language,
}: {
  onTranscript: (text: string) => void;
  onRejected?: (message: string, safeAlternative: string | null) => void;
  label?: string;
  language?: string | null;
}) {
  const effectiveLanguage =
    language ??
    (typeof window !== "undefined"
      ? window.localStorage.getItem("story-engine-story-language")
      : null);
  const { state, partialText, finalText, rejection, errorMessage, start, stop } =
    useVoiceTranscription(undefined, effectiveLanguage);
  const lastFinalRef = useRef<string | null>(null);

  useEffect(() => {
    if (finalText !== null && finalText !== lastFinalRef.current) {
      lastFinalRef.current = finalText;
      if (finalText.trim()) {
        onTranscript(finalText.trim());
      }
    }
  }, [finalText, onTranscript]);

  useEffect(() => {
    if (rejection) {
      onRejected?.(rejection.message, rejection.safeAlternative);
    }
  }, [rejection, onRejected]);

  const recording = state === "recording" || state === "connecting" || state === "stopping";

  return (
    <div className="inline-flex flex-col gap-1">
      <button
        type="button"
        aria-pressed={recording}
        onClick={() => {
          if (recording) {
            stop();
          } else {
            void start();
          }
        }}
        className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${
          recording
            ? "border-rose-400 bg-rose-950/30 text-rose-200"
            : "border-stone-700 bg-[#11101a] text-stone-200"
        }`}
      >
        <span aria-hidden>{recording ? "●" : "🎙"}</span>
        {recording ? "Stop" : label}
      </button>
      {recording && partialText && (
        <p role="status" className="max-w-xs text-xs text-stone-400">
          {partialText}
        </p>
      )}
      {errorMessage && (
        <p role="alert" className="max-w-xs text-xs text-rose-300">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
