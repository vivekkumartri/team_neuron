"use client";

import { useEffect, useState } from "react";

import { apiBase, apiFetch, ApiError } from "../../lib/api-client";

interface CharacterVoiceEntry {
  character_name: string;
  content_type: string;
}

interface CharacterVoiceListResponse {
  voices: CharacterVoiceEntry[];
}

/**
 * Compact per-character voice upload, meant to sit inside a single character
 * card (e.g. `CastEditor.tsx`) rather than the full standalone manager
 * (`CharacterVoiceUploader.tsx`, used on the `/voice` page). Same backend
 * (`PUT/DELETE /voice/character-voices/{name}`) — this is just a smaller
 * form scoped to one character's current name.
 */
export function CharacterVoiceUploadField({ characterName }: { characterName: string }) {
  const trimmedName = characterName.trim();
  const [uploaded, setUploaded] = useState<CharacterVoiceEntry | null>(null);
  const [checking, setChecking] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [refText, setRefText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!trimmedName) {
      setUploaded(null);
      return;
    }
    let cancelled = false;
    setChecking(true);
    apiFetch<CharacterVoiceListResponse>("/voice/character-voices")
      .then((response) => {
        if (cancelled) return;
        setUploaded(response.voices.find((voice) => voice.character_name === trimmedName) ?? null);
      })
      .catch(() => {
        if (!cancelled) setUploaded(null);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [trimmedName]);

  const upload = async () => {
    setError(null);
    if (!refText.trim()) {
      setError("Enter the exact transcript of the clip.");
      return;
    }
    if (!file) {
      setError("Choose an audio file.");
      return;
    }
    setSaving(true);
    try {
      const body = new FormData();
      body.append("ref_text", refText.trim());
      body.append("audio", file);
      const response = await fetch(
        `${apiBase()}/voice/character-voices/${encodeURIComponent(trimmedName)}`,
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
      const saved = await response.json();
      setUploaded(saved);
      setFile(null);
      setRefText("");
      setExpanded(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/voice/character-voices/${encodeURIComponent(trimmedName)}`, {
        method: "DELETE",
      });
      setUploaded(null);
    } catch {
      setError("Couldn't remove the uploaded voice.");
    } finally {
      setSaving(false);
    }
  };

  if (!trimmedName) {
    return (
      <p className="mt-3 text-xs text-stone-500">Add this character's name to upload a voice.</p>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-stone-700 bg-[#191724] p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-teal-300">
          Character voice
        </span>
        {checking && <span className="text-xs text-stone-500">Checking…</span>}
      </div>

      {uploaded && !expanded ? (
        <div className="mt-2 flex items-center justify-between text-xs text-stone-300">
          <span>Custom voice uploaded ({uploaded.content_type})</span>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="text-teal-300 underline underline-offset-4"
            >
              Replace
            </button>
            <button
              type="button"
              onClick={() => void remove()}
              disabled={saving}
              className="text-rose-300 underline underline-offset-4 disabled:opacity-40"
            >
              Remove
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-2 space-y-2">
          <p className="text-xs text-stone-400">
            Upload a short clip (your own, or otherwise rights-cleared) to use this character's
            real voice instead of the auto-picked one.
          </p>
          <textarea
            value={refText}
            onChange={(event) => setRefText(event.target.value)}
            rows={2}
            placeholder="Exact transcript of what's spoken in the clip"
            className="w-full rounded-md border border-stone-700 bg-[#11101a] p-2 text-xs text-stone-100"
          />
          <input
            type="file"
            accept="audio/*"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="block w-full text-xs text-stone-300"
          />
          {error && (
            <p role="alert" className="text-xs text-rose-300">
              {error}
            </p>
          )}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => void upload()}
              disabled={saving}
              className="rounded-md bg-amber-300 px-3 py-1.5 text-xs font-medium text-stone-950 disabled:opacity-40"
            >
              {saving ? "Uploading…" : "Save voice"}
            </button>
            {uploaded && (
              <button
                type="button"
                onClick={() => {
                  setExpanded(false);
                  setError(null);
                }}
                className="text-xs text-stone-400"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
