"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";
import type { StoryLanguageCode } from "./LanguagePicker";

export interface CastCharacter {
  name: string;
  role: string;
  voice: string;
  traits: string;
  visual: string;
  is_protagonist: boolean;
}

interface CastProposalResponse {
  characters: Omit<CastCharacter, "is_protagonist">[];
}

const blankCharacter = (isProtagonist = false): CastCharacter => ({
  name: "",
  role: isProtagonist ? "Protagonist" : "Supporting character",
  voice: "",
  traits: "",
  visual: "",
  is_protagonist: isProtagonist,
});

export function CastEditor({
  seed,
  language,
  onContinue,
}: {
  seed: string;
  language: StoryLanguageCode;
  onContinue: (cast: CastCharacter[]) => void;
}) {
  const [cast, setCast] = useState<CastCharacter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const proposal = await apiFetch<CastProposalResponse>("/stories/cast-proposal", {
        method: "POST",
        body: { seed, language },
      });
      setCast(
        proposal.characters.map((character, index) => ({
          ...character,
          is_protagonist: index === 0,
        })),
      );
    } catch {
      setError("We couldn't generate a cast just now. You can try again or build it yourself.");
      setCast((current) => (current.length ? current : [blankCharacter(true)]));
    } finally {
      setLoading(false);
    }
  }, [language, seed]);

  useEffect(() => {
    void generate();
  }, [generate]);

  const update = (index: number, field: keyof CastCharacter, value: string | boolean) => {
    setCast((current) =>
      current.map((character, characterIndex) =>
        characterIndex === index
          ? {
              ...character,
              [field]: value,
              ...(field === "is_protagonist" && value
                ? { is_protagonist: true }
                : {}),
            }
          : field === "is_protagonist" && value
            ? { ...character, is_protagonist: false }
            : character,
      ),
    );
  };

  const validCast = cast.length > 0 && cast.every((character) => character.name.trim());

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-stone-300">
          Your starting cast is proposed from your story idea. Every detail is visible and editable
          before Chapter 1 begins.
        </p>
        <button
          type="button"
          onClick={() => void generate()}
          disabled={loading}
          className="mt-3 rounded-lg border border-teal-300/60 px-3 py-2 text-sm text-teal-200 disabled:opacity-40"
        >
          {loading ? "Generating characters…" : "Regenerate cast from this idea"}
        </button>
      </div>

      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        {cast.map((character, index) => (
          <fieldset key={`${index}-${character.name}`} className="rounded-xl border border-stone-700 bg-[#11101a] p-4">
            <legend className="px-1 text-xs font-medium uppercase tracking-wide text-teal-300">
              {character.is_protagonist ? "Protagonist" : "Starting character"}
            </legend>
            {(["name", "role", "voice", "traits", "visual"] as const).map((field) => (
              <label key={field} className="mt-3 block text-xs capitalize text-stone-400">
                {field === "voice" ? "Voice / dialogue style" : field === "visual" ? "Visual attributes" : field}
                <input
                  value={character[field]}
                  onChange={(event) => update(index, field, event.target.value)}
                  className="mt-1 w-full rounded-md border border-stone-700 bg-[#191724] p-2 text-sm text-stone-100"
                />
              </label>
            ))}
            <label className="mt-3 flex items-center gap-2 text-sm text-stone-300">
              <input
                type="radio"
                name="protagonist"
                checked={character.is_protagonist}
                onChange={() => update(index, "is_protagonist", true)}
              />
              Make protagonist
            </label>
            {cast.length > 1 && (
              <button
                type="button"
                onClick={() => setCast((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                className="mt-3 text-sm text-rose-300 underline underline-offset-4"
              >
                Remove character
              </button>
            )}
          </fieldset>
        ))}
      </div>

      <button
        type="button"
        disabled={cast.length >= 6}
        onClick={() => setCast((current) => [...current, blankCharacter()])}
        className="rounded-lg border border-stone-600 px-3 py-2 text-sm disabled:opacity-40"
      >
        Add another starting character
      </button>

      <button
        type="button"
        disabled={!validCast || loading}
        onClick={() => onContinue(cast.map((character, index) => ({ ...character, is_protagonist: character.is_protagonist || index === 0 })))}
        className="ml-3 rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:opacity-40"
      >
        Continue to cast lock
      </button>
    </div>
  );
}
