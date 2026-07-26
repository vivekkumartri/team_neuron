"use client";

import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "../../../lib/api-client";

interface DemoStorySummary {
  id: string;
  title: string;
  tagline: string;
  seed_prompt: string;
  cover_asset_url: string | null;
}

export function DemoStoryPicker({ onSelect }: { onSelect: (demoId: string) => void }) {
  const [stories, setStories] = useState<DemoStorySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<DemoStorySummary[]>("/demo/stories")
      .then((data) => {
        if (!cancelled) setStories(data);
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Couldn't load demo stories.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p role="alert" className="text-sm text-rose-300">{error}</p>;
  }
  if (!stories) {
    return <p className="text-sm text-stone-400">Loading demo stories…</p>;
  }
  if (stories.length === 0) {
    return (
      <p className="text-sm text-stone-400">
        No demo stories yet. Run <code>scripts/export_demo_story.py</code> against a real branch
        to create one under <code>demo_data/</code>.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-300">
        Demo mode is on — pick one of the pre-generated stories below. Nothing here calls
        OpenAI or writes to the database; it just replays saved chapters, comic panels, and
        narration.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {stories.map((story) => (
          <button
            key={story.id}
            type="button"
            onClick={() => onSelect(story.id)}
            className="rounded-xl border border-stone-700 bg-[#11101a] p-4 text-left transition hover:border-violet-400/60"
          >
            {story.cover_asset_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={story.cover_asset_url}
                alt=""
                className="mb-3 h-32 w-full rounded-lg object-cover"
              />
            )}
            <p className="font-semibold text-stone-100">{story.title}</p>
            {story.tagline && <p className="mt-1 text-sm text-stone-400">{story.tagline}</p>}
            {story.seed_prompt && (
              <p className="mt-2 text-xs italic text-stone-500">"{story.seed_prompt}"</p>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
