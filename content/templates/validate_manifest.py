"""Validate template rights metadata before a template enters the library."""

from __future__ import annotations

import csv
import json
from pathlib import Path

REQUIRED_COLUMNS = frozenset(
    {
        "template_id",
        "title",
        "content_path",
        "author",
        "rights_basis",
        "license_evidence",
        "approval_status",
        "source_attribution",
        "sponsorship_disclosure",
        "approved_scene_map",
    }
)
ALLOWED_RIGHTS = frozenset({"original", "licensed", "mock-licensed"})


class TemplateManifestError(ValueError):
    """A record cannot be included in the approved template library."""


def validate_manifest(manifest_path: Path) -> None:
    root = manifest_path.parent.parent
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_COLUMNS:
            raise TemplateManifestError("Manifest must have exactly the required metadata columns")
        rows = list(reader)

    if not rows:
        raise TemplateManifestError("Manifest must include at least one template")
    seen_ids: set[str] = set()
    for row in rows:
        _validate_record(row, root=root, seen_ids=seen_ids)


def _validate_record(row: dict[str, str], *, root: Path, seen_ids: set[str]) -> None:
    if any(not value.strip() for key, value in row.items() if key != "sponsorship_disclosure"):
        raise TemplateManifestError("All required template metadata must be present")
    template_id = row["template_id"]
    if template_id in seen_ids:
        raise TemplateManifestError(f"Duplicate template id: {template_id}")
    seen_ids.add(template_id)
    if row["rights_basis"] not in ALLOWED_RIGHTS:
        raise TemplateManifestError("rights_basis must be original, licensed, or mock-licensed")
    if row["approval_status"] != "approved":
        raise TemplateManifestError("Only approved templates may be deployed")
    for field in ("content_path", "license_evidence", "approved_scene_map"):
        path = root / row[field]
        if not path.is_file():
            raise TemplateManifestError(f"Missing {field}: {row[field]}")
    try:
        json.loads((root / row["approved_scene_map"]).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateManifestError("approved_scene_map must be valid JSON") from exc
    disclosure = row["sponsorship_disclosure"]
    if disclosure and "presented by" not in disclosure.casefold():
        raise TemplateManifestError("Sponsored template disclosure must begin with 'Presented by'")


if __name__ == "__main__":
    validate_manifest(Path("content/template-manifest.csv"))
