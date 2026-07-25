# Story Engine — Requirements Reconciliation

This appendix resolves differences among the original requirements draft, backend design, clickable prototype, current `requirements.md`, and `design.md`. `design.md` is the implementation authority; this file records why earlier artifacts differ.

| Area | Final disposition | Source decision |
| --- | --- | --- |
| Hidden-characteristic blurred hint | Removed. No genre can reveal or hint at an unrevealed characteristic. | Supersedes backend §6.1 and prototype Cast hidden row. |
| Short seed | No hard minimum. Below ~12 tokens, use a visible clarification loop. | Supersedes prototype `>=20` gate and stale requirements limit. |
| World Sandbox direct changes | Submit evaluator-reviewed canon-event requests with confirmation and pending state. | Supersedes prototype direct kill/revive handlers and earlier direct-write API shape. |
| Progression controls | Exactly Continue, Edit traits, and Jump/rewind; storyteller directions are advisory. | Supersedes prototype two-choice/custom-action interaction. |
| Character traits | Core identity locks at cast lock; mutable, inspectable trait state is versioned per branch/chapter. | Reconciles cast lock with trait-edit/rewind requirements. |
| Relationship graph | Read-only visualization; relationship edits use validated request dialogs. | Reconciles editable-family-tree requirement with read-only graph decision. |
| Templates | Original or confirmed-licensed templates only. Unlicensed known-IP inhabitation/source-scene jumping is deferred. | Satisfies IP guardrails. |
| Publication | Auto-publish after world/evaluator validation, with visible stream, immutable history, and branch/revision undo. | Reconciles auto-publish with no-silent-change principle. |
| Content policy | Safety, IP, distress, trait-spiral, privacy, and disclosure policy is MVP scope. | Supersedes the earlier “policy open” placeholder. |
| Monetization | Disclosed curation/sponsorship metadata is supported in the template model; commerce, paywalls, and shop links are deferred. | Prevents undisclosed placement/steering. |
| Comic/image/animated portraits | Deferred from the text-only MVP. | Later direct product decision. |
| User self-avatar / “insert yourself” | Deferred; `entities.is_user_avatar` is not included in the branch-scoped MVP schema. | Requires a separate privacy/persona design review. |
| Prototype Comic Studio | Visual reference only; its live regenerate/export controls are removed in favor of a non-operable **Coming later** state. | Text-only MVP decision. |

## Traceability Status

- Original FR/GR requirements are implemented by the tasks named in `task.md` §0.4, 2C.2, 2D.4, 3E.3–3E.4, 4H.2–4H.4, 5I.1, and 5J.1.
- Deferred work remains visible in `design.md` §Deferred MVP Boundaries and must not be silently added to MVP scope.
- Any future change to a reconciled decision must update this file, `design.md`, and the relevant task acceptance criteria in the same pull request.
