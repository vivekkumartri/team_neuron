"use client";

import { useState } from "react";

import { apiFetch, ApiError } from "../../lib/api-client";

interface CharacterAudioLine {
  scene_index: number;
  kind: "scene_heading" | "action" | "dialogue";
  speaker: string | null;
  text: string;
  voice_id: string;
  audio_base64: string;
}

interface CharacterAudioResponse {
  lines: CharacterAudioLine[];
}

function base64ToObjectUrl(base64: string): string {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
}

/**
 * Pastes a raw screenplay-style script (scene headings, action lines,
 * speaker-cued dialogue) and generates one IndicF5 clip per line via
 * `POST /voice/script-audio`. Each character's line uses whatever voice
 * was auto-cast or uploaded for them (`CharacterVoiceUploader`).
 */
export function CharacterAudioPlayer() {
  const [scriptText, setScriptText] = useState("");
  const [lines, setLines] = useState<CharacterAudioLine[]>([]);
  const [audioUrls, setAudioUrls] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    if (!scriptText.trim()) {
      setError("Paste some script text first.");
      return;
    }
    setStatus("loading");
    setError(null);
    audioUrls.forEach((url) => URL.revokeObjectURL(url));
    try {
      const response = await apiFetch<CharacterAudioResponse>("/voice/script-audio", {
        method: "POST",
        body: { script_text: scriptText },
      });
      setLines(response.lines);
      setAudioUrls(response.lines.map((line) => base64ToObjectUrl(line.audio_base64)));
      setStatus("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't generate character audio.");
      setStatus("error");
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Generate character audio</h2>
        <p className="mt-1 text-sm text-stone-400">
          Paste a scene (scene heading, action lines, and speaker-cued dialogue) to hear it read
          back with a distinct voice per character.
        </p>
      </div>

      <textarea
        value={scriptText}
        onChange={(event) => setScriptText(event.target.value)}
        rows={12}
        className="w-full rounded-lg border border-stone-700 bg-[#11101a] p-3 font-mono text-sm text-stone-100"
        placeholder={"లోపల — టీ దుకాణం — సాయంత్రం\n\nరవి\nఅన్నా, పని చేస్తాను..."}
      />

      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={() => void generate()}
        disabled={status === "loading"}
        className="rounded-lg bg-teal-300 px-4 py-2 text-sm font-medium text-stone-950 disabled:opacity-40"
      >
        {status === "loading" ? "Generating…" : "Generate character audio"}
      </button>

      {status === "ready" && lines.length > 0 && (
        <ol className="space-y-3">
          {lines.map((line, index) => (
            <li
              key={index}
              className="rounded-lg border border-stone-700 bg-[#11101a] p-3 text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-teal-200">
                  {line.speaker ?? (line.kind === "scene_heading" ? "Scene" : "Narrator")}
                </span>
                <span className="text-xs text-stone-500">{line.voice_id}</span>
              </div>
              <p className="mt-1 text-stone-300">{line.text}</p>
              <audio controls src={audioUrls[index]} className="mt-2 w-full" />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
