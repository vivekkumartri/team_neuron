from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from content.templates.validate_manifest import TemplateManifestError, validate_manifest


def test_repository_template_manifest_is_approved() -> None:
    validate_manifest(Path("content/template-manifest.csv"))


def test_manifest_rejects_missing_rights_metadata(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("template_id,title\nmissing,No metadata\n", encoding="utf-8")

    with pytest.raises(TemplateManifestError, match="required metadata columns"):
        validate_manifest(manifest)
