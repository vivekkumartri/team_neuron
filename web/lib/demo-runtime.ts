"use client";

/**
 * The in-browser "fake backend" for demo mode.
 *
 * The goal (per the user's explicit request): reuse the exact same
 * `OnboardingFlow`/`WorkspaceView`/`StoryboardView`/etc. components as the
 * real app — same seed form, same template picker, same cast editor and
 * lock button, same chapter tree, same focal-character dropdown, same
 * "Continue"/"Edit traits"/"Rewind" controls — with the *only* difference
 * being that every network call those components make gets answered from
 * the saved `demo_data/<id>/` bundle (fetched once from the real,
 * unauthenticated `GET /api/v1/demo/stories/{id}` endpoint) instead of
 * hitting Postgres or OpenAI.
 *
 * `api-client.ts`'s `apiFetch` calls `handleDemoRequest` for every request
 * while demo mode is on; `generation-stream.ts`'s `useGenerationStream`
 * checks `isDemoJobId` directly to skip the real `EventSource` entirely.
 * Everything below is deliberately synchronous/in-memory (a plain
 * module-level `Map`) — there is no database in demo mode, so state resets
 * on page reload, which is expected: it is a *replay* of saved content, not
 * a second persistence layer.
 *
 * ID scheme (all fake ids are self-describing, so a request can be routed
 * without any server round trip):
 *   story id / branch id  -> "demo:<bundleId>"
 *   chapter id            -> "demo:<bundleId>:ch<N>"
 *   cast member entity id -> "demo:<bundleId>:char<index>"
 *   job id                -> "demo:<bundleId>:job:<n>"
 */

import { currentDemoStoryId } from "./demo-mode";

// Deliberately not imported from `api-client.ts` (which imports this module
// for `handleDemoRequest`) to avoid a circular import between the two.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

const DEMO_PREFIX = "demo:";

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

interface DemoChapterBundle {
  chapter_index: number;
  title: string;
  text: string;
  narration_asset_url: string | null;
  storyboard: DemoStoryboardScene[];
}

interface DemoCastMemberBundle {
  name: string;
  role: string;
  traits: string;
}

interface DemoStoryBundle {
  id: string;
  title: string;
  tagline: string;
  seed_prompt: string;
  language: string;
  cast: DemoCastMemberBundle[];
  chapters: DemoChapterBundle[];
}

interface DemoCastMember {
  entity_id: string;
  name: string;
  role: string;
}

interface DemoSession {
  bundle: DemoStoryBundle;
  revealedChapters: number;
  cast: DemoCastMember[];
}

const sessions = new Map<string, DemoSession>();
const bundleLoads = new Map<string, Promise<DemoStoryBundle>>();

export class DemoApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "DemoApiError";
  }
}

function branchId(bundleId: string): string {
  return `${DEMO_PREFIX}${bundleId}`;
}

function chapterRef(bundleId: string, index: number): string {
  return `${DEMO_PREFIX}${bundleId}:ch${index}`;
}

function parseRef(raw: string): { bundleId: string; rest: string[] } | null {
  if (!raw.startsWith(DEMO_PREFIX)) return null;
  const [, bundleId, ...rest] = raw.split(":");
  if (!bundleId) return null;
  return { bundleId, rest };
}

async function loadBundle(bundleId: string): Promise<DemoStoryBundle> {
  let load = bundleLoads.get(bundleId);
  if (!load) {
    // A plain, un-intercepted fetch straight to the real (unauthenticated,
    // static-file-backed) demo endpoint — this is the one real network call
    // demo mode ever makes, and it never leaves this machine's own backend
    // reading its own `demo_data/` folder.
    load = fetch(`${API_BASE}/demo/stories/${bundleId}`, { credentials: "include" }).then(
      async (response) => {
        if (!response.ok) {
          throw new DemoApiError(response.status, "Couldn't load this demo story's saved data.");
        }
        return (await response.json()) as DemoStoryBundle;
      },
    );
    bundleLoads.set(bundleId, load);
  }
  return load;
}

async function getSession(bundleId: string): Promise<DemoSession> {
  let session = sessions.get(bundleId);
  if (!session) {
    const bundle = await loadBundle(bundleId);
    session = {
      bundle,
      revealedChapters: 0,
      cast: bundle.cast.map((member, index) => ({
        entity_id: `${DEMO_PREFIX}${bundleId}:char${index}`,
        name: member.name,
        role: member.role || "CHARACTER",
      })),
    };
    sessions.set(bundleId, session);
  }
  return session;
}

