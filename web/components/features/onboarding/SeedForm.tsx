"use client";

import { useState } from "react";

/**
 * Seed clarification with NO hard character minimum — the retired prototype
 * gated progression behind a `>= 20` character count; this MVP instead shows
 * a visible clarification prompt for short/ambiguous seeds and always lets
 * the author continue (design.md "Loophole and Integrity Guards").
 */
const CLARIFICATION_THRESHOLD = 12;

export function SeedForm({ onContinue }: { onContinue: (seed: string) => void }) {
  const [seed, setSeed] = useState("");
  const [acknowledgedShortSeed, setAcknowledgedShortSeed] = useState(false);

  const trimmed = seed.trim();
  const needsClarification = trimmed.length > 0 && trimmed.length < CLARIFICATION_THRESHOLD;
  const canContinue = trimmed.length > 0 && (!needsClarification || acknowledgedShortSeed);

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (canContinue) onContinue(trimmed);
      }}
    >
      <label htmlFor="seed-input" className="block text-sm font-medium text-stone-200">
        What's the story about?
      </label>
      <textarea
        id="seed-input"
        value={seed}
        onChange={(event) => {
          setSeed(event.target.value);
          setAcknowledgedShortSeed(false);
        }}
        rows={4}
        className="w-full rounded-lg border border-stone-700 bg-[#11101a] p-3 text-stone-100"
        placeholder="A lighthouse keeper who can hear the ships that never made it home."
      />
      {needsClarification && (
        <div role="status" className="rounded-lg border border-amber-300/60 bg-amber-950/20 p-3 text-sm text-amber-100">
          <p>
            That's a short seed — it's easy to lose the thread once branches start. You can
            add more detail, or continue as-is.
          </p>
          <label className="mt-2 flex items-center gap-2">
            <input
              type="checkbox"
              checked={acknowledgedShortSeed}
              onChange={(event) => setAcknowledgedShortSeed(event.target.checked)}
            />
            Continue with this seed
          </label>
        </div>
      )}
      <button
        type="submit"
        disabled={!canContinue}
        className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Continue
      </button>
    </form>
  );
}
