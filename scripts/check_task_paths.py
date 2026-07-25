"""Fail CI if parallel tracks in the same task phase claim the same exact target path."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

TRACK_RE = re.compile(r"^### Track ([A-Z])")
PHASE_RE = re.compile(r"^## Phase (\d+)")
TARGET_RE = re.compile(r"^  - \*\*Target Files:\*\* (.+)$")
CODE_RE = re.compile(r"`([^`]+)`")


def main() -> int:
    task_path = Path(__file__).resolve().parents[1] / "task.md"
    phase = ""
    track = ""
    owners: dict[tuple[str, str], set[str]] = defaultdict(set)

    for line in task_path.read_text(encoding="utf-8").splitlines():
        if match := PHASE_RE.match(line):
            phase = match.group(1)
            track = ""
            continue
        if match := TRACK_RE.match(line):
            track = match.group(1)
            continue
        if match := TARGET_RE.match(line):
            if not phase or not track:
                continue
            for path in CODE_RE.findall(match.group(1)):
                if path.endswith("/") or "all Phase" in path:
                    continue
                owners[(phase, path)].add(track)

    collisions = {
        (phase, path): sorted(tracks)
        for (phase, path), tracks in owners.items()
        if len(tracks) > 1
    }
    if collisions:
        for (phase, path), tracks in sorted(collisions.items()):
            print(f"Phase {phase} collision: {path} is claimed by tracks {', '.join(tracks)}")
        return 1

    print("No exact target-file collisions across parallel tracks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
