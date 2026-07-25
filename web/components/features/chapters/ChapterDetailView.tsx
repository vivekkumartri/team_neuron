"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";
import { RevisionRequestForm } from "../../revisions/RevisionRequestForm";
import { ChapterNarrationPlayer } from "../../shared/ChapterNarrationPlayer";

interface DialogueLine {
  line_index: number;
  speaker_entity_id: string | null;
  line_text: string;
}

interface Scene {
  scene_index: number;
  summary: string;
  dialogue: DialogueLine[];
}

interface Choice {
  choice_index: number;
  label: string;
  progression_mode: string;
}

interface ChapterResponse {
  id: string;
  branch_id: string;
  chapter_index: number;
  status: string;
  published_at: string | null;
  scenes: Scene[];
  choices: Choice[];
}

/**
 * Gives `RevisionRequestForm` (built earlier, previously unreachable from
 * any route) a real home: fetches `GET /chapters/:id`, renders the
 * published screenplay, and hosts the revision form below it.
 */
export function ChapterDetailView({ chapterId }: { chapterId: string }) {
  const [chapter, setChapter] = useState<ChapterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<ChapterResponse>(`/chapters/${chapterId}`)
      .then((data) => {
        if (!cancelled) setChapter(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this chapter.");
      });
    return () => {
      cancelled = true;
    };
  }, [chapterId]);

  if (error) {
    return (
      <p role="alert" className="text-sm text-rose-300">
        {error}
      </p>
    );
  }

  if (!chapter) {
    return (
      <p role="status" className="text-sm text-stone-400">
        Loading chapter…
      </p>
    );
  }

  return (
    <article className="mx-auto max-w-3xl space-y-8">
      <header>
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
          Chapter {chapter.chapter_index} · {chapter.status}
        </p>
        {chapter.status === "PUBLISHED" && (
          <div className="mt-3">
            <ChapterNarrationPlayer chapterId={chapterId} />
          </div>
        )}
      </header>

      <div className="space-y-6">
        {chapter.scenes.map((scene) => (
          <section key={scene.scene_index} className="rounded-xl border border-stone-700 p-5">
            <p className="text-stone-200">{scene.summary}</p>
            {scene.dialogue.length > 0 && (
              <ul className="mt-4 space-y-2 text-sm text-stone-300">
                {scene.dialogue.map((line) => (
                  <li key={line.line_index}>{line.line_text}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>

      {chapter.choices.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          {chapter.choices.map((choice) => (
            <div
              key={choice.choice_index}
              className="rounded-lg border border-stone-700 p-3 text-center text-sm text-stone-300"
            >
              {choice.label}
            </div>
          ))}
        </div>
      )}

      <section className="rounded-xl border border-stone-700 bg-[#191724] p-6">
        <h2 className="text-lg font-semibold">Request a revision</h2>
        <p className="mt-1 text-sm text-stone-400">
          This never changes what's above directly — see the note below once submitted.
        </p>
        <div className="mt-4">
          <RevisionRequestForm chapterId={chapterId} />
        </div>
      </section>
    </article>
  );
}
