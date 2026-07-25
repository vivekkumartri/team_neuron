"use client";

/**
 * Visible, versioned trait card for one entity's current branch state.
 *
 * Backed by `GET /branches/:id/state` (`src/story_engine/api/routes/world.py`),
 * which returns only current, published entity state — never a candidate or
 * hidden-characteristic row (design.md "Loophole and Integrity Guards").
 */
export interface EntityTraitState {
  entityId: string;
  name: string;
  entityType: string;
  state: Record<string, unknown>;
}

export function TraitCard({ entity }: { entity: EntityTraitState }) {
  const traitEntries = Object.entries(entity.state);
  return (
    <article className="rounded-lg border border-stone-700 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{entity.name}</h3>
        <span className="rounded-full border border-stone-600 px-2 py-0.5 text-xs uppercase text-stone-400">
          {entity.entityType}
        </span>
      </div>
      {traitEntries.length === 0 ? (
        <p className="mt-2 text-sm text-stone-400">No recorded traits yet.</p>
      ) : (
        <dl className="mt-3 space-y-1 text-sm">
          {traitEntries.map(([key, value]) => (
            <div key={key} className="flex justify-between gap-4">
              <dt className="text-stone-400">{key}</dt>
              <dd className="text-right text-stone-200">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}
