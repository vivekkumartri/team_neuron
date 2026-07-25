"use client";

import { useState } from "react";

import { apiFetch } from "../../../lib/api-client";

/**
 * Explicit, per-category consent — nothing is inferred or pre-checked.
 * Saving calls the real `PATCH /me/preferences` endpoint once per accepted
 * category; "Lock in" then freezes the result via
 * `POST /me/personalization-snapshots` so generation reads an immutable
 * snapshot rather than live, still-editable preferences.
 */
const CATEGORIES: { key: string; label: string; description: string }[] = [
  { key: "pacing", label: "Pacing", description: "Faster scene transitions, fewer lingering beats." },
  { key: "tone", label: "Tone", description: "Lean toward hopeful outcomes over bleak ones." },
  { key: "content_boundary", label: "Content boundaries", description: "Avoid graphic violence." },
];

export function PersonalizationConsent({ onLocked }: { onLocked: () => void }) {
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = (key: string) => {
    setAccepted((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const lockIn = async () => {
    setSaving(true);
    setError(null);
    try {
      for (const key of accepted) {
        await apiFetch("/me/preferences", {
          method: "PATCH",
          body: { preference_key: key, preference_value: true, source: "EXPLICIT" },
        });
      }
      await apiFetch("/me/personalization-snapshots", { method: "POST" });
      onLocked();
    } catch {
      setError("Couldn't save your preferences. Nothing was locked in — try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-300">
        These are optional and only apply if you say yes. Nothing here is inferred for you.
      </p>
      <ul className="space-y-2">
        {CATEGORIES.map((category) => (
          <li key={category.key}>
            <label className="flex items-start gap-3 rounded-lg border border-stone-700 p-3">
              <input
                type="checkbox"
                checked={accepted.has(category.key)}
                onChange={() => toggle(category.key)}
                className="mt-1"
              />
              <span>
                <span className="block font-medium">{category.label}</span>
                <span className="block text-sm text-stone-300">{category.description}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      <button
        type="button"
        onClick={lockIn}
        disabled={saving}
        className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:opacity-40"
      >
        {saving ? "Locking in…" : "Lock in preferences"}
      </button>
    </div>
  );
}
