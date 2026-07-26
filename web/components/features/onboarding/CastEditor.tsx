"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";
import { CharacterVoiceUploadField } from "../../shared/CharacterVoiceUploadField";
import type { StoryLanguageCode } from "./LanguagePicker";

export interface CastCharacter {
  name: string;
  role: string;
  voice: string;
  traits: string;
  visual: string;
  background_story: string;
  photo_data_url?: string;
}

interface CastProposalResponse {
  characters: CastCharacter[];
  source: "llm" | "seed_fallback";
}

const blankCharacter = (): CastCharacter => ({
  name: "",
  role: "",
  voice: "",
  traits: "",
  visual: "",
  background_story: "",
});

/**
 * No character is a "protagonist" here — every cast member is equal, both
 * in this editor and downstream (`cast_members.role` is always 'CHARACTER',
 * `POST /stories`'s `CastMemberInput` no longer has an `is_protagonist`
 * field at all). The first character listed is still used as chapter 1's
 * initial focal character, purely as an ordering convenience to give
 * generation somewhere to start — it carries no special status and can be
 * reordered or removed like any other.
 */
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
  const [usingFallback, setUsingFallback] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);

  const generate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const proposal = await apiFetch<CastProposalResponse>("/stories/cast-proposal", {
        method: "POST",
        body: { seed, language },
      });
      setCast(
        proposal.characters.map((character) => ({
          ...character,
          background_story: character.background_story ?? "",
        })),
      );
      setUsingFallback(proposal.source === "seed_fallback");
    } catch {
      setError("We couldn't generate a cast just now. You can try again or build it yourself.");
      setCast((current) => (current.length ? current : [blankCharacter()]));
      setUsingFallback(true);
    } finally {
      setLoading(false);
    }
  }, [language, seed]);

  useEffect(() => {
    void generate();
  }, [generate]);

  const update = (index: number, field: keyof CastCharacter, value: string) => {
    setCast((current) =>
      current.map((character, characterIndex) =>
        characterIndex === index ? { ...character, [field]: value } : character,
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
      {usingFallback && !error && (
        <p role="status" className="rounded-lg border border-amber-300/50 bg-amber-950/20 p-3 text-sm text-amber-100">
          We used the names and setting in your idea to draft this editable cast. You can refine
          every field or regenerate it when the model is available.
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {cast.map((character, index) => (
          <fieldset key={`${index}-${character.name}`} className="rounded-xl border border-stone-700 bg-[#11101a] p-4">
            <legend className="px-1 text-xs font-medium uppercase tracking-wide text-teal-300">
              Character
            </legend>
            {(["name", "role", "voice", "traits", "visual", "background_story"] as const).map((field) => (
              <label key={field} className="mt-3 block text-xs capitalize text-stone-400">
                {field === "voice"
                  ? "Voice / dialogue style"
                  : field === "visual"
                    ? "Visual attributes"
                    : field === "background_story"
                      ? "Background story"
                      : field}
                <input
                  value={character[field]}
                  onChange={(event) => update(index, field, event.target.value)}
                  className="mt-1 w-full rounded-md border border-stone-700 bg-[#191724] p-2 text-sm text-stone-100"
                />
              </label>
            ))}
            <label className="mt-3 block text-xs text-stone-400">
              Optional character photo (used as the consistency reference)
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  if (file.size > 8 * 1024 * 1024) {
                    setPhotoError("Choose an image smaller than 8 MB.");
                    return;
                  }
                  setPhotoError(null);
                  const reader = new FileReader();
                  reader.onload = () => {
                    if (typeof reader.result === "string") {
                      update(index, "photo_data_url", reader.result);
                    }
                  };
                  reader.readAsDataURL(file);
                }}
                className="mt-1 block w-full text-sm text-stone-300 file:mr-3 file:rounded-md file:border-0 file:bg-stone-700 file:px-3 file:py-2 file:text-stone-100"
              />
            </label>
            <CharacterVoiceUploadField characterName={character.name} />
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

      {photoError && <p role="alert" className="text-sm text-rose-300">{photoError}</p>}

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
        onClick={() => onContinue(cast)}
        className="ml-3 rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:opacity-40"
      >
        Continue to cast lock
      </button>
    </div>
  );
}
