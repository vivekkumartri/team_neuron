"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch, apiBase } from "../../../lib/api-client";

interface StoryboardDialogue {
  line_number: number;
  speaker_entity_id: string | null;
  speaker_name: string | null;
  line_text: string;
}

interface StoryboardScene {
  scene_number: number;
  status: string;
  image_url: string | null;
  location: string;
  action: string;
  emotion: string;
  characters: { entity_id: string; name: string; reference_asset_id: string | null }[];
  dialogue: StoryboardDialogue[];
}

interface StoryboardResponse {
  job_id: string;
  chapter_id: string;
  status: string;
  error_message: string | null;
  scenes: StoryboardScene[];
}

function assetUrl(path: string): string {
  return path.startsWith("http") ? path : `${apiBase().replace(/\/api\/v1$/, "")}${path}`;
}

export function StoryboardView({ chapterId }: { chapterId: string }) {
  const [storyboard, setStoryboard] = useState<StoryboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<StoryboardResponse>(`/chapters/${chapterId}/storyboard`);
      setStoryboard(data);
    } catch (caught) {
      if (!(caught instanceof ApiError && caught.status === 404)) {
        setError(caught instanceof ApiError ? caught.message : "Couldn't load the storyboard.");
      }
    } finally {
      setLoading(false);
    }
  }, [chapterId]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setStoryboard(null);
    void load();
  }, [load]);

  useEffect(() => {
    if (!storyboard || !["QUEUED", "RUNNING"].includes(storyboard.status)) return;
    const timer = window.setInterval(() => void load(), 2_000);
    return () => window.clearInterval(timer);
  }, [load, storyboard]);

  const create = async () => {
    setStarting(true);
    setError(null);
    try {
      const data = await apiFetch<StoryboardResponse>(`/chapters/${chapterId}/storyboard`, {
        method: "POST",
      });
      setStoryboard(data);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Couldn't start the storyboard.");
    } finally {
      setStarting(false);
    }
  };

  if (loading) return <p className="text-sm text-stone-400">Checking comic storyboard…</p>;
  if (error) {
    return (
      <div className="space-y-2">
        <p role="alert" className="text-sm text-rose-300">{error}</p>
        <button type="button" onClick={() => void load()} className="text-sm text-teal-200 underline">
          Retry
        </button>
      </div>
    );
  }
  if (!storyboard) {
    return (
      <div className="rounded-lg border border-violet-400/40 bg-violet-950/20 p-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Comic storyboard</p>
        <p className="mt-2 text-sm text-stone-300">
          Turn this chapter into scene-by-scene comic panels. Original dialogue stays unchanged.
        </p>
        <button
          type="button"
          onClick={() => void create()}
          disabled={starting}
          className="mt-3 rounded-lg bg-violet-300 px-4 py-2 text-sm font-medium text-stone-950 disabled:opacity-40"
        >
          {starting ? "Starting storyboard…" : "Create comic storyboard"}
        </button>
      </div>
    );
  }
  if (storyboard.status !== "SUCCEEDED") {
    return (
      <div className="rounded-lg border border-violet-400/40 bg-violet-950/20 p-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Comic storyboard</p>
        <p role="status" className="mt-2 text-sm text-stone-300">
          {storyboard.status === "FAILED" ? storyboard.error_message ?? "Storyboard failed." : "Building comic panels…"}
        </p>
        {storyboard.status === "FAILED" && (
          <button type="button" onClick={() => void create()} className="mt-3 text-sm text-teal-200 underline">
            Try again
          </button>
        )}
      </div>
    );
  }

  return (
    <section aria-label="Comic storyboard" className="mt-4 space-y-4">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Comic storyboard</p>
        <p className="mt-1 text-sm text-stone-400">One illustration per scene with the original dialogue.</p>
      </div>
      {storyboard.scenes.map((scene) => (
        <article key={scene.scene_number} className="grid overflow-hidden rounded-xl border border-stone-700 bg-[#11101a] md:grid-cols-2">
          <div className="min-h-56 bg-stone-900">
            {scene.image_url ? (
              <img src={assetUrl(scene.image_url)} alt={`Scene ${scene.scene_number}`} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full min-h-56 items-center justify-center text-sm text-stone-500">Image unavailable</div>
            )}
          </div>
          <div className="p-5">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Scene {scene.scene_number}</p>
            <p className="mt-2 text-xs text-stone-500">{scene.location} · {scene.emotion}</p>
            <ul className="mt-4 space-y-3">
              {scene.dialogue.map((line) => (
                <li key={line.line_number} className="text-sm leading-relaxed text-stone-200">
                  {line.speaker_name && <span className="font-semibold text-amber-200">{line.speaker_name}: </span>}
                  {line.line_text}
                </li>
              ))}
            </ul>
          </div>
        </article>
      ))}
    </section>
  );
}
