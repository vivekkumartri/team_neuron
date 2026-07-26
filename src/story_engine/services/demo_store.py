"""Demo mode storage: a plain folder per story, a plain folder per chapter.

No database, no job tracking, no LLM calls. Just files on disk that the API
reads straight back. Layout::

    demo_data/
      story1/
        story.json          {"title": "...", "tagline": "...", "seed_prompt": "..."}
        ch1/
          chapter.json       {"title": "...", "text": "...", "storyboard": [...], "narration_asset": "narration.mp3"}
          scene_1.png         (referenced from chapter.json's storyboard[i].image_asset)
          narration.mp3
        ch2/
          chapter.json
          ...
      story2/
        story.json
        ch1/
          chapter.json

To add a demo story: make a folder under `demo_data/` (its name is the
story's id, e.g. `story1`), drop a `story.json` in it, and one `ch1/`,
`ch2/`, ... subfolder per chapter, each with a `chapter.json`. That's the
whole format. `scripts/export_demo_story.py` builds one of these for you
from a real generated branch; you can also hand-write one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DEMO_DATA_DIR = Path(__file__).resolve().parents[3] / "demo_data"

_ID_SAFE = re.compile(r"^[a-zA-Z0-9_-]+$")
_CHAPTER_FOLDER = re.compile(r"^ch(\d+)$")


class DemoStoryNotFoundError(RuntimeError):
    pass


class UnsafeDemoPathError(RuntimeError):
    """An id or asset name tried to escape `demo_data/` (`..`, absolute path, etc.)."""


def _validate_id(value: str) -> None:
    if not value or not _ID_SAFE.match(value):
        raise UnsafeDemoPathError(f"Invalid demo id: {value!r}")


def _story_dir(story_id: str) -> Path:
    _validate_id(story_id)
    return DEMO_DATA_DIR / story_id


def _chapter_dirs(story_dir: Path) -> list[tuple[int, Path]]:
    """Every `chN/` subfolder, sorted by chapter number N."""

    found: list[tuple[int, Path]] = []
    if not story_dir.is_dir():
        return found
    for entry in story_dir.iterdir():
        match = _CHAPTER_FOLDER.match(entry.name)
        if entry.is_dir() and match:
            found.append((int(match.group(1)), entry))
    return sorted(found, key=lambda pair: pair[0])


def list_demo_stories() -> list[dict]:
    if not DEMO_DATA_DIR.is_dir():
        return []
    summaries: list[dict] = []
    for entry in sorted(DEMO_DATA_DIR.iterdir()):
        story_json = entry / "story.json"
        if not entry.is_dir() or not story_json.is_file():
            continue
        story = json.loads(story_json.read_text(encoding="utf-8"))
        cover = story.get("cover_asset")
        summaries.append(
            {
                "id": entry.name,
                "title": str(story.get("title", entry.name)),
                "tagline": str(story.get("tagline", "")),
                "seed_prompt": str(story.get("seed_prompt", "")),
                "cover_asset_url": (
                    f"/api/v1/demo/assets/{entry.name}/{cover}" if cover else None
                ),
            }
        )
    return summaries


def load_demo_story(story_id: str) -> dict:
    story_dir = _story_dir(story_id)
    story_json = story_dir / "story.json"
    if not story_json.is_file():
        raise DemoStoryNotFoundError(story_id)
    story = json.loads(story_json.read_text(encoding="utf-8"))

    chapters: list[dict] = []
    for chapter_index, chapter_dir in _chapter_dirs(story_dir):
        chapter_json = chapter_dir / "chapter.json"
        if not chapter_json.is_file():
            continue
        chapter = json.loads(chapter_json.read_text(encoding="utf-8"))
        chapter["chapter_index"] = chapter_index
        folder = chapter_dir.name
        if chapter.get("narration_asset"):
            chapter["narration_asset_url"] = (
                f"/api/v1/demo/assets/{story_id}/{folder}/{chapter['narration_asset']}"
            )
        for scene in chapter.get("storyboard", []):
            if scene.get("image_asset"):
                scene["image_asset_url"] = (
                    f"/api/v1/demo/assets/{story_id}/{folder}/{scene['image_asset']}"
                )
        chapters.append(chapter)

    cover = story.get("cover_asset")
    return {
        "id": story_id,
        "title": str(story.get("title", story_id)),
        "tagline": str(story.get("tagline", "")),
        "seed_prompt": str(story.get("seed_prompt", "")),
        "language": str(story.get("language", "en")),
        "cover_asset_url": f"/api/v1/demo/assets/{story_id}/{cover}" if cover else None,
        "cast": story.get("cast", []),
        "chapters": chapters,
    }


def resolve_asset_path(story_id: str, asset_path: str) -> Path:
    """`asset_path` is either `cover.png` (story-level) or `ch1/scene_1.png` (chapter-level)."""

    story_dir = _story_dir(story_id).resolve()
    candidate = (story_dir / asset_path).resolve()
    if story_dir not in candidate.parents and candidate != story_dir:
        raise UnsafeDemoPathError(f"Invalid demo asset path: {asset_path!r}")
    return candidate
