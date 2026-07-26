"use client";

import { useCallback, useEffect, useState } from "react";

import { apiBase, apiFetch, ApiError } from "../../lib/api-client";

interface CharacterVoiceEntry {
  character_name: string;
  content_type: string;
}

interface CharacterVoiceListResponse {
  voices: CharacterVoiceEntry[];
}

/**
 * Manages per-character reference-voice uploads for the multi-voice
 * character audio feature (`api/routes/character_voice.py`). An author
 * uploads their own (or otherwise rights-cleared) short clip for a named
 * character plus its exact transcript; that clip is then used as the
 * IndicF5 zero-shot reference whenever that character speaks. Re-uploading
 * for the same name at any time replaces the previous clip (`PUT` upsert),
 * so there is one form for both "add" and "update".
 *
 * `characterNames`, when given, locks this to only the story's real
 * (already-locked) cast: the free-text name field becomes a `<select>` over
 * that list, so this page can't be used to attach a voice to a name that
 * doesn't actually exist in the story. Omitting it (no active story
 * selected) falls back to free text — a caller decides whether that's
 * acceptable for its context.
 */
export function CharacterVoiceUploader({
  characterNames,
}: {
  characterNames?: string[];
}) {
  const [voices, setVoices] = useState<CharacterVoiceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [characterName, setCharacterName] = useState("");
  const [refText, setRefText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch<CharacterVoiceListResponse>("/voice/character-voices");
      setVoices(response.voices);
    } catch {
      setError("Couldn't load uploaded character voices.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upload = async () => {
    setFormError(null);
    const name = characterName.trim();
    if (!name) {
      setFormError("Enter the character's name exactly as it appears in the script.");
      return;
    }
    if (!refText.trim()) {
      setFormError("Enter the exact transcript of what's spoken in the uploaded clip.");
      return;
    }
    if (!file) {
      setFormError("Choose an audio file to upload.");
      return;
    }

    setSaving(true);
    try {
      const body = new FormData();
      body.append("ref_text", refText.trim());
      body.append("audio", file);
      const response = await fetch(
        `${apiBase()}/voice/character-voices/${encodeURIComponent(name)}`,
        { method: "PUT", credentials: "include", body },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const detail =
          payload && typeof payload === "object" && "detail" in payload
            ? String((payload as { detail: unknown }).detail)
            : `Upload failed with ${response.status}`;
        throw new ApiError(response.status, detail);
      }
      setCharacterName("");
      setRefText("");
      setFile(null);
      await refresh();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (name: string) => {
    try {
      await apiFetch(`/voice/character-voices/${encodeURIComponent(name)}`, { method: "DELETE" });
      await refresh();
    } catch {
      setError(`Couldn't remove the voice for "${name}".`);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Character voices</h2>
        <p className="mt-1 text-sm text-stone-400">
          Upload a short reference clip (a few seconds is enough) for any character. It replaces
          the auto-picked voice for that character whenever you generate audio, and you can
          re-upload at any time to change it.
        </p>
      </div>

      <fieldset className="space-y-3 rounded-xl border border-stone-700 bg-[#11101a] p-4">
        <legend className="px-1 text-xs font-medium uppercase tracking-wide text-teal-300">
          Add or replace a character voice
        </legend>
        <label className="block text-xs text-stone-400">
          Character of story
          {characterNames ? (
            <select
              value={characterName}
              onChange={(event) => setCharacterName(event.target.value)}
              className="mt-1 w-full rounded-md border border-stone-700 bg-[#191724] p-2 text-sm text-stone-100"
            >
              <option value="">Choose a character…</option>
              {characterNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={characterName}
              onChange={(event) => setCharacterName(event.target.value)}
              className="mt-1 w-full rounded-md border border-stone-700 bg-[#191724] p-2 text-sm text-stone-100"
              placeholder="e.g. రవి"
            />
          )}
        </label>
        <label className="block text-xs text-stone-400">
          Exact transcript of the uploaded clip
          <textarea
            value={refText}
            onChange={(event) => setRefText(event.target.value)}
            rows={2}
            className="mt-1 w-full rounded-md border border-stone-700 bg-[#191724] p-2 text-sm text-stone-100"
            placeholder="Type precisely what is spoken in the audio file below"
          />
        </label>
        <label className="block text-xs text-stone-400">
          Audio file
          <input
            type="file"
            accept="audio/*"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm text-stone-300"
          />
        </label>
        {formError && (
          <p role="alert" className="text-sm text-rose-300">
            {formError}
          </p>
        )}
        <button
          type="button"
          onClick={() => void upload()}
          disabled={saving}
          className="rounded-lg bg-amber-300 px-4 py-2 text-sm font-medium text-stone-950 disabled:opacity-40"
        >
          {saving ? "Uploading…" : "Save character voice"}
        </button>
      </fieldset>

      {loading && <p className="text-sm text-stone-400">Loading uploaded voices…</p>}
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      {!loading && voices.length === 0 && !error && (
        <p className="text-sm text-stone-400">No character voices uploaded yet.</p>
      )}
      {voices.length > 0 && (
        <ul className="space-y-2">
          {voices.map((voice) => (
            <li
              key={voice.character_name}
              className="flex items-center justify-between rounded-lg border border-stone-700 bg-[#11101a] p-3 text-sm"
            >
              <span className="text-stone-200">{voice.character_name}</span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-stone-500">{voice.content_type}</span>
                <button
                  type="button"
                  onClick={() => void remove(voice.character_name)}
                  className="text-rose-300 underline underline-offset-4"
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
