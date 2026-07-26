"""Walk the whole database and export every story's chapters into demo_data/.

Single-branch/single-story export is `export_demo_story.py`. This is the
"just get everything I've generated so far into the demo folder" version:
it finds every story in Postgres, picks the furthest-progressed branch for
each one (so rewinds are handled the same way `export_demo_story.py`
already handles them -- see `_branch_ancestor_chain` in that module, reused
here), and exports it under `demo_data/<slug>/ch1`, `ch2`, `ch3`, `ch4`, ...

Usage::

    export DATABASE_URL="postgresql://story_engine:story_engine_dev@localhost:5432/story_engine"
    python3 scripts/export_all_demo_stories.py
    # or, to also synthesize narration audio per chapter (costs OpenAI TTS calls):
    export OPENAI_API_KEY=sk-...
    python3 scripts/export_all_demo_stories.py --narrate

Each story becomes its own folder; a story with no published chapters is
skipped (nothing to export) rather than failing the whole run.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from scripts.export_demo_story import export_branch  # noqa: E402

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, fallback: str) -> str:
    slug = _SLUG_SAFE.sub("-", text.lower()).strip("-")
    return slug or fallback


def _furthest_branch_per_story(
    connection: psycopg.Connection[Any],
) -> list[tuple[str, str, str]]:
    """One (story_id, scenario, leaf_branch_id) per story with any published chapter.

    "Furthest-progressed branch" = the branch holding the highest
    `chapter_index` among that story's branches. Starting the ancestor-chain
    walk (in `export_branch`) from there picks up every earlier chapter too,
    including ones left behind on a parent branch after a rewind -- the
    same logic `export_demo_story.py` already uses for one story at a time.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT s.id, s.scenario, c.branch_id, c.chapter_index "
            "FROM stories s "
            "JOIN branches b ON b.story_id = s.id "
            "JOIN chapters c ON c.branch_id = b.id AND c.status = 'PUBLISHED'"
        )
        rows = cast(list[tuple[Any, ...]], cursor.fetchall())

    best: dict[str, tuple[str, str, int]] = {}
    for story_id, scenario, branch_id, chapter_index in rows:
        story_id, branch_id = str(story_id), str(branch_id)
        current = best.get(story_id)
        if current is None or chapter_index > current[2]:
            best[story_id] = (str(scenario or ""), branch_id, chapter_index)

    return [(story_id, scenario, branch_id) for story_id, (scenario, branch_id, _) in best.items()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--narrate",
        action="store_true",
        help="Also synthesize narration audio per chapter (costs OpenAI TTS calls)",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be set")

    with psycopg.connect(database_url) as connection:
        stories = _furthest_branch_per_story(connection)
        if not stories:
            print("No published chapters found anywhere in the database.")
            return

        used_ids: set[str] = set()
        for story_id, scenario, branch_id in stories:
            base_slug = _slugify(scenario[:40], f"story-{story_id[:8]}")
            demo_id = base_slug
            suffix = 2
            while demo_id in used_ids:
                demo_id = f"{base_slug}-{suffix}"
                suffix += 1
            used_ids.add(demo_id)

            title = scenario[:80].strip() or f"Story {story_id[:8]}"
            print(f"\n--- Exporting story {story_id} (branch {branch_id}) -> demo_data/{demo_id}/ ---")
            try:
                export_branch(
                    connection,
                    branch_id=branch_id,
                    demo_id=demo_id,
                    title=title,
                    tagline="",
                    seed_prompt=scenario,
                    language="en",
                    narrate=args.narrate,
                )
            except SystemExit as error:
                print(f"  skipped: {error}")


if __name__ == "__main__":
    main()
