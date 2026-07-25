"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";

interface BusinessReport {
  id: string;
  candidate_id: string;
  chapter_id: string | null;
  disclosed_weighting: Record<string, unknown>;
  redacted_summary: string;
  created_at: string;
}

/**
 * Read-only aggregate view against `GET /branches/:id/business-reports`
 * (Task 4H.4). Each row is one `report_job.py` run's `business_reports`
 * record — the redacted summary and disclosed weighting are exactly what
 * the worker wrote, nothing recomputed client-side. There is no per-report
 * detail route yet (`TraceDrawer` covers per-run agent traces, not business
 * reports), so this view is list-only by design.
 */
export function BusinessReportsView({ branchId }: { branchId: string }) {
  const [reports, setReports] = useState<BusinessReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<BusinessReport[]>(`/branches/${branchId}/business-reports`)
      .then((data) => {
        if (!cancelled) setReports(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load business reports.");
      });
    return () => {
      cancelled = true;
    };
  }, [branchId]);

  if (error) {
    return (
      <p role="alert" className="text-sm text-rose-300">
        {error}
      </p>
    );
  }
  if (!reports) {
    return (
      <p role="status" className="text-stone-400">
        Loading business reports…
      </p>
    );
  }
  if (reports.length === 0) {
    return (
      <p className="text-sm text-stone-400">
        No business reports yet for this branch — they're generated after a
        chapter publishes.
      </p>
    );
  }

  return (
    <section aria-label="Business reports">
      <h2 className="text-lg font-semibold">Business reports</h2>
      <ul className="mt-3 space-y-3">
        {reports.map((report) => (
          <li key={report.id} className="rounded-lg border border-stone-700 p-3 text-sm">
            <p className="text-stone-400">
              {new Date(report.created_at).toLocaleString()}
              {report.chapter_id ? ` · chapter ${report.chapter_id}` : ""}
            </p>
            <p className="mt-2 text-stone-200">{report.redacted_summary}</p>
            {Object.keys(report.disclosed_weighting).length > 0 && (
              <pre className="mt-2 overflow-x-auto rounded bg-stone-900 p-2 text-xs text-stone-400">
                {JSON.stringify(report.disclosed_weighting, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
