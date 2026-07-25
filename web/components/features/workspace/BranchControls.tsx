"use client";

/**
 * The exactly-three progression modes design.md requires: Continue
 * automatically, Edit traits, Jump/rewind. No mutation endpoint exists on
 * the backend for any of these yet (see task.md Task 4H.3 status note), so
 * these are wired to an `onSelect` callback the parent can no-op or stub —
 * the important constraint enforced here is that there are exactly three
 * options and none of them silently changes state on click alone.
 */
export type ProgressionMode = "continue" | "edit-traits" | "jump-rewind";

export function BranchControls({
  onSelect,
  disabled = false,
}: {
  onSelect: (mode: ProgressionMode) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-3" role="group" aria-label="Progression mode">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect("continue")}
        className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:opacity-40"
      >
        Continue automatically
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect("edit-traits")}
        className="rounded-lg border border-violet-300 px-4 py-3 text-violet-100 disabled:opacity-40"
      >
        Edit traits
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect("jump-rewind")}
        className="rounded-lg border border-teal-300 px-4 py-3 text-teal-100 disabled:opacity-40"
      >
        Jump / rewind
      </button>
    </div>
  );
}
