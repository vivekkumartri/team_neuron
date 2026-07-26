"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, ApiError } from "../../../lib/api-client";
import { useGenerationStream } from "../../../lib/generation-stream";
import { ActivityFeed } from "./ActivityFeed";
import { AgentCoordinationCanvas } from "./AgentCoordinationCanvas";
import { BranchControls, type ProgressionMode } from "./BranchControls";
import { type QuotaBannerState } from "./QuotaBanner";
import { ChapterNarrationTab } from "../../shared/ChapterNarrationTab";
import { VoiceInputButton } from "../../shared/VoiceInputButton";
import { StoryboardView } from "./StoryboardView";

interface ProgressionResponse {
  job_id: string;
  branch_id: string;
  status: string;
}

interface ChapterSummary {
  id: string;
  chapter_index: number;
  status: string;
  published_at: string | null;
}

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

interface ChapterDetail {
  id: string;
  branch_id: string;
  chapter_index: number;
  status: string;
  published_at: string | null;
  scenes: Scene[];
}

interface CastMemberResponse {
  entity_id: string;
  name: string;
  role: string;
}

interface BranchSummary {
  id: string;
  name: string;
  parent_branch_id: string | null;
}

const MODE_TO_API: Record<ProgressionMode, "CONTINUE" | "EDIT_TRAITS" | "REWIND"> = {
  continue: "CONTINUE",
  "edit-traits": "EDIT_TRAITS",
  "jump-rewind": "REWIND",
};

/**
 * Replaces the earlier static `WorkspaceStudio` demo (whose three
 * progression buttons had no `onClick` at all) with the real, wired path:
 * `BranchControls` submits to `POST /branches/:id/progression`
 * (`api/routes/progression.py`), and once a job id comes back,
 * `useGenerationStream` opens the real SSE connection instead of the
 * `/api/v1/generation-events/demo` stand-in.
 */
