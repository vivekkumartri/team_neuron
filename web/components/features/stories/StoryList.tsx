"use client";

import { useStories, useSelectedBranch } from "../../../lib/story-context";

/**
 * The real story picker `IdScopedView`'s text boxes stand in for. Lists the
 * caller's stories (`GET /api/v1/stories`) and lets them select one's
 * `initial_branch_id` as the active branch — every story today has exactly
 * one branch (`create_story` always creates one), so this is a complete
 * picker for the current data model, not a stopgap.
 */
export function StoryList({ onSelect }: { onSelect?: (branchId: string) => void }) {
  const { stories, error, reload } = useStories();
  const { branchId: selectedBranchId, selectBranch } = useSelectedBranch();

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-rose-400 bg-rose-950/20 p-4 text-sm">
        {error}
        <button type="button" onClick={reload} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  if (!stories) {
    return (
      <p role="status" className="text-sm text-stone-400">
        Loading your stories…
      </p>
    );
  }

  if (stories.length === 0) {
    return <p className="text-sm text-stone-400">You haven't started a story yet.</p>;
  }

  return (
    <ul className="space-y-2">
      {stories.map((story) => {
        const disabled = !story.initial_branch_id;
        const isActive = story.initial_branch_id === selectedBranchId;
        return (
          <li key={story.id}>
            <button
              type="button"
              disabled={disabled}
              aria-current={isActive ? "true" : undefined}
              onClick={() => {
                if (!story.initial_branch_id) return;
                selectBranch(story.initial_branch_id);
                onSelect?.(story.initial_branch_id);
              }}
              className={`w-full rounded-lg border p-3 text-left disabled:opacity-40 ${
                isActive ? "border-teal-300 bg-teal-950/20" : "border-stone-700"
              }`}
            >
              <span className="font-medium">{story.title}</span>
              {disabled && (
                <span className="ml-2 text-xs text-stone-400">(still setting up)</span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
