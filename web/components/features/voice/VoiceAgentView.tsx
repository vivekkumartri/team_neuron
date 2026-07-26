"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";
import { useSelectedBranch } from "../../../lib/story-context";
import { CharacterAudioPlayer } from "../../shared/CharacterAudioPlayer";
import { CharacterVoiceUploader } from "../../shared/CharacterVoiceUploader";

interface CastMemberResponse {
  entity_id: string;
  name: string;
  role: string;
}

/**
 * `/voice` — upload per-character reference voices and generate multi-voice
 * scene audio. The character picker is locked to the active story's real
 * cast (`/branches/:id/cast-members`, the same source `WorkspaceView.tsx`
 * uses) rather than a free-text field, so this page can only attach a voice
 * to a character that actually exists in the story.
 */
export function VoiceAgentView() {
  const { branchId } = useSelectedBranch();
  const [characterNames, setCharacterNames] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!branchId) {
      setCharacterNames(null);
      return;
    }
    let cancelled = false;
    apiFetch<CastMemberResponse[]>(`/branches/${branchId}/cast-members`)
      .then((members) => {
        if (!cancelled) setCharacterNames(members.map((member) => member.name));
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this story's cast.");
      });
    return () => {
      cancelled = true;
    };
  }, [branchId]);

  if (!branchId) {
    return (
      <section className="mx-auto max-w-3xl space-y-4">
        <h1 className="text-2xl font-semibold">Voice agent</h1>
        <p className="text-sm text-stone-400">
          Select or start a story first — character voices are tied to that story's cast.
        </p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-3xl space-y-10">
      <h1 className="text-2xl font-semibold">Voice agent</h1>
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      {characterNames === null && !error && (
        <p className="text-sm text-stone-400">Loading this story's cast…</p>
      )}
      {characterNames !== null && characterNames.length === 0 && (
        <p className="text-sm text-stone-400">This story has no cast members yet.</p>
      )}
      {characterNames !== null && characterNames.length > 0 && (
        <CharacterVoiceUploader characterNames={characterNames} />
      )}
      <hr className="border-stone-800" />
      <CharacterAudioPlayer />
    </section>
  );
}
