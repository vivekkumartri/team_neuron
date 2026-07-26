"use client";

/**
 * Demo mode is a purely client-side switch (see the "Demo mode" toggle in
 * `Sidebar.tsx`). When on, onboarding shows a picker over the canned
 * stories served from `GET /api/v1/demo/stories` instead of the normal
 * "write your own idea" flow, and picking one renders `DemoWorkspaceView`
 * instead of the real `WorkspaceView` — no generation jobs, no database.
 *
 * Kept in `localStorage` (not the backend) because demo mode is a property
 * of this browser/kiosk, not of any story or user account.
 */

import { useCallback, useEffect, useState } from "react";

const DEMO_MODE_KEY = "story-engine-demo-mode";
const DEMO_STORY_KEY = "story-engine-demo-story-id";

function readBoolean(key: string): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(key) === "1";
}

function readString(key: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(key);
}

export function useDemoMode(): [boolean, (enabled: boolean) => void] {
  const [enabled, setEnabledState] = useState(false);

  useEffect(() => {
    setEnabledState(readBoolean(DEMO_MODE_KEY));
    const onStorage = (event: StorageEvent) => {
      if (event.key === DEMO_MODE_KEY) setEnabledState(readBoolean(DEMO_MODE_KEY));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setEnabled = useCallback((value: boolean) => {
    window.localStorage.setItem(DEMO_MODE_KEY, value ? "1" : "0");
    if (!value) window.localStorage.removeItem(DEMO_STORY_KEY);
    setEnabledState(value);
  }, []);

  return [enabled, setEnabled];
}

/**
 * Sync, non-hook reads for use outside React components — `apiFetch`
 * (`api-client.ts`) and `useGenerationStream` (`generation-stream.ts`)
 * need to know "are we in demo mode, and for which saved story" on every
 * call, not just on mount, and neither is itself a component that could
 * call `useDemoMode()`.
 */
export function isDemoModeOn(): boolean {
  return readBoolean(DEMO_MODE_KEY);
}

export function currentDemoStoryId(): string | null {
  return readString(DEMO_STORY_KEY);
}

export function useSelectedDemoStory(): [string | null, (id: string | null) => void] {
  const [demoId, setDemoIdState] = useState<string | null>(null);

  useEffect(() => {
    setDemoIdState(readString(DEMO_STORY_KEY));
    const onStorage = (event: StorageEvent) => {
      if (event.key === DEMO_STORY_KEY) setDemoIdState(readString(DEMO_STORY_KEY));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setDemoId = useCallback((id: string | null) => {
    if (id) {
      window.localStorage.setItem(DEMO_STORY_KEY, id);
    } else {
      window.localStorage.removeItem(DEMO_STORY_KEY);
    }
    setDemoIdState(id);
  }, []);

  return [demoId, setDemoId];
}
