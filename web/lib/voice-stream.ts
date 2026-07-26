"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiWsBase } from "./api-client";

/**
 * Client for `WS /api/v1/voice/transcribe`.
 *
 * Matches `generation-stream.ts`'s style (a small hook exposing connection
 * state plus accumulated data), but for an outbound audio WebSocket instead
 * of an inbound SSE stream: identity rides on the same
 * `x-forwarded-user`/`x-forwarded-email` headers the browser already sends
 * on every request (see `api-client.ts`), so no token has to be attached
 * here — the browser's WebSocket handshake carries the same cookies/headers
 * as any other same-origin request through the Databricks Apps proxy.
 *
 * Records the whole utterance and transcribes it once, when recording stops
 * — not a true incremental stream. An earlier version called
 * `recorder.start(chunkIntervalMs)` and sent each `ondataavailable` chunk to
 * the server as its own audio file; for `audio/webm`, only the *first* chunk
 * from a timesliced recording contains the container header, so every chunk
 * after that was an undecodable fragment. The server transcribed the first
 * chunk fine, errored on every chunk after, and `final` ended up built from
 * whatever partial text happened to survive — which is why transcription
 * silently stopped working and nothing landed in the target field. Calling
 * `recorder.start()` with no timeslice makes `ondataavailable` fire exactly
 * once, on `stop()`, with one complete, valid recording.
 */

export type VoiceStreamState = "idle" | "connecting" | "recording" | "stopping" | "error";

export interface VoiceTranscriptState {
  state: VoiceStreamState;
  partialText: string;
  finalText: string | null;
  rejection: { message: string; safeAlternative: string | null } | null;
  errorMessage: string | null;
  start: () => Promise<void>;
  stop: () => void;
}

const DEFAULT_CHUNK_INTERVAL_MS = 2500;

/**
 * `language` is the story's `en`/`hi`/`te` preference (task.md Phase 6
 * multilingual entry), forwarded to `voice.py` as a `?language=` query
 * param so it can pass it through to Whisper as an accuracy hint. Omitted
 * entirely when not provided, so pre-existing callers with no notion of a
 * story language keep working unchanged (server-side default is "no hint").
 */
function wsUrl(language?: string | null): string {
  const query = language ? `?language=${encodeURIComponent(language)}` : "";
  return `${apiWsBase()}/voice/transcribe${query}`;
}

export function useVoiceTranscription(
  chunkIntervalMs = DEFAULT_CHUNK_INTERVAL_MS,
  language?: string | null,
): VoiceTranscriptState {
  const [state, setState] = useState<VoiceStreamState>("idle");
  const [partialText, setPartialText] = useState("");
  const [finalText, setFinalText] = useState<string | null>(null);
  const [rejection, setRejection] = useState<{ message: string; safeAlternative: string | null } | null>(
    null,
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const cleanup = useCallback(() => {
    recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    recorderRef.current = null;
    streamRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const start = useCallback(async () => {
    setErrorMessage(null);
    setRejection(null);
    setFinalText(null);
    setPartialText("");

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setState("error");
      setErrorMessage("Voice input isn't supported in this browser.");
      return;
    }

    setState("connecting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const socket = new WebSocket(wsUrl(language));
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;

      socket.onopen = () => {
        const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        recorderRef.current = recorder;
        recorder.ondataavailable = (event) => {
          if (event.data.size === 0) return;
          // Fires once, on stop() (no timeslice passed to start()), with one
          // complete valid recording — safe to send and decode as a whole file.
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(event.data);
          }
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ action: "stop" }));
          }
        };
        recorder.start();
        setState("recording");
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data as string) as {
            type: string;
            text?: string;
            message?: string;
            safe_alternative?: string | null;
          };
          if (payload.type === "partial" && payload.text) {
            setPartialText((current) => `${current} ${payload.text}`.trim());
          } else if (payload.type === "final") {
            setFinalText(payload.text ?? "");
            setState("idle");
          } else if (payload.type === "rejected") {
            setRejection({
              message: payload.message ?? "That input couldn't be used.",
              safeAlternative: payload.safe_alternative ?? null,
            });
            setState("idle");
          } else if (payload.type === "error") {
            setErrorMessage(payload.message ?? "Transcription error.");
          }
        } catch {
          // Ignore malformed frames rather than surfacing a raw parse error.
        }
      };

      socket.onerror = () => {
        setState("error");
        setErrorMessage("Voice connection failed.");
      };
      socket.onclose = () => {
        recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
      };
    } catch {
      setState("error");
      setErrorMessage("Microphone access was denied or unavailable.");
    }
  }, [chunkIntervalMs, language]);

  const stop = useCallback(() => {
    setState("stopping");
    // `ondataavailable` (fired by this `stop()` call, since recording started
    // with no timeslice) sends the audio and the "stop" control message
    // together, in that order — sending "stop" here too would race it and
    // could reach the server before the audio does.
    recorderRef.current?.stop();
  }, []);

  return { state, partialText, finalText, rejection, errorMessage, start, stop };
}
