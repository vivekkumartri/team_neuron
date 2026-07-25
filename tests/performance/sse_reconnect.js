import { check } from "k6";
import http from "k6/http";

/**
 * Task 5J.2: reconnect-storm resilience for the SSE generation-events
 * endpoint (`api/routes/events.py`). k6's core HTTP module doesn't keep a
 * streaming connection open the way a browser `EventSource` does, so this
 * script approximates a reconnect storm by issuing many rapid short-lived
 * requests with an incrementing `Last-Event-ID`, which is enough to exercise
 * the server's per-poll RLS re-check and dedup logic (`stream_job_events`)
 * under concurrent load even without holding the stream open k6-side.
 *
 * Unrun in this sandbox, same reason as api_load.js — no live deployment.
 */
export const options = {
  vus: 50,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<1000"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const JOB_ID = __ENV.JOB_ID || "00000000-0000-0000-0000-000000000000";

export default function () {
  const lastEventId = String(Math.floor(Math.random() * 10));
  const res = http.get(`${BASE_URL}/api/v1/generation-jobs/${JOB_ID}/events`, {
    headers: {
      "x-forwarded-user": "loadtest-user",
      "x-forwarded-email": "loadtest@example.com",
      "Last-Event-ID": lastEventId,
    },
    timeout: "5s",
  });
  check(res, {
    "reconnect never returns 5xx": (r) => r.status < 500,
  });
}
