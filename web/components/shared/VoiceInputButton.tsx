"use client";

import { useEffect, useRef } from "react";

import { useVoiceTranscription } from "../../lib/voice-stream";

/**
 * Icon-only mic control meant to sit *inside* the field it feeds, anchored
 * to the bottom-right corner the way a chat app (WhatsApp, iMessage, etc.)
 * places its mic inside the message box rather than as a separate button
 * off to the side — the previous version rendered as its own labeled button
 * below the textarea, disconnected from the field it was actually for.
 * Wrap the target `<textarea>`/`<input>` in a `relative` container and drop
 * this inside it (see `SeedForm.tsx` for the pattern); it positions itself
 * with `absolute`, so it needs nothing from the caller but that wrapper.
 *
 * Shows a recording indicator, live partial transcript while speaking, and
 * calls `onTranscript` once with the final, content-policy-checked text (see
 * `api/routes/voice.py` — a `rejected` transcript never reaches
 * `onTranscript`, only `onRejected`).
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
    <>
      <button
        type="button"
        aria-pressed={recording}
        aria-label={recording ? "Stop recording" : label}
        title={recording ? "Stop recording" : label}
        onClick={() => {
          if (recording) {
            stop();
          } else {
            void start();
          }
        }}
        className={`absolute right-2 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-full border text-sm shadow ${
          recording
            ? "animate-pulse border-rose-400 bg-rose-950/60 text-rose-200"
            : "border-stone-600 bg-[#191724] text-stone-300 hover:border-teal-300 hover:text-teal-200"
        }`}
      >
        <span aria-hidden>{recording ? "●" : "🎙"}</span>
      </button>
      {(recording && partialText) || errorMessage ? (
        <p
          role={errorMessage ? "alert" : "status"}
          className={`absolute right-0 top-full mt-1 max-w-[80%] rounded-md bg-[#11101a] px-2 py-1 text-xs shadow ${
            errorMessage ? "text-rose-300" : "text-stone-400"
          }`}
        >
          {errorMessage ?? partialText}
        </p>
      ) : null}
    </>
  );
}
