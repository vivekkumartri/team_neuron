"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "../../../lib/api-client";
import { TraitCard, type EntityTraitState } from "../workspace/TraitCard";

interface RelationshipRow {
  from_entity_id: string;
  to_entity_id: string;
  relationship_type: string;
}

interface BranchStateResponse {
  branch_id: string;
  entities: { entity_id: string; name: string; entity_type: string; state: Record<string, unknown> }[];
  relationships: RelationshipRow[];
}

/**
 * Read-only world view against `GET /branches/:id/state`. Entity/relationship
 * mutation happens only through canon-event requests
 * (`POST /branches/:id/canon-event-requests`, Task 4G.2) reviewed by the
 * world agent — this view never mutates state directly.
 */
export function WorldView({ branchId }: { branchId: string }) {
  const [state, setState] = useState<BranchStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<BranchStateResponse>(`/branches/${branchId}/state`)
      .then((data) => {
        if (!cancelled) setState(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load world state.");
      });
    return () => {
      cancelled = true;
    };
  }, [branchId]);

  if (error) {
    return (
      <p role="alert" className="text-sm text-rose-300">
        {error}
      </p>
    );
  }
  if (!state) {
    return (
      <p role="status" className="text-stone-400">
        Loading world state…
      </p>
    );
  }

  const entitiesById = new Map(state.entities.map((entity) => [entity.entity_id, entity.name]));
  const traitEntities: EntityTraitState[] = state.entities.map((entity) => ({
    entityId: entity.entity_id,
    name: entity.name,
    entityType: entity.entity_type,
    state: entity.state,
  }));

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Entities</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {traitEntities.map((entity) => (
            <TraitCard key={entity.entityId} entity={entity} />
          ))}
        </div>
      </section>
      <section aria-label="Relationships (read-only)">
        <h2 className="text-lg font-semibold">Relationships</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {state.relationships.map((rel, index) => (
            <li key={index} className="rounded-lg border border-stone-700 p-3">
              {entitiesById.get(rel.from_entity_id) ?? rel.from_entity_id}
              {" -> "}
              {entitiesById.get(rel.to_entity_id) ?? rel.to_entity_id}
              <span className="ml-2 text-stone-400">({rel.relationship_type})</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
