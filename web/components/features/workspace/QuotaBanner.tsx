"use client";

/** Renders the quota state returned by `GET /api/v1/me/quota`. */
export interface QuotaBannerState {
  category: string;
  used: number;
  limit: number;
  remaining: number;
  exceeded: boolean;
  approaching: boolean;
}

const CATEGORY_LABELS: Record<string, string> = {
  CHAPTERS_PER_MONTH: "Chapters this month",
  CONCURRENT_BRANCHES: "Active branches",
  CONCURRENT_GENERATION_JOBS: "Generation jobs running",
};

export function QuotaBanner({ state }: { state: QuotaBannerState | null }) {
  if (!state || (!state.exceeded && !state.approaching)) {
    return null;
  }

  const label = CATEGORY_LABELS[state.category] ?? state.category;

  if (state.exceeded) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-rose-400 bg-rose-950/20 p-3 text-sm text-rose-100"
      >
        <p className="font-medium">{label}: quota reached ({state.used}/{state.limit}).</p>
        <p className="mt-1 text-rose-200">
          Existing content stays available — this only pauses new submissions in this category
          until it resets or your limit increases.
        </p>
      </div>
    );
  }

  return (
    <div
      role="status"
      className="rounded-lg border border-amber-300/60 bg-amber-950/20 p-3 text-sm text-amber-100"
    >
      {label}: {state.used}/{state.limit} used, {state.remaining} remaining.
    </div>
  );
}