export function WorkspaceView({ branchId }: { branchId: string }) {
  const [chapterId, setChapterId] = useState("");
  const [focalEntityId, setFocalEntityId] = useState("");
  const [traitChange, setTraitChange] = useState("");
  const [rewindTo, setRewindTo] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [quotaState, setQuotaState] = useState<QuotaBannerState | null>(null);
  const [latestChapter, setLatestChapter] = useState<ChapterDetail | null>(null);
  const [chapterLoadError, setChapterLoadError] = useState<string | null>(null);
  const [chapterTree, setChapterTree] = useState<ChapterSummary[]>([]);
  const [cast, setCast] = useState<CastMemberResponse[]>([]);
  const [newCharacterName, setNewCharacterName] = useState("");
  const [castBusy, setCastBusy] = useState(false);
  const [castError, setCastError] = useState<string | null>(null);
  const [chapterTab, setChapterTab] = useState<"story" | "narration">("story");
  const [mainTab, setMainTab] = useState<"story" | "characters">("story");
  const [branch, setBranch] = useState<BranchSummary | null>(null);

  const { events, connectionState, complete } = useGenerationStream(jobId);

  // Surfaces the branch's own name (e.g. "Ch. 1 (Branch B)" for a rewind
  // branch — see `progression.py`) so it's actually visible which timeline
  // you're on, instead of only existing as an opaque id in localStorage.
  useEffect(() => {
    if (!branchId) return;
    let cancelled = false;
    apiFetch<BranchSummary>(`/branches/${branchId}`)
      .then((data) => {
        if (!cancelled) setBranch(data);
      })
      .catch(() => {
        if (!cancelled) setBranch(null);
      });
    return () => {
      cancelled = true;
    };
  }, [branchId]);

  const refreshCast = useCallback(async () => {
    if (!branchId) return;
    try {
      const members = await apiFetch<CastMemberResponse[]>(`/branches/${branchId}/cast-members`);
      setCast(members);
    } catch {
      // Cast panel is a convenience view; leave existing state on failure.
    }
  }, [branchId]);

  useEffect(() => {
    void refreshCast();
  }, [refreshCast]);

  const addCharacter = async () => {
    const name = newCharacterName.trim();
    if (!name) return;
    setCastBusy(true);
    setCastError(null);
    try {
      await apiFetch<CastMemberResponse>(`/branches/${branchId}/cast-members`, {
        method: "POST",
        body: { name },
      });
      setNewCharacterName("");
      await refreshCast();
    } catch (err) {
      setCastError(err instanceof ApiError ? err.message : "Couldn't add that character.");
    } finally {
      setCastBusy(false);
    }
  };

  const removeCharacter = async (entityId: string) => {
    setCastBusy(true);
    setCastError(null);
    try {
      await apiFetch<void>(`/branches/${branchId}/cast-members/${entityId}`, { method: "DELETE" });
      if (focalEntityId === entityId) setFocalEntityId("");
      await refreshCast();
    } catch (err) {
      setCastError(err instanceof ApiError ? err.message : "Couldn't remove that character.");
    } finally {
      setCastBusy(false);
    }
  };

  // The published chapters so far on this branch, shown as a compact tree at
  // the top of the screen — refetched whenever a new one is published, so an
  // author picking "Continue" for the next chapter can see what came before
  // without hunting for it.
  useEffect(() => {
    if (!branchId) return;
    let cancelled = false;
    (async () => {
      try {
        const chapters = await apiFetch<ChapterSummary[]>(`/branches/${branchId}/chapters`);
        if (!cancelled) setChapterTree(chapters.filter((c) => c.status === "PUBLISHED"));
      } catch {
        // Non-critical: the tree is a convenience view, not required to work.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [branchId, complete]);

  // The progression/job response never returns a chapter id (only a job
  // id) — once the SSE stream reports `complete`, look up the branch's
  // chapters to find the one this job just published, then fetch its full
  // text so it actually renders instead of the static "ready" banner. This
  // also fills `chapterId` so the *next* "Continue" click sends the real
  // latest chapter id instead of null (which was regenerating chapter 1
  // every time instead of continuing).
  useEffect(() => {
    if (!complete || !branchId) return;
    let cancelled = false;
    (async () => {
      try {
        const chapters = await apiFetch<ChapterSummary[]>(`/branches/${branchId}/chapters`);
        const published = chapters.filter((chapter) => chapter.status === "PUBLISHED");
        const latest = published[published.length - 1];
        if (!latest || cancelled) return;
        const detail = await apiFetch<ChapterDetail>(`/chapters/${latest.id}`);
        if (cancelled) return;
        setLatestChapter(detail);
        setChapterId(detail.id);
        setChapterLoadError(null);
        setChapterTab("story");
      } catch {
        if (!cancelled) {
          setChapterLoadError("Couldn't load the chapter text. It may still be publishing.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [complete, branchId, jobId]);

  useEffect(() => {
    const activeBranch = window.localStorage.getItem("story-engine-active-branch");
    const activeJob = window.localStorage.getItem("story-engine-active-job");
    if (activeBranch === branchId && activeJob) {
      setJobId(activeJob);
    }
    // Prefill the focal entity from cast-lock time (see CastLock.tsx) so
    // "Continue automatically" works without the author hand-typing a raw
    // UUID — leaving this blank used to send `focal_entity_id: ""`, which
    // FastAPI rejects with a 422 the UI then rendered unreadably.
    const savedFocalEntity = window.localStorage.getItem(
      `story-engine-focal-entity-${branchId}`,
    );
    if (savedFocalEntity) {
      setFocalEntityId(savedFocalEntity);
    }
  }, [branchId]);

  const refreshQuota = useCallback(async () => {
    try {
      const states = await apiFetch<QuotaBannerState[]>("/me/quota");
      setQuotaState(
        states.find((state) => state.exceeded) ??
          states.find((state) => state.approaching) ??
          null,
      );
    } catch {
      // Quota visibility must not prevent an author from viewing or working
      // in an existing branch when the read-only quota endpoint is unavailable.
      setQuotaState(null);
    }
  }, []);

  useEffect(() => {
    void refreshQuota();
  }, [refreshQuota]);

  const submit = async (mode: ProgressionMode) => {
    setError(null);
    setSubmitting(true);
    try {
      const response = await apiFetch<ProgressionResponse>(`/branches/${branchId}/progression`, {
        method: "POST",
        // Without a client-supplied key, the backend derives one from
        // `chapter_id` alone (`auto-{chapter_id or 'chapter-1'}-{mode}`).
        // Continuing without editing anything leaves `chapterId` blank on
        // every click, which used to produce the SAME derived key every
        // time — so clicking "Continue automatically" for chapter 2 would
        // silently replay chapter 1's old response instead of starting a
        // new job. A fresh key per real click fixes that.
        idempotencyKey: crypto.randomUUID(),
        body: {
          chapter_id: chapterId.trim() || null,
          focal_entity_id: focalEntityId.trim() || null,
          mode: MODE_TO_API[mode],
          trait_change: mode === "edit-traits" ? traitChange || null : null,
          rewind_to_chapter_id: mode === "jump-rewind" ? rewindTo || null : null,
        },
      });
      setJobId(response.job_id);
      window.localStorage.setItem("story-engine-active-job", response.job_id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This branch already has an active generation job in progress.");
      } else if (err instanceof ApiError) {
        // Show the real backend reason (already made readable by
        // `formatErrorDetail` in api-client.ts) instead of a generic
        // message that hides what actually happened — e.g. a 429 quota
        // block, or a 422 validation error, both have a real, useful
        // message by this point.
        setError(err.message);
      } else {
        setError("Couldn't submit that. Nothing changed.");
      }
    } finally {
      setSubmitting(false);
      void refreshQuota();
    }
  };

  // A job already exists for this branch (set either right after cast-lock
  // via localStorage, or after a manual submit below) and hasn't finished
  // streaming yet: show generation itself as the primary screen instead of
  // the raw "Advance this branch" ID-entry form. Landing straight on that
  // form after locking a cast — instead of watching Chapter 1 actually
  // generate — was the reported problem; the story is meant to start
  // generating immediately after the cast conversation, not wait on a
  // second manual step.
  const isGenerating = jobId !== null && !complete;
  // A job that dies mid-run (e.g. an OpenAI request timeout) never writes its
  // final "PUBLISHED"/"BLOCKED" event — it just goes straight to FAILED — but
  // the SSE stream still emits `generation-complete` since FAILED is terminal.
  // Without checking for a PUBLISHED event, the UI showed "Chapter 1 is
  // ready" even when generation had actually failed with nothing published.
  const succeeded = events.some((event) => event.status === "PUBLISHED");

  const chapterTreeStrip = chapterTree.length > 0 && (
    <nav aria-label="Story so far" className="flex flex-wrap items-center gap-2 rounded-xl border border-stone-700 bg-[#11101a] p-3">
      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-stone-500">
        Story so far
      </span>
      {chapterTree.map((chapter, index) => (
        <span key={chapter.id} className="flex items-center gap-2">
          <button
            type="button"
            onClick={async () => {
              try {
                const detail = await apiFetch<ChapterDetail>(`/chapters/${chapter.id}`);
                setLatestChapter(detail);
                setChapterLoadError(null);
                setChapterTab("story");
              } catch {
                setChapterLoadError("Couldn't load that chapter.");
              }
            }}
            className="rounded-full border border-stone-600 px-2.5 py-1 text-xs text-stone-200 hover:border-teal-300 hover:text-teal-200"
            title={`View chapter ${chapter.chapter_index}`}
          >
            Ch. {chapter.chapter_index}
          </button>
          {index < chapterTree.length - 1 && <span className="text-stone-600">→</span>}
        </span>
      ))}
    </nav>
  );

  if (isGenerating) {
    return (
      <section className="mx-auto max-w-3xl space-y-6">
        {chapterTreeStrip}
        <div className="rounded-xl border border-teal-400/60 bg-teal-950/20 p-6 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">
            Generating your story
          </p>
          <p className="mt-2 text-lg font-medium text-stone-100">
            The cast is coming to life — Chapter 1 is being written now.
          </p>
          <p className="mt-1 text-sm text-stone-400">
            Job <code>{jobId}</code> — {connectionState}
          </p>
        </div>
        <div className="rounded-xl border border-stone-700 bg-[#191724] p-4">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">
            Agent activity
          </p>
          <div className="mt-4 space-y-4">
            <AgentCoordinationCanvas events={events} />
            <ActivityFeed events={events} />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-7xl space-y-6">
      {branch && (
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-stone-500">
          {branch.name}
        </p>
      )}
      <div className="flex overflow-hidden rounded-lg border border-stone-700 text-xs w-fit">
        <button
          type="button"
          onClick={() => setMainTab("story")}
          aria-current={mainTab === "story" ? "page" : undefined}
          className={`px-4 py-2 ${mainTab === "story" ? "bg-teal-950/40 text-teal-200" : "text-stone-300"}`}
        >
          Story
        </button>
        <button
          type="button"
          onClick={() => setMainTab("characters")}
          aria-current={mainTab === "characters" ? "page" : undefined}
          className={`px-4 py-2 ${mainTab === "characters" ? "bg-teal-950/40 text-teal-200" : "text-stone-300"}`}
        >
          Characters {cast.length > 0 ? `(${cast.length})` : ""}
        </button>
      </div>

      {mainTab === "characters" ? (
        <div className="mx-auto max-w-2xl rounded-xl border border-stone-700 bg-[#191724] p-6">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">Cast</p>
          <p className="mt-1 text-sm text-stone-400">
            Add or remove characters here — the next chapter you generate only ever draws on
            whoever is currently in this list.
          </p>
          <ul className="mt-4 space-y-2">
            {cast.map((member) => (
              <li
                key={member.entity_id}
                className="flex items-center justify-between gap-2 rounded-lg border border-stone-700 p-3 text-sm"
              >
                <span>{member.name}</span>
                <button
                  type="button"
                  disabled={castBusy || cast.length <= 1}
                  onClick={() => void removeCharacter(member.entity_id)}
                  title={cast.length <= 1 ? "A story needs at least one character" : undefined}
                  className="text-xs text-rose-300 underline underline-offset-4 disabled:opacity-40"
                >
                  Remove
                </button>
              </li>
            ))}
            {cast.length === 0 && <li className="text-sm text-stone-400">No cast loaded yet.</li>}
          </ul>
          <div className="mt-4 flex gap-2">
            <input
              value={newCharacterName}
              onChange={(event) => setNewCharacterName(event.target.value)}
              placeholder="New character name"
              className="min-w-0 flex-1 rounded-lg border border-stone-700 bg-[#11101a] p-2 text-sm"
              onKeyDown={(event) => {
                if (event.key === "Enter") void addCharacter();
              }}
            />
            <button
              type="button"
              disabled={castBusy || !newCharacterName.trim()}
              onClick={() => void addCharacter()}
              className="rounded-lg border border-teal-300/60 px-3 py-2 text-sm text-teal-200 disabled:opacity-40"
            >
              Add
            </button>
          </div>
          {castError && (
            <p role="alert" className="mt-2 text-sm text-rose-300">
              {castError}
            </p>
          )}
        </div>
      ) : (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <article className="rounded-xl border border-stone-700 bg-[#191724] p-6">
        {chapterTreeStrip && <div className="mb-4">{chapterTreeStrip}</div>}
        {jobId && complete && succeeded && (
          <p className="mb-4 rounded-lg border border-teal-400/50 bg-teal-950/20 p-3 text-sm text-teal-100">
            {latestChapter
              ? `Chapter ${latestChapter.chapter_index} is ready. Use the controls below to continue the story, edit traits, or rewind.`
              : "Chapter is ready. Loading the text…"}
          </p>
        )}
        {jobId && complete && !succeeded && (
          <p className="mb-4 rounded-lg border border-rose-400/50 bg-rose-950/20 p-3 text-sm text-rose-100">
            Generation didn&apos;t finish successfully (the evaluator rejected the candidate, or
            the request failed/timed out). Nothing was published — try Continue again.
          </p>
        )}
        {chapterLoadError && (
          <p className="mb-4 text-sm text-rose-300">{chapterLoadError}</p>
        )}
        {/* Whatever chapter is currently selected — the one a job just published, or one
            picked from "Story so far" above — stays visible here regardless of job state,
            so an author can browse back to any previous chapter's full text at any time. */}
        {latestChapter && (
          <div className="mb-6">
            <div className="mb-3 flex items-center justify-between">
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
                Chapter {latestChapter.chapter_index}
              </p>
              {latestChapter.status === "PUBLISHED" && (
                <div className="flex overflow-hidden rounded-lg border border-stone-700 text-xs">
                  <button
                    type="button"
                    onClick={() => setChapterTab("story")}
                    aria-current={chapterTab === "story" ? "page" : undefined}
                    className={`px-3 py-2 ${chapterTab === "story" ? "bg-teal-950/40 text-teal-200" : "text-stone-300"}`}
                  >
                    Story
                  </button>
                  <button
                    type="button"
                    onClick={() => setChapterTab("narration")}
                    aria-current={chapterTab === "narration" ? "page" : undefined}
                    className={`px-3 py-2 ${chapterTab === "narration" ? "bg-teal-950/40 text-teal-200" : "text-stone-300"}`}
                  >
                    Narration
                  </button>
                </div>
              )}
            </div>
            {chapterTab === "narration" && latestChapter.status === "PUBLISHED" ? (
              <ChapterNarrationTab chapterId={latestChapter.id} />
            ) : (
              <div className="space-y-3 rounded-lg border border-stone-700 bg-[#11101a] p-4 text-stone-100">
                {latestChapter.scenes.map((scene) => (
                  <div key={scene.scene_index}>
                    <p className="whitespace-pre-wrap leading-relaxed">{scene.summary}</p>
                    {scene.dialogue.length > 0 && (
                      <ul className="mt-2 space-y-1 text-stone-300">
                        {scene.dialogue.map((line) => (
                          <li key={line.line_index}>{line.line_text}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
                <StoryboardView chapterId={latestChapter.id} />
              </div>
            )}
          </div>
        )}
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
          Advance this branch
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            Chapter ID
            <input
              value={chapterId}
              onChange={(event) => setChapterId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 font-mono text-xs"
            />
          </label>
          <label className="block text-sm">
            Focal character
            <select
              value={focalEntityId}
              onChange={(event) => setFocalEntityId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 text-sm"
            >
              <option value="">Select a character…</option>
              {cast.map((member) => (
                <option key={member.entity_id} value={member.entity_id}>
                  {member.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm sm:col-span-2">
            Trait change (only used for "Edit traits")
            <div className="relative mt-1">
              <input
                value={traitChange}
                onChange={(event) => setTraitChange(event.target.value)}
                className="w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 pr-12 text-sm"
              />
              <VoiceInputButton
                label="Speak trait change"
                onTranscript={(text) =>
                  setTraitChange((current) => (current.trim() ? `${current.trim()} ${text}` : text))
                }
              />
            </div>
          </label>
          <label className="block text-sm sm:col-span-2">
            Rewind-to chapter ID (only used for "Jump / rewind")
            <input
              value={rewindTo}
              onChange={(event) => setRewindTo(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 font-mono text-xs"
            />
          </label>
        </div>
        {error && (
          <p role="alert" className="mt-3 text-sm text-rose-300">
            {error}
          </p>
        )}
        <div className="mt-6">
          <BranchControls onSelect={submit} disabled={submitting} />
        </div>
        {jobId && (
          <p className="mt-4 text-sm text-stone-400">
            Job <code>{jobId}</code> — {complete ? "complete" : connectionState}
          </p>
        )}
      </article>
      <aside aria-live="polite" className="rounded-xl border border-stone-700 bg-[#191724] p-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">
          Agent activity
        </p>
        <div className="mt-4">
          {jobId ? (
            <div className="space-y-4">
              <AgentCoordinationCanvas events={events} />
              <ActivityFeed events={events} />
            </div>
          ) : (
            <p className="text-sm text-stone-400">
              Submit a progression mode to start streaming activity.
            </p>
          )}
        </div>
      </aside>
    </div>
      )}
    </section>
  );
}
