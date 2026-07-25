"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";

interface EndingOption {
  id: string;
  label: string;
  summary: string;
  selected: boolean;
  resulting_chapter_id: string | null;
}

/**
 * Reads/selects existing `ending_options` rows via
 * `GET/POST /branches/:id/ending-options*` (Task 4H.4 backend gap closed).
 * Never generates ending candidates itself — those come from the business/
 * evaluator pipeline once a branch crosses the readiness threshold.
 */
export function EndingOptionsView({ branchId }: { branchId: string }) {
  const [options, setOptions] = useState<EndingOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selecting, setSelecting] = useState<string | null>(null);

  const load = () => {
    apiFetch<EndingOption[]>(`/branches/${branchId}/ending-options`)
      .then(setOptions)
      .catch(() => setError("Couldn't load ending options."));
  };

  useEffect(load, [branchId]);

  const select = async (optionId: string) => {
    setSelecting(optionId);
    setError(null);
    try {
      await apiFetch(`/branches/${branchId}/ending-options/${optionId}/select`, {
        method: "POST",
      });
      load();
    } catch {
      setError("Couldn't select that ending. Nothing changed.");
    } finally {
      setSelecting(null);
    }
  };

  if (error) {
    return (
      <p role="alert" className="text-sm text-rose-300">
        {error}
      </p>
    );
  }
  if (!options) {
    return (
      <p role="status" className="text-stone-400">
        Loading ending options…
      </p>
    );
  }
  if (options.length === 0) {
    return (
      <p className="text-stone-400">
        No ending options yet. They appear once this branch is far enough along, or after you
        request them manually.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {options.map((option) => (
        <li
          key={option.id}
          className={`rounded-lg border p-4 ${option.selected ? "border-teal-300 bg-teal-950/20" : "border-stone-700"}`}
        >
          <h3 className="font-semibold">{option.label}</h3>
          <p className="mt-1 text-sm text-stone-300">{option.summary}</p>
          <button
            type="button"
            disabled={option.selected || selecting === option.id}
            onClick={() => select(option.id)}
            className="mt-3 rounded-lg bg-amber-300 px-3 py-2 text-sm font-medium text-stone-950 disabled:opacity-40"
          >
            {option.selected ? "Selected" : selecting === option.id ? "Selecting…" : "Choose this ending"}
          </button>
        </li>
      ))}
    </ul>
  );
}