function chapterSummary(bundleId: string, chapter: DemoChapterBundle) {
  return {
    id: chapterRef(bundleId, chapter.chapter_index),
    chapter_index: chapter.chapter_index,
    status: "PUBLISHED",
    published_at: new Date().toISOString(),
  };
}

function chapterDetail(bundleId: string, chapter: DemoChapterBundle) {
  return {
    id: chapterRef(bundleId, chapter.chapter_index),
    branch_id: branchId(bundleId),
    chapter_index: chapter.chapter_index,
    status: "PUBLISHED",
    published_at: new Date().toISOString(),
    scenes: [{ scene_index: 1, summary: chapter.text, dialogue: [] }],
  };
}

function storyboardResponse(bundleId: string, chapter: DemoChapterBundle) {
  if (chapter.storyboard.length === 0) {
    return null;
  }
  return {
    job_id: `${chapterRef(bundleId, chapter.chapter_index)}:storyboard`,
    chapter_id: chapterRef(bundleId, chapter.chapter_index),
    status: "SUCCEEDED",
    error_message: null,
    scenes: chapter.storyboard.map((scene) => ({
      scene_number: scene.scene_number,
      status: "SUCCEEDED",
      image_url: scene.image_asset_url,
      location: scene.location,
      action: scene.action,
      emotion: scene.emotion,
      characters: [],
      dialogue: scene.dialogue,
    })),
  };
}

export function isDemoJobId(jobId: string | null): boolean {
  return jobId !== null && jobId.startsWith(DEMO_PREFIX);
}

