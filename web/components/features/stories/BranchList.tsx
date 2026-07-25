"use client";

import { useBranches } from "../../../lib/story-context";

/**
 * Full branch-tree picker for one arc. Currently unreachable from
 * `StoryList` (no `arc_id` in `GET /stories` yet — see `story-context.ts`'s
 * doc comment), but built against the real `GET /arcs/{arc_id}/branches`
 * response shape so it's ready once that gap closes.
 */
export function BranchList({
  arcId,
  selectedBranchId,
  onSelect,
}: {
  arcId: string;
  selectedBranchId: string | null;
  onSelect: (branchId: string) => void;
}) {
  const { branches, error } = useBranches(arcId);

  if (error) {
    return (
      <p role="alert" className="text-sm text-rose-300">
        {error}
      </p>
    );
  }

  if (!branches) {
    return (
      <p role="status" className="text-sm text-stone-400">
        Loading branches…
      </p>
    );
  }

  if (branches.length === 0) {
    return <p className="text-sm text-stone-400">No branches yet.</p>;
  }

  return (
    <ul className="space-y-2">
      {branches.map((branch) => (
        <li key={branch.id}>
          <button
            type="button"
            aria-current={branch.id === selectedBranchId ? "true" : undefined}
            onClick={() => onSelect(branch.id)}
            className={`w-full rounded-lg border p-3 text-left ${
              branch.id === selectedBranchId
                ? "border-teal-300 bg-teal-950/20"
                : "border-stone-700"
            }`}
          >
            <span className="font-medium">{branch.name}</span>
            <span className="ml-2 text-xs text-stone-400">
              {branch.chapter_count} chapter{branch.chapter_count === 1 ? "" : "s"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
