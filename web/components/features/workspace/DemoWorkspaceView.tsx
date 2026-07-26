"use client";

import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "../../../lib/api-client";

interface DemoDialogueLine {
  speaker_name: string | null;
  line_text: string;
}

interface DemoStoryboardScene {
  scene_number: number;
  location: string;
  action: string;
  emotion: string;
  image_asset_url: string | null;
  dialogue: DemoDialogueLine[];
}

interface DemoChapter {
  chapter_index: number;
  title: string;
  text: string;
  narration_asset_url: string | null;
  storyboard: DemoStoryboardScene[];
}

interface DemoCastMember {
  name: string;
  role: string;
  traits: string;
}

interface DemoStoryDetail {
  id: string;
  title: string;
  tagline: string;
  seed_prompt: string;
  cover_asset_url: string | null;
  cast: DemoCastMember[];
  chapters: DemoChapter[];
}

/**
 * Read-only replay of a pre-generated demo story (see `services/demo_store.py`
 * on the backend). Deliberately has none of `WorkspaceView`'s machinery for
 * live generation, SSE polling, or progression — it just fetches one bundle
 * and renders it.
 */
export function DemoWorkspaceView({ demoId, onExit }: { demoId: string; onExit: () => void }) {
  const [story, setStory] = useState<DemoStoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeChapterIndex, setActiveChapterIndex] = useState(1);

  useEffect(() => {
    let cancelled = false;
    setStory(null);
    setError(null);
    apiFetch<DemoStoryDetail>(`/demo/stories/${demoId}`)
      .then((data) => {
        if (!cancelled) {
          setStory(data);
          setActiveChapterIndex(data.chapters[0]?.chapter_index ?? 1);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Couldn't load this demo story.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [demoId]);

  if (error) {
    return (
      <div className="space-y-3">
        <p role="alert" className="text-sm text-rose-300">{error}</p>
        <button type="button" onClick={onExit} className="text-sm text-teal-200 underline">
          Back
        </button>
      </div>
    );
  }
  if (!story) {
    return <p className="text-sm text-stone-400">Loading demo story…</p>;
  }

  const chapter = story.chapters.find((c) => c.chapter_index === activeChapterIndex) ?? story.chapters[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Demo mode</p>
          <h1 className="mt-1 text-2xl font-semibold">{story.title}</h1>
          {story.tagline && <p className="mt-1 text-sm text-stone-400">{story.tagline}</p>}
          {story.seed_prompt && (
            <p className="mt-2 text-xs italic text-stone-500">Original prompt: "{story.seed_prompt}"</p>
          )}
        </div>
        <button
          type="button"
          onClick={onExit}
          className="rounded-lg border border-stone-600 px-3 py-2 text-sm"
        >
          Choose a different demo story
        </button>
      </div>

      {story.cast.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {story.cast.map((member) => (
            <span
              key={member.name}
              className="rounded-full border border-stone-700 bg-[#191724] px-3 py-1 text-xs text-stone-300"
              title={member.traits}
            >
              {member.name}
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {story.chapters.map((c) => (
          <button
            key={c.chapter_index}
            type="button"
            onClick={() => setActiveChapterIndex(c.chapter_index)}
            className={`rounded-full border px-3 py-1 text-sm ${
              c.chapter_index === activeChapterIndex
                ? "border-amber-300 text-amber-200"
                : "border-stone-700 text-stone-300"
            }`}
          >
            Ch. {c.chapter_index}
          </button>
        ))}
      </div>

      {chapter && (
        <article className="space-y-4 rounded-xl border border-stone-700 bg-[#191724] p-6">
          <h2 className="text-lg font-semibold text-stone-100">{chapter.title}</h2>
          {chapter.narration_asset_url && (
            // eslint-disable-next-line jsx-a11y/media-has-caption
            <audio controls src={chapter.narration_asset_url} className="w-full" />
          )}
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-200">
            {chapter.text}
          </p>

          {chapter.storyboard.length > 0 && (
            <section className="mt-4 space-y-4">
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
                Comic storyboard
              </p>
              {chapter.storyboard.map((scene) => (
                <div
                  key={scene.scene_number}
                  className="grid overflow-hidden rounded-xl border border-stone-700 bg-[#11101a] md:grid-cols-2"
                >
                  <div className="min-h-56 bg-stone-900">
                    {scene.image_asset_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={scene.image_asset_url}
                        alt={`Scene ${scene.scene_number}`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full min-h-56 items-center justify-center text-sm text-stone-500">
                        Image unavailable
                      </div>
                    )}
                  </div>
                  <div className="p-5">
                    <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
                      Scene {scene.scene_number}
                    </p>
                    <p className="mt-2 text-xs text-stone-500">
                      {scene.location} · {scene.emotion}
                    </p>
                    <ul className="mt-4 space-y-3">
                      {scene.dialogue.map((line, index) => (
                        <li key={index} className="text-sm leading-relaxed text-stone-200">
                          {line.speaker_name && (
                            <span className="font-semibold text-amber-200">{line.speaker_name}: </span>
                          )}
                          {line.line_text}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </section>
          )}
        </article>
      )}
    </div>
  );
}
