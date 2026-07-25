# Interactive Story Engine — Requirements Document

**Status:** Draft v1
**Owner:** Astik
**Last updated:** 2026-07-25

---

## 1. Overview

A platform that turns a user-provided story seed (new story, predefined story, dream fragment, or partial story) into an interactive, branching narrative experience. The system generates a character family tree with illustrated character cards, lets the user drive or edit the story chapter-by-chapter, and can export any chapter or full run as a comic.

### 1.1 Problem statement
Most AI story tools either (a) generate a static one-shot story with no user agency, or (b) allow chat-style freeform continuation with no structure, memory, or visual output. This product sits in between: structured character/world state, chapter-based pacing, explicit user control points, and a visual (comic) output artifact.

### 1.2 Goals
- Let a user go from a rough idea to a structured cast of characters in one pass.
- Give the user real narrative agency without requiring them to write prose themselves.
- Make every AI decision point (interpretation, trait changes, branching) reversible and confirmable — never silently committed.
- Produce a shareable visual artifact (comic) at the end of the process.

### 1.3 Non-goals (Phase 1)
- Not building a multiplayer/shared-authoring experience.
- Not supporting full-length novels — scope is chapter units (~30-second story beats).
- Not licensing or reproducing existing copyrighted film/book/show content (see Guardrails, §5.1).
- Not building voice/video output in Phase 1 — comic (static panel) export only.

---

## 2. Users & use cases

| Persona | Use case |
|---|---|
| Casual creative user | Turns a daydream or "what if" into a short illustrated story |
| Fan-fiction-style writer | Starts from a predefined story template and diverges from a specific scene |
| Worldbuilder | Iterates on a character family tree and explores "what if this trait were different" |
| Comic hobbyist | Uses the tool purely to get a shareable comic strip out of a short narrative beat |

---

## 3. Functional requirements — Phase 1 (end-to-end core loop)

### 3.1 Story input
- **FR-1.1**: User can submit input as one of: a new original story, a predefined/template story (selected from a library), a dream/fragment description, or a partial existing story excerpt.
- **FR-1.2**: Input can be short (a sentence) or long (multiple paragraphs). No minimum length enforced, but very short input (under a configurable token threshold) triggers the clarification flow (FR-1.3) rather than silent inference.
- **FR-1.3 — Input confirmation loop**:
  - System reflects back its interpretation of the input in plain language ("Sounds like a survival story set in space with two estranged siblings — is that right?").
  - System offers 2–4 concrete directional suggestions the user can pick from, or the user can type a free-text correction.
  - User must confirm (explicitly or by proceeding) before character generation begins.
  - This loop can repeat if the user keeps redirecting; there is no hard cap on rounds, but the UI should nudge toward convergence after ~3 rounds.

### 3.2 Character generation
- **FR-2.1**: System generates a **character family tree** capturing relationships (parent/child, sibling, rival, mentor, etc.) inferred from or consistent with the input.
- **FR-2.2**: For each character, generate a **character card** containing:
  - Name, role in story, personality traits, backstory summary, motivations
  - An animated portrait/avatar (short looping animation, not full video)
- **FR-2.3**: Character tree and cards must be editable post-generation (rename, add/remove a relationship, regenerate a single card without regenerating the whole tree).

### 3.3 Character selection
- **FR-3.1**: User selects one existing character from the tree to follow as the protagonist of the next chapter, **or**
- **FR-3.2**: User introduces a brand-new character (manually specified or LLM-assisted), which gets folded into the existing family tree with system-suggested relationships to existing characters.

### 3.4 Chapter loop (core loop, repeats)
- **FR-4.1**: System generates a **30-second story unit** ("chapter") centered on the active character, consistent with prior chapters and current character trait state.
- **FR-4.2**: After each chapter, user is presented exactly three path options:
  1. **Continue automatically** — AI extends the character's arc with no further input.
  2. **Edit traits** — before the next chapter generates. Two entry modes:
     - **LLM-suggested edits**: system proposes a small set of concrete trait-change options (e.g. "make her more reckless," "introduce a rivalry with X") that the user taps to accept.
     - **Freeform edits**: user directly specifies a change in their own words.
     - **Go with the flow**: user can decline both and keep current traits — this is the default if the user takes no action.
  3. **Jump / rewind** — user selects a previous scene (own line, from any chapter so far, or — for predefined stories — any scene in the source material) and continues from that point instead of the current end-of-timeline point. See §3.5 for branching semantics.
- **FR-4.3**: Trait edits and rewinds must be visibly reflected in the character card (updated trait list) before the next chapter generates, so the user can see what changed.

### 3.5 Branching & versioning
- **FR-5.1**: Every "jump/rewind" action creates a **new branch** from the selected point rather than destructively overwriting existing chapters. (Decision locked: branch-preserving, not overwrite-only — see rationale in §7.)
- **FR-5.2**: User can view a lightweight branch map/history and switch between branches.
- **FR-5.3**: For predefined stories specifically, the user can jump into **any scene in the original source structure**, not just previously-generated chapters, and diverge from there.

