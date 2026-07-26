"use client";

import { useState } from "react";

import { VoiceInputButton } from "../../shared/VoiceInputButton";

/**
 * Seed clarification with NO hard character minimum - the retired prototype
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
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        if (canContinue) onContinue(trimmed);
      }}
    >
      <div className="space-y-2">
        <label htmlFor="seed-input" className="block text-sm font-medium text-stone-100">
          What's the story about?
        </label>
        <p className="text-sm leading-6 text-stone-400">
          Sketch the premise in a sentence or two, or speak it out loud and let the mic turn it into a seed.
        </p>
      </div>
      <textarea
        id="seed-input"
        value={seed}
        onChange={(event) => {
          setSeed(event.target.value);
          setAcknowledgedShortSeed(false);
        }}
        rows={5}
        className="w-full rounded-2xl border border-stone-700/90 bg-[linear-gradient(180deg,rgba(14,14,24,0.98),rgba(17,16,26,0.92))] px-4 py-4 text-base leading-7 text-stone-100 shadow-inner shadow-black/20 outline-none transition-colors placeholder:text-stone-500 focus:border-teal-300/60"
        placeholder="A lighthouse keeper who can hear the ships that never made it home."
      />
      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <VoiceInputButton
          label="Speak your seed"
          onTranscript={(text) => {
            setSeed((current) => (current.trim() ? `${current.trim()} ${text}` : text));
            setAcknowledgedShortSeed(false);
          }}
        />
        <button
          type="submit"
          disabled={!canContinue}
          className="inline-flex min-h-14 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#f8d56b,#f3ba2f)] px-7 py-3 text-base font-semibold text-stone-950 shadow-[0_16px_30px_rgba(243,186,47,0.22)] transition-transform duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0 md:min-w-[11rem]"
        >
          Continue
        </button>
      </div>
      {needsClarification && (
        <div
          role="status"
          className="rounded-2xl border border-amber-300/50 bg-[linear-gradient(135deg,rgba(120,53,15,0.22),rgba(69,26,3,0.12))] p-4 text-sm text-amber-100"
        >
          <p>
            That's a short seed - it's easy to lose the thread once branches start. You can add more detail, or
            continue as-is.
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
    </form>
  );
}
