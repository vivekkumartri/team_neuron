import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Task 5J.2: concurrent-user API load against the dev/staging SLOs recorded
 * in docs/adr/201-slo-and-capacity.md. This script has never been executed
 * against a live deployment — there is no Databricks App/dev workspace in
 * this project's development sandbox — so its thresholds are the documented
 * target, not a verified result. Run with:
 *   k6 run -e BASE_URL=https://<app-host> -e AUTH_HEADER='x-forwarded-user: ...' tests/performance/api_load.js
 */
export const options = {
  scenarios: {
    concurrent_readers: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "1m", target: 20 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    // Matches docs/adr/201-slo-and-capacity.md's documented API latency SLO.
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const headers = { "x-forwarded-user": "loadtest-user", "x-forwarded-email": "loadtest@example.com" };
  const res = http.get(`${BASE_URL}/api/v1/stories`, { headers });
  check(res, {
    "status is 200 or 401 (never 5xx under load)": (r) => r.status === 200 || r.status === 401,
  });
  sleep(1);
}