### 3.6 Ending
- **FR-6.1**: Once the story reaches a plausible closing point (system-detected, based on narrative pacing heuristics — not a fixed chapter count), the system presents **multiple distinct ending options** rather than auto-resolving to one ending.
- **FR-6.2**: User can also manually request "show me ending options now" at any point after a minimum number of chapters, without waiting for system detection.

### 3.7 Comic generation
- **FR-7.1**: Any single chapter can be converted into a **comic strip** (paneled visual layout) on demand.
- **FR-7.2**: User can compile a full branch's chapter sequence into one continuous comic export.
- **FR-7.3**: Comic export is a static image/PDF artifact — no animation — downloadable and shareable.

---

## 4. Phase 2 (future, not in initial build)

- **"Inhabit a known story" mode** (e.g. "put me inside 3 Idiots"): deferred pending IP/licensing review (§5.1). Likely implementation path is a **vibe/archetype descriptor** ("engineering college friendship story, strict father figure, quirky genius roommate") rather than direct use of licensed names, likenesses, or verbatim scenes.
- **Dream mode**: user describes a dream or abstract fragment; system builds an original world and cast around it. This is a variant of the existing input flow (§3.1) with a different input prompt framing — likely mergeable into one general "describe a world" input mode rather than a separate system.

---

## 5. Guardrails

### 5.1 Intellectual property / copyright
- **GR-1.1**: The system must not reproduce copyrighted dialogue, song lyrics, or verbatim text from existing films, books, or shows, even when the user names a specific work as inspiration.
- **GR-1.2**: The system must not generate content that uses a real, named, copyrighted character (e.g. a specific film character) as a playable entity unless the underlying IP is properly licensed. Until licensed, "inspired by" requests should be handled by generating **original characters with analogous archetypes**, not reproductions of the named characters.
- **GR-1.3**: Predefined story templates in the library must be either originally authored for this product or used under a confirmed license — never scraped or reproduced from copyrighted source material without rights.
- **GR-1.4**: Generated character art/animation must not imitate a specific recognizable celebrity, public figure, or a distinctive copyrighted visual character design.

### 5.2 Content safety
- **GR-2.1**: No generation of graphic violence, gore, sexual/suggestive content, or content that sexualizes or otherwise endangers minors, regardless of user framing (including "for a story," "fictional," or roleplay framings).
- **GR-2.2**: Age-appropriate defaults: if a user's input or ongoing story trends toward content unsuitable for general audiences, the system should redirect rather than escalate.
- **GR-2.3**: Character trait edits must be filtered — e.g. a trait-edit request that pushes a character toward glorified self-harm, hate speech, or extremist ideology should be declined with an in-story-appropriate alternative offered instead.
- **GR-2.4**: No real, identifiable private individuals may be used as characters without their consent (this includes "make a character based on my ex" type requests when identifying details make the person recognizable and the portrayal is disparaging or non-consensual).

### 5.3 User agency & transparency guardrails
- **GR-3.1**: No AI decision (input interpretation, trait change, branch point) should be silently committed — every generation step that materially changes the story must have a visible confirm/undo point. This is a hard product principle, not just a nice-to-have (ties to FR-1.3, FR-4.2, FR-4.3).
- **GR-3.2**: The system must never claim a generated ending or chapter is "the" canonical outcome if the source was a predefined/licensed story with an actual canonical ending — divergent user paths must be clearly labeled as **alternate/fan-generated**, not as official canon.
- **GR-3.3**: All character trait states must be inspectable at any time — no hidden trait modifiers the user can't see or query.

### 5.4 Data & privacy
- **GR-4.1**: If dream-mode input includes personal/sensitive details (real names, real relationships, real trauma), the system should treat this as sensitive user content: not used for model training/fine-tuning beyond the session without explicit consent, not surfaced in any shared/public template library.
- **GR-4.2**: User-generated stories and character data are private by default; any "publish to community library" action requires explicit opt-in per story, not a global account-level setting.
- **GR-4.3**: Comic exports should not embed hidden metadata identifying the user unless the user chooses to attribute themselves.

### 5.5 Wellbeing guardrails
- **GR-5.1**: If dream-mode or personal-story input surfaces signs of real distress (e.g. a "dream" that is actually describing a real traumatic event, grief, or self-harm ideation), the system should not treat this purely as creative material to dramatize — it should respond with appropriate care/redirection rather than generating an entertainment narrative around it.
- **GR-5.2**: The system should avoid reinforcing harmful trait spirals — e.g. if a user repeatedly edits a character toward self-destructive, abusive, or degrading traits chapter after chapter, the system can offer a gentle in-context nudge/alternate suggestion rather than mechanically complying every time.

### 5.6 System/output guardrails
- **GR-6.1**: Branch history must never silently delete a user's prior work — destructive actions (deleting a branch, overwriting a character permanently) require explicit confirmation.
- **GR-6.2**: Comic generation must degrade gracefully — if the model can't produce a coherent panel breakdown for a chapter, the system should say so rather than emit a broken/garbled comic.
- **GR-6.3**: Rate/quota limits (chapter generations, comic exports, image generations per session) should be explicit to the user, not silent failures.

