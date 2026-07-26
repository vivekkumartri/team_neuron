"""Freeze a real, already-generated branch into a "demo mode" bundle.

Demo mode (`GET /api/v1/demo/...`, see `services/demo_store.py`) replays
pre-generated content with no database and no LLM calls, so a live demo
never depends on OpenAI being reachable. This script is the other half:
run it once, against a branch you already generated normally (chapters
published, storyboards created), and it writes everything that branch
needs for replay — chapter text, storyboard panel images, and (optionally)
narration audio — into `demo_data/<demo-id>/`.

Usage::

    export DATABASE_URL="postgresql://story_engine:story_engine_dev@localhost:5432/story_engine"
    export OPENAI_API_KEY=sk-...        # only needed if you pass --narrate
    python3 scripts/export_demo_story.py \\
        --branch-id 09c6e29f-e91b-4e5c-ba4c-58696d6a4a3e \\
        --demo-id castaway-signal \\
        --title "The Castaway Signal" \\
        --tagline "A stranded crew decodes a message that isn't for them." \\
        --narrate

This connects directly with the app's own DB role (not through
`tenant_connection`/RLS) because it's an offline operator tool, not a
request on behalf of an end user — the same trust boundary as
`scripts/migrate.py` and `scripts/seed_storyboard_demo.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

DEMO_DATA_DIR = REPO_ROOT / "demo_data"


def _fetch_all(cursor: psycopg.Cursor[Any], sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    cursor.execute(sql, params)
    return cast(list[tuple[Any, ...]], cursor.fetchall())


def _branch_ancestor_chain(cursor: psycopg.Cursor[Any], branch_id: str) -> list[str]:
    """Every branch from `branch_id` up to the root, closest-first.

    A rewind creates a *new* branch, so a story's chapters can end up spread
    across several branches (e.g. chapters 1-2 on the original branch,
    chapter 3 on a branch forked after a rewind). A single `branch_id` only
    owns the chapters generated directly on it, so exporting "the whole
    story so far" from one leaf branch means walking `parent_branch_id`
    back to the root and collecting chapters from every branch in that
    chain, not just the leaf.
    """

    chain: list[str] = []
    current: str | None = branch_id
    seen: set[str] = set()
    while current is not None and current not in seen:
        seen.add(current)
        chain.append(current)
        cursor.execute("SELECT parent_branch_id FROM branches WHERE id = %s", (current,))
        row = cursor.fetchone()
        current = str(row[0]) if row is not None and row[0] is not None else None
    return chain


def export_branch(
    connection: psycopg.Connection[Any],
    *,
    branch_id: str,
    demo_id: str,
    title: str,
    tagline: str,
    seed_prompt: str,
    language: str,
    narrate: bool,
) -> None:
    # Plain folder-per-story, folder-per-chapter layout (services/demo_store.py):
    #   demo_data/<demo_id>/story.json
    #   demo_data/<demo_id>/ch1/chapter.json (+ any scene images / narration.mp3)
    #   demo_data/<demo_id>/ch2/chapter.json
    story_dir = DEMO_DATA_DIR / demo_id
    story_dir.mkdir(parents=True, exist_ok=True)

    with connection.cursor() as cursor:
        cursor.execute("SELECT story_id FROM branches WHERE id = %s", (branch_id,))
        row = cursor.fetchone()
        if row is None:
            raise SystemExit(f"Branch not found: {branch_id}")
        story_id = row[0]

        cast_rows = _fetch_all(
            cursor,
            "SELECT e.name, cm.role, e.visual_description FROM cast_members cm "
            "JOIN entities e ON e.id = cm.entity_id WHERE cm.story_id = %s "
            "ORDER BY cm.created_at",
            (story_id,),
        )
        cast_out = [
            {"name": str(name), "role": str(role or ""), "traits": str(traits or "")}
            for name, role, traits in cast_rows
        ]

        # Walk the branch's ancestor chain (leaf -> root) so chapters that
        # were generated before a rewind, on a parent branch, are included
        # too -- see `_branch_ancestor_chain`'s docstring.
        branch_chain = _branch_ancestor_chain(cursor, branch_id)
        # `chapters` has no `title` column (see `migrations/0003_...sql`) --
        # chapters are only ever identified by `chapter_index`. A synthetic
        # "Chapter N" title is generated below instead.
        all_rows = _fetch_all(
            cursor,
            "SELECT branch_id, id, chapter_index FROM chapters "
            "WHERE branch_id = ANY(%s) AND status = 'PUBLISHED' ORDER BY chapter_index",
            (branch_chain,),
        )
        # If the same chapter_index somehow exists on more than one branch
        # in the chain, prefer the one closest to the leaf (branch_chain is
        # already leaf-first).
        chain_rank = {bid: rank for rank, bid in enumerate(branch_chain)}
        by_index: dict[int, tuple[Any, Any, Any]] = {}
        for row_branch_id, chapter_id, chapter_index in all_rows:
            existing = by_index.get(chapter_index)
            if existing is None or chain_rank[str(row_branch_id)] < chain_rank.get(
                str(existing[2]), len(branch_chain)
            ):
                by_index[chapter_index] = (chapter_id, chapter_index, row_branch_id)
        chapter_rows = [
            (chapter_id, chapter_index)
            for chapter_id, chapter_index, _branch in sorted(
                by_index.values(), key=lambda item: item[1]
            )
        ]
        if not chapter_rows:
            raise SystemExit(
                f"No published chapters found on branch {branch_id} or its ancestors; "
                "nothing to export"
            )
        if len(branch_chain) > 1:
            print(
                f"Collected chapters from {len(branch_chain)} branch(es) in this story's "
                f"lineage: {', '.join(branch_chain)}"
            )

        chapter_count = 0
        for chapter_id, chapter_index in chapter_rows:
            chapter_dir = story_dir / f"ch{chapter_index}"
            chapter_dir.mkdir(exist_ok=True)

            scene_rows = _fetch_all(
                cursor,
                "SELECT id, summary FROM scenes WHERE chapter_id = %s ORDER BY scene_index",
                (chapter_id,),
            )
            text_parts: list[str] = []
            for scene_id, summary in scene_rows:
                text_parts.append(str(summary))
                dialogue_rows = _fetch_all(
                    cursor,
                    "SELECT e.name, d.line_text FROM dialogue d "
                    "LEFT JOIN entities e ON e.id = d.speaker_entity_id "
                    "WHERE d.scene_id = %s ORDER BY d.line_index",
                    (scene_id,),
                )
                for speaker_name, line_text in dialogue_rows:
                    prefix = f"{speaker_name}: " if speaker_name else ""
                    text_parts.append(f"{prefix}{line_text}")
            chapter_text = "\n\n".join(text_parts)

            narration_asset = None
            if narrate:
                narration_asset = _export_narration(chapter_text, chapter_dir)

            storyboard_out = _export_storyboard(cursor, chapter_id, chapter_dir)

            chapter_json = {
                "title": f"Chapter {chapter_index}",
                "text": chapter_text,
                "narration_asset": narration_asset,
                "storyboard": storyboard_out,
            }
            (chapter_dir / "chapter.json").write_text(
                json.dumps(chapter_json, indent=2), encoding="utf-8"
            )
            chapter_count += 1

    story_json = {
        "title": title,
        "tagline": tagline,
        "seed_prompt": seed_prompt,
        "language": language,
        "cast": cast_out,
    }
    (story_dir / "story.json").write_text(json.dumps(story_json, indent=2), encoding="utf-8")
    print(f"Wrote {story_dir} ({chapter_count} chapter(s) as ch1, ch2, ...)")


def _export_storyboard(
    cursor: psycopg.Cursor[Any], chapter_id: str, chapter_dir: Path
) -> list[dict[str, Any]]:
    cursor.execute(
        "SELECT id FROM storyboard_jobs WHERE chapter_id = %s AND status = 'SUCCEEDED'",
        (chapter_id,),
    )
    job_row = cursor.fetchone()
    if job_row is None:
        return []
    job_id = job_row[0]

    scene_rows = _fetch_all(
        cursor,
        "SELECT scene_index, panel_asset_id, location, action, emotion, "
        "source_line_start, source_line_end FROM storyboard_scenes "
        "WHERE job_id = %s AND status = 'SUCCEEDED' ORDER BY scene_index",
        (job_id,),
    )
    out: list[dict[str, Any]] = []
    for scene_index, panel_asset_id, location, action, emotion, line_start, line_end in scene_rows:
        image_asset = None
        if panel_asset_id is not None:
            cursor.execute(
                "SELECT mime_type, content FROM storyboard_assets WHERE id = %s",
                (panel_asset_id,),
            )
            asset_row = cursor.fetchone()
            if asset_row is not None:
                mime_type, content = asset_row
                ext = "png" if "png" in str(mime_type) else "jpg"
                image_asset = f"scene_{scene_index}.{ext}"
                (chapter_dir / image_asset).write_bytes(bytes(content))

        cursor.execute(
            "SELECT e.name, d.line_text FROM dialogue d "
            "LEFT JOIN entities e ON e.id = d.speaker_entity_id "
            "JOIN scenes sc ON sc.id = d.scene_id "
            "WHERE sc.chapter_id = %s ORDER BY d.line_index "
            "OFFSET %s LIMIT %s",
            (chapter_id, max(int(line_start) - 1, 0), int(line_end) - int(line_start) + 1),
        )
        dialogue = [
            {"speaker_name": str(name) if name else None, "line_text": str(text)}
            for name, text in cast(list[tuple[Any, ...]], cursor.fetchall())
        ]

        out.append(
            {
                "scene_number": int(scene_index),
                "location": str(location or ""),
                "action": str(action or ""),
                "emotion": str(emotion or ""),
                "image_asset": image_asset,
                "dialogue": dialogue,
            }
        )
    return out


def _export_narration(chapter_text: str, chapter_dir: Path) -> str | None:
    from story_engine.agents.voice_provider import OpenAIVoiceProvider
    from story_engine.api.settings import load_settings

    settings = load_settings()
    if not settings.llm_configured:
        print(f"  (skipping narration for {chapter_dir.name}: no OPENAI_API_KEY)")
        return None
    provider = OpenAIVoiceProvider(api_key=settings.openai_api_key or "")
    audio_bytes = provider.synthesize_speech(
        text=chapter_text[:4000],
        model=settings.openai_tts_model,
        voice=settings.narrator_voice,
    )
    filename = "narration.mp3"
    (chapter_dir / filename).write_bytes(audio_bytes)
    return filename


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--demo-id", required=True, help="URL-safe id, e.g. castaway-signal")
    parser.add_argument("--title", required=True)
    parser.add_argument("--tagline", default="")
    parser.add_argument("--seed-prompt", default="")
    parser.add_argument("--language", default="en")
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
        export_branch(
            connection,
            branch_id=args.branch_id,
            demo_id=args.demo_id,
            title=args.title,
            tagline=args.tagline,
            seed_prompt=args.seed_prompt,
            language=args.language,
            narrate=args.narrate,
        )


if __name__ == "__main__":
    main()
