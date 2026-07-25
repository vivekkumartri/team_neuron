"""Test-session bootstrap.

This sandbox's `python3` is 3.10, but the codebase uses `enum.StrEnum`
(stdlib since 3.11). Rather than rewrite every enum in the codebase, shim it
in from the `strenum` package (already a project dependency for this exact
reason) before any test module imports anything from `story_engine`. See
task.md Task 5J.1's note for the origin of this approach.
"""

from __future__ import annotations

import enum

if not hasattr(enum, "StrEnum"):
    import strenum

    enum.StrEnum = strenum.StrEnum  # type: ignore[attr-defined]
