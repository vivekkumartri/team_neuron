"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "./api-client";

/**
 * The missing piece every `IdScopedView` text box in `app/page.tsx` stands
 * in for: a real selected-branch value, backed by the same
 * `story-engine-active-branch` localStorage key `CastLock.tsx` already
 * writes on Chapter 1 queuing (so a story created via onboarding is
 * automatically "selected" without an extra click).
 */
const ACTIVE_BRANCH_KEY = "story-engine-active-branch";

export interface StorySummary {
  id: string;
  title: string;
  personalization_enabled: boolean;
  agent_trace_enabled: boolean;
  initial_branch_id: string | null;
  initial_focal_entity_id: string | null;
}

export interface BranchSummary {
  id: string;
  name: string;
  chapter_count: number;
}

export function useStories(): {
  stories: StorySummary[] | null;
  error: string | null;
  reload: () => void;
} {
  const [stories, setStories] = useState<StorySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    apiFetch<StorySummary[]>("/stories")
      .then((data) => {
        if (!cancelled) setStories(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load your stories.");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return { stories, error, reload: () => setReloadToken((n) => n + 1) };
}

/**
 * `GET /api/v1/stories` doesn't return an `arc_id` today (only
 * `initial_branch_id`), so a full branch tree per story isn't fetchable yet
 * — `GET /arcs/{arc_id}/branches` exists but needs an arc id this response
 * doesn't carry. Until `StoryResponse` grows an `arc_id` field, this hook
 * takes one directly rather than silently returning nothing; callers that
 * only have a story's `initial_branch_id` should treat that single branch
 * as the full timeline for now (accurate for every story today, since
 * `create_story` always creates exactly one branch).
 */
export function useBranches(arcId: string | null): {
  branches: BranchSummary[] | null;
  error: string | null;
} {
  const [branches, setBranches] = useState<BranchSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!arcId) {
      setBranches(null);
      return;
    }
    let cancelled = false;
    apiFetch<BranchSummary[]>(`/arcs/${arcId}/branches`)
      .then((data) => {
        if (!cancelled) setBranches(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load branches for this story.");
      });
    return () => {
      cancelled = true;
    };
  }, [arcId]);

  return { branches, error };
}

/** Reads/writes the single globally "active" branch this browser is working in. */
export function useSelectedBranch(): {
  branchId: string | null;
  selectBranch: (branchId: string) => void;
} {
  const [branchId, setBranchId] = useState<string | null>(null);

  useEffect(() => {
    setBranchId(window.localStorage.getItem(ACTIVE_BRANCH_KEY));
  }, []);

  const selectBranch = useCallback((next: string) => {
    window.localStorage.setItem(ACTIVE_BRANCH_KEY, next);
    setBranchId(next);
  }, []);

  return { branchId, selectBranch };
}
