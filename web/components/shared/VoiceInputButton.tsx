"use client";

import { useEffect, useRef } from "react";

import { useVoiceTranscription } from "../../lib/voice-stream";

const WAVE_BARS = [0.5, 0.85, 1.2, 0.9, 0.65, 1.05, 0.75];

/**
 * Drop-in mic control for any free-text field. Shows a recording indicator,
 * live partial transcript while speaking, and calls `onTranscript` once with
 * the final, content-policy-checked text (see `api/routes/voice.py` -
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
 * at story-creation time - the same localStorage-for-cross-flow-state
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
  const { state, partialText, finalText, rejection, errorMessage, audioLevel, start, stop } =
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
  const listening = state === "recording";
  const buttonLabel =
    state === "connecting" ? "Connecting mic..." : recording ? "Stop recording" : label;

  return (
    <div className="flex min-w-[18rem] flex-1 flex-col gap-2">
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
        className={`group relative inline-flex min-h-14 w-full items-center gap-3 overflow-hidden rounded-2xl border px-4 py-3 text-left transition-all duration-200 ${
          recording
            ? "border-teal-300/70 bg-[linear-gradient(135deg,rgba(20,184,166,0.22),rgba(17,16,26,0.96))] text-teal-50 shadow-[0_0_0_1px_rgba(45,212,191,0.08),0_14px_34px_rgba(13,148,136,0.18)]"
            : "border-stone-700/90 bg-[linear-gradient(135deg,rgba(17,16,26,1),rgba(27,36,46,0.92))] text-stone-100 hover:border-teal-300/40 hover:text-teal-50"
        }`}
      >
        <span
          aria-hidden
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm transition-colors ${
            recording
              ? "border-teal-200/50 bg-teal-300/12 text-teal-100"
              : "border-stone-600 bg-stone-900/70 text-teal-300"
          }`}
        >
          {recording ? "●" : "🎙"}
        </span>
        <span className="flex min-w-0 flex-1 items-center gap-3">
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold tracking-[0.01em]">{buttonLabel}</span>
            <span className={`block text-xs ${recording ? "text-teal-100/80" : "text-stone-400"}`}>
              {recording ? "Live transcript ready as you speak" : "Tap to speak instead of typing"}
            </span>
          </span>
          <span
            aria-hidden
            className={`flex h-8 items-end gap-1 rounded-full px-3 transition-all duration-200 ${
              recording ? "bg-black/20 opacity-100" : "bg-transparent opacity-80 group-hover:opacity-100"
            }`}
          >
            {WAVE_BARS.map((multiplier, index) => {
              const height = recording
                ? 10 + Math.round((14 + audioLevel * 24) * multiplier)
                : 8 + (index % 3) * 3;
              return (
                <span
                  key={index}
                  className={`w-1 rounded-full transition-[height,background-color,opacity] duration-150 ${
                    listening ? "bg-teal-200" : recording ? "bg-teal-100/80" : "bg-stone-500/70"
                  }`}
                  style={{
                    height: `${height}px`,
                    opacity: listening ? Math.max(0.45, Math.min(1, 0.45 + audioLevel * 0.85)) : 1,
                  }}
                />
              );
            })}
          </span>
        </span>
      </button>
      {recording && partialText && (
        <p
          role="status"
          className="rounded-2xl border border-teal-300/20 bg-teal-300/6 px-4 py-3 text-sm text-stone-200"
        >
          {partialText}
        </p>
      )}
      {errorMessage && (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/25 bg-rose-950/20 px-3 py-2 text-sm text-rose-200"
        >
          {errorMessage}
        </p>
      )}
    </div>
  );
}
