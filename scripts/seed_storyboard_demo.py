"""Seed two published chapters for local storyboard verification.

Usage:
    DATABASE_URL=... python scripts/seed_storyboard_demo.py

The first character has a tiny uploaded reference image; the second has no
reference so the storyboard worker must create one during Chapter 1. Chapter 2
reuses both characters and is the consistency check.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
from uuid import UUID

import psycopg

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _id(cursor: psycopg.Cursor[object]) -> UUID:
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Seed insert did not return an id")
    return UUID(str(row[0]))


def seed(database_url: str) -> tuple[UUID, UUID, UUID, UUID]:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT app_provision_user(%s, %s)",
                ("storyboard-demo-user", "storyboard-demo@example.com"),
            )
            user_id = _id(cursor)
            cursor.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
            cursor.execute(
                "INSERT INTO stories (user_id, title, scenario, personalization_enabled, "
                "agent_trace_enabled, language) "
                "VALUES (%s, %s, %s, false, false, 'en') RETURNING id",
                (
                    user_id,
                    "The Lighthouse Signal",
                    "Two investigators discover why a lighthouse went dark before dawn.",
                ),
            )
            story_id = _id(cursor)
            cursor.execute(
                "INSERT INTO arcs (story_id, name) VALUES (%s, 'Main arc') RETURNING id",
                (story_id,),
            )
            arc_id = _id(cursor)
            cursor.execute(
                "INSERT INTO branches (story_id, arc_id, name, status) "
                "VALUES (%s, %s, 'Main timeline', 'ACTIVE') RETURNING id",
                (story_id, arc_id),
            )
            branch_id = _id(cursor)

            entities: list[tuple[UUID, str]] = []
            for name, background, visual in (
                (
                    "Mira",
                    "A lighthouse keeper who knows every signal pattern by heart.",
                    "short dark hair, navy coat, brass lantern",
                ),
                (
                    "Arun",
                    "A radio engineer who is brave but distrustful of silence.",
                    "curly hair, green field jacket, old radio headset",
                ),
            ):
                cursor.execute(
                    "INSERT INTO entities (story_id, name, entity_type, founding_branch_id, "
                    "background_story, visual_description) "
                    "VALUES (%s, %s, 'character', %s, %s, %s) RETURNING id",
                    (story_id, name, branch_id, background, visual),
                )
                entities.append((_id(cursor), name))
            for index, (entity_id, _) in enumerate(entities):
                cursor.execute(
                    "INSERT INTO cast_members (story_id, entity_id, role) VALUES (%s, %s, %s)",
                    (story_id, entity_id, "PROTAGONIST" if index == 0 else "SUPPORTING"),
                )

            cursor.execute(
                "INSERT INTO storyboard_assets (story_id, asset_kind, mime_type, content, sha256) "
                "VALUES (%s, 'CHARACTER_REFERENCE', 'image/png', %s, %s) RETURNING id",
                (story_id, _ONE_PIXEL_PNG, hashlib.sha256(_ONE_PIXEL_PNG).hexdigest()),
            )
            uploaded_asset_id = _id(cursor)
            cursor.execute(
                "INSERT INTO character_visual_references "
                "(story_id, entity_id, asset_id, source, version) "
                "VALUES (%s, %s, %s, 'UPLOADED', 1)",
                (story_id, entities[0][0], uploaded_asset_id),
            )

            chapter_ids: list[UUID] = []
            chapters = (
                (
                    1,
                    (
                        (entities[0][0], "The light went dark at midnight."),
                        (entities[1][0], "Then someone wanted the ships unseen."),
                        (entities[0][0], "We should inspect the tower."),
                        (entities[1][0], "Wait. I heard something upstairs."),
                    ),
                ),
                (
                    2,
                    (
                        (entities[1][0], "The radio is receiving a second signal."),
                        (entities[0][0], "Then the tower is not empty."),
                    ),
                ),
            )
            for chapter_index, dialogue in chapters:
                cursor.execute(
                    "INSERT INTO chapters "
                    "(branch_id, chapter_index, focal_character_id, status, published_at) "
                    "VALUES (%s, %s, %s, 'PUBLISHED', now()) RETURNING id",
                    (branch_id, chapter_index, entities[0][0]),
                )
                chapter_id = _id(cursor)
                chapter_ids.append(chapter_id)
                cursor.execute(
                    "INSERT INTO scenes (chapter_id, scene_index, summary) "
                    "VALUES (%s, 1, %s) RETURNING id",
                    (chapter_id, "\n".join(text for _, text in dialogue)),
                )
                scene_id = _id(cursor)
                for line_index, (speaker_id, text) in enumerate(dialogue, start=1):
                    cursor.execute(
                        "INSERT INTO dialogue (scene_id, line_index, speaker_entity_id, line_text) "
                        "VALUES (%s, %s, %s, %s)",
                        (scene_id, line_index, speaker_id, text),
                    )
                for choice_index, mode in enumerate(("CONTINUE", "EDIT_TRAITS", "REWIND"), start=1):
                    cursor.execute(
                        "INSERT INTO choices (chapter_id, choice_index, label, progression_mode) "
                        "VALUES (%s, %s, %s, %s)",
                        (chapter_id, choice_index, mode.replace("_", " ").title(), mode),
                    )
        connection.commit()
    return story_id, branch_id, chapter_ids[0], chapter_ids[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL must be supplied")
    story_id, branch_id, chapter_one, chapter_two = seed(args.database_url)
    print(f"story_id={story_id}")
    print(f"branch_id={branch_id}")
    print(f"chapter_1_id={chapter_one}")
    print(f"chapter_2_id={chapter_two}")


if __name__ == "__main__":
    main()