/** Canned agent-activity lines shown briefly before a demo chapter "arrives". */
export function demoActivityEvents(): {
  sequence: number;
  summary: string;
  agent: string;
  recipient_agent: string | null;
  status: string;
  entity_id: string | null;
}[] {
  return [
    {
      sequence: 1,
      summary: "Reading the next chapter from this demo's saved data.",
      agent: "director",
      recipient_agent: null,
      status: "GENERATING",
      entity_id: null,
    },
    {
      sequence: 2,
      summary: "No live agents run in demo mode — this chapter was pre-generated.",
      agent: "world",
      recipient_agent: null,
      status: "PUBLISHED",
      entity_id: null,
    },
  ];
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

/**
 * Routes one `apiFetch` call to fake data. Returns `undefined` for paths
 * this module doesn't recognize, which tells `apiFetch` to fall through to
 * a real network call (should not normally happen for anything the
 * onboarding/workspace screens actually use — see the module docstring for
 * the full covered surface).
 */
export async function handleDemoRequest(path: string, options: RequestOptions): Promise<unknown> {
  const method = options.method ?? "GET";

  // --- Pre-story-creation steps (no ids exist yet) ---------------------
  if (path === "/stories/cast-proposal" && method === "POST") {
    const bundleId = currentBundleIdOrThrow();
    const session = await getSession(bundleId);
    return {
      characters: session.bundle.cast.map((member) => ({
        name: member.name,
        role: member.role,
        voice: "",
        traits: member.traits,
        visual: "",
        background_story: "",
      })),
      source: "seed_fallback",
    };
  }
  if (path === "/stories" && method === "POST") {
    const bundleId = currentBundleIdOrThrow();
    const session = await getSession(bundleId);
    return {
      id: branchId(bundleId),
      language: session.bundle.language || "en",
      initial_branch_id: branchId(bundleId),
      initial_focal_entity_id: session.cast[0]?.entity_id ?? null,
    };
  }
  if (path === "/me/preferences") {
    return {};
  }
  if (path === "/me/personalization-snapshots" && method === "POST") {
    return {};
  }
  if (path === "/me/quota") {
    return [];
  }

  // --- Everything below operates on a "demo:<bundleId>[...]" id already
  // embedded in the URL, so the bundle is unambiguous from the path alone.
  const storyLockMatch = path.match(/^\/stories\/([^/]+)\/cast-lock$/);
  if (storyLockMatch && method === "POST") {
    const ref = parseRef(storyLockMatch[1]);
    if (ref) return {};
  }

  const branchMatch = path.match(/^\/branches\/([^/]+)$/);
  if (branchMatch && method === "GET") {
    const ref = parseRef(branchMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      return { id: branchId(ref.bundleId), name: session.bundle.title, parent_branch_id: null };
    }
  }

  const chaptersListMatch = path.match(/^\/branches\/([^/]+)\/chapters$/);
  if (chaptersListMatch && method === "GET") {
    const ref = parseRef(chaptersListMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      return session.bundle.chapters
        .filter((chapter) => chapter.chapter_index <= session.revealedChapters)
        .map((chapter) => chapterSummary(ref.bundleId, chapter));
    }
  }

  const castListMatch = path.match(/^\/branches\/([^/]+)\/cast-members$/);
  if (castListMatch) {
    const ref = parseRef(castListMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      if (method === "GET") return session.cast;
      if (method === "POST") {
        const body = options.body as { name?: string } | undefined;
        const name = body?.name?.trim();
        if (!name) throw new DemoApiError(422, "A character needs a name.");
        const member: DemoCastMember = {
          entity_id: `${DEMO_PREFIX}${ref.bundleId}:char${session.cast.length}:${Date.now()}`,
          name,
          role: "CHARACTER",
        };
        session.cast.push(member);
        return member;
      }
    }
  }

  const castDeleteMatch = path.match(/^\/branches\/([^/]+)\/cast-members\/([^/]+)$/);
  if (castDeleteMatch && method === "DELETE") {
    const ref = parseRef(castDeleteMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      if (session.cast.length <= 1) {
        throw new DemoApiError(409, "A story needs at least one character.");
      }
      session.cast = session.cast.filter((member) => member.entity_id !== castDeleteMatch[2]);
      return {};
    }
  }

  const progressionMatch = path.match(/^\/branches\/([^/]+)\/progression$/);
  if (progressionMatch && method === "POST") {
    const ref = parseRef(progressionMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      const total = session.bundle.chapters.length;
      if (session.revealedChapters >= total) {
        throw new DemoApiError(
          409,
          `This demo story only has ${total} pre-generated chapter${total === 1 ? "" : "s"} saved.`,
        );
      }
      session.revealedChapters += 1;
      return {
        job_id: `${DEMO_PREFIX}${ref.bundleId}:job:${session.revealedChapters}:${Date.now()}`,
        branch_id: branchId(ref.bundleId),
        status: "QUEUED",
      };
    }
  }

  const chapterDetailMatch = path.match(/^\/chapters\/([^/]+)$/);
  if (chapterDetailMatch && method === "GET") {
    const ref = parseRef(chapterDetailMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      const index = Number(ref.rest[0]?.replace(/^ch/, ""));
      const chapter = session.bundle.chapters.find((c) => c.chapter_index === index);
      if (!chapter) throw new DemoApiError(404, "Chapter not found");
      return chapterDetail(ref.bundleId, chapter);
    }
  }

  const storyboardMatch = path.match(/^\/chapters\/([^/]+)\/storyboard$/);
  if (storyboardMatch) {
    const ref = parseRef(storyboardMatch[1]);
    if (ref) {
      const session = await getSession(ref.bundleId);
      const index = Number(ref.rest[0]?.replace(/^ch/, ""));
      const chapter = session.bundle.chapters.find((c) => c.chapter_index === index);
      if (!chapter) throw new DemoApiError(404, "Chapter not found");
      const response = storyboardResponse(ref.bundleId, chapter);
      if (method === "GET") {
        if (!response) throw new DemoApiError(404, "Storyboard not created");
        return response;
      }
      if (method === "POST") {
        if (response) return response;
        return {
          job_id: `${chapterRef(ref.bundleId, index)}:storyboard`,
          chapter_id: chapterRef(ref.bundleId, index),
          status: "FAILED",
          error_message: "This demo chapter has no pre-generated storyboard saved.",
          scenes: [],
        };
      }
    }
  }

  const narrationMatch = path.match(/^\/voice\/chapters\/([^/]+)\/narration/);
  if (narrationMatch) {
    if (method === "GET") {
      return { status: "not_started", estimated_seconds: null, error: null, lines: null, total_lines: 0 };
    }
    if (method === "POST") {
      throw new DemoApiError(503, "Multi-voice narration isn't available in demo mode.");
    }
  }

  return undefined;
}

function currentBundleIdOrThrow(): string {
  const id = currentDemoStoryId();
  if (!id) {
    throw new DemoApiError(400, "No demo story is selected.");
  }
  return id;
}