---

## 6. Data model considerations (high-level, non-binding)

- **Story** → has one or more **branches** (tree structure, not a flat list)
- **Branch** → ordered sequence of **chapters**; each chapter references the character trait state *at the time it was generated* (immutable snapshot, not a live pointer) so that rewinding to an old chapter reflects that chapter's actual trait state
- **Character** → base identity (name, role) + **trait state history** (versioned, since traits can be edited chapter-to-chapter and across branches)
- **Family tree** → relationship graph between characters, versioned similarly to traits since new characters can be added mid-story
- **Comic export** → derived artifact referencing a specific chapter or branch range; not a source of truth, always regenerable from the underlying chapter data

---

## 7. Key decisions already locked

| Decision | Resolution |
|---|---|
| Branch model on rewind | **Branch-preserving** (new branch created), not destructive overwrite — preserves user's prior work and matches the "go back and make changes" requirement literally |
| Trait edit default | If user takes no action, character traits stay as-is ("go with the flow") — editing is opt-in, never forced |
| Input clarification | Always shown for short/ambiguous input; user must confirm before character generation starts |
| Phase 2 "inhabit a known story" | Deferred; likely solved via vibe/archetype description rather than direct licensed-IP use, pending legal review |

---

## 8. Monetization & business model

### 8.1 Guiding principle
Monetization and business-driven content steering are permitted, but only in **disclosed** forms. The test for any monetization mechanic: *the user should always be able to tell a preference or promotion is being applied to them, and could opt out if they noticed.* Anything that only works because the user doesn't notice it is out of scope (see GR-3.1, GR-3.2).

### 8.2 Genre weighting & curation
- **MON-1.1 — Weighted defaults, disclosed at onboarding**: the system can default to promoting certain genres (e.g. adventure, mystery) for business reasons, but this must be stated to the user (e.g. in the input-confirmation flow, FR-1.3) with a visible way to change it. Not a silent bias.
- **MON-1.2 — Template curation**: the business can editorially curate which predefined story templates are featured/promoted (homepage carousel, "trending genres this month") based on business goals. This is standard editorial/merchandising choice, not manipulation, since the full library remains equally accessible.
- **MON-1.3 — Weighted suggestions in the confirmation loop**: LLM-generated directional suggestions (FR-1.3) may be weighted toward business-preferred genres, provided they are still presented and labeled as suggestions the user can freely reject or redirect away from.
- **MON-1.4 — A/B testing on suggestion ordering/presentation**: permitted as standard product experimentation (which suggestions appear first, how they're framed) as long as the user's ability to choose differently is never removed or obscured.

### 8.3 Sponsored & branded content
- **MON-2.1 — Disclosed sponsored chapters/characters**: a brand may sponsor a chapter, character wardrobe/prop, or full predefined story template, but it must be clearly labeled as sponsored/branded content, consistent with advertising disclosure norms (e.g. FTC/ASA-style disclosure).
- **MON-2.2 — "Shop the scene"**: if a scene features a described object/outfit/setting, the system may offer an optional, clearly-labeled link to a similar real product. This must be user-initiated (a tap/click to see the product), never auto-inserted into the narrative text itself.
- **MON-2.3 — Sponsored template library entries**: brands may pay to have an officially-labeled template in the predefined-story library (e.g. "Presented by [Brand]"), positioned alongside organic templates, not disguised as one.

### 8.4 Explicitly out of scope
- **MON-3.1**: No covert product placement embedded in organically-generated user stories without disclosure.
- **MON-3.2**: No genre or ideological steering designed specifically to bypass the user's conscious awareness ("subliminal" framing) — if a mechanic's effectiveness depends on the user not noticing it, it is not permitted.
- **MON-3.3**: No dynamic pricing or paywall gating disguised as narrative content (e.g. an ending withheld and framed as a "twist" purely to force payment, without being labeled as a paywall).

---

## 9. Open questions

1. Comic export: per-chapter only in MVP, or must full-branch compilation ship in Phase 1?
2. Animated portraits: short looping animation vs. static image with subtle parallax — what's the actual visual fidelity target and rendering cost budget?
3. What's the system's heuristic for "story has reached a plausible ending point" — fixed chapter count as a floor, pacing model, or explicit user-only trigger in MVP (simplest, defer automatic detection to later)?
4. Predefined story library: sourced from originally-authored templates only, or is there a licensing path being pursued for known IP integration later?
5. Session/quota limits — chapters, images, and comic exports per user per day — need actual numbers before build.

---

## 10. Success metrics (draft)

- % of sessions that reach at least one full chapter loop iteration (input → chapter → user decision)
- % of sessions that produce a comic export (indicates the loop delivered a shareable artifact)
- Branch usage rate (are users actually rewinding/diverging, or mostly going linear?)
- Trait-edit acceptance rate for LLM-suggested edits vs. freeform edits (signal on suggestion quality)
