"use client";

import { useEffect, useRef, useState } from "react";

import { apiBase } from "./api-client";
import { demoActivityEvents, isDemoJobId } from "./demo-runtime";

export interface GenerationActivityEvent {
  sequence: number;
  summary: string;
  agent: string;
  recipient_agent: string | null;
  status: string;
  entity_id: string | null;
}

export type ConnectionState = "connecting" | "open" | "reconnecting" | "closed";

/**
 * Subscribes to `GET /api/v1/generation-jobs/:jobId/events`.
 *
 * The browser's native `EventSource` already resends the last received
 * `id` as `Last-Event-ID` on reconnect, so the server-side dedup in
 * `stream_job_events` (see `src/story_engine/api/sse.py`) is enough on its
 * own — this hook only needs to track connection state and append events,
 * not manage the reconnect handshake itself.
 */
export function useGenerationStream(jobId: string | null): {
  events: GenerationActivityEvent[];
  connectionState: ConnectionState;
  complete: boolean;
} {
  const [events, setEvents] = useState<GenerationActivityEvent[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [complete, setComplete] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setEvents([]);
    setComplete(false);
    if (!jobId) return;

    // Demo mode: the "job" is fake (see `demo-runtime.ts`) — there is no
    // real backend process to open an SSE connection to. Show the same
    // brief activity feed shape the real stream would, then complete, all
    // client-side and near-instantly, so `WorkspaceView` (reused unchanged)
    // still visually transitions through "generating" the way it normally
    // does instead of just teleporting to the chapter.
    if (isDemoJobId(jobId)) {
      setConnectionState("connecting");
      const timer = window.setTimeout(() => {
        setEvents(demoActivityEvents());
        setConnectionState("open");
        window.setTimeout(() => {
          setComplete(true);
          setConnectionState("closed");
        }, 400);
      }, 350);
      return () => window.clearTimeout(timer);
    }

    setConnectionState("connecting");
    const source = new EventSource(`${apiBase()}/generation-jobs/${jobId}/events`, {
      withCredentials: true,
    });
    sourceRef.current = source;

    source.onopen = () => setConnectionState("open");
    source.onerror = () => setConnectionState((current) => (current === "open" ? "reconnecting" : current));

    source.addEventListener("generation-progress", (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as GenerationActivityEvent;
      setEvents((current) => [...current, event]);
    });
    source.addEventListener("heartbeat", () => setConnectionState("open"));
    source.addEventListener("generation-complete", () => {
      setComplete(true);
      setConnectionState("closed");
      source.close();
    });

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [jobId]);

  return { events, connectionState, complete };
}
