"""Regression test that every archived analysis has the required frontmatter.

Prevents schema drift as the pipeline evolves.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_manifest import parse_frontmatter  # noqa: E402

ANALYSES_DIR = ROOT / "analyses"

REQUIRED_FIELDS = {
    "policy_id",
    "date",
    "title",
    "jurisdiction",
    "verdict",
    "tags",
}

VALID_VERDICTS = {
    "PASS",
    "PASS-WITH-NOTES",
    "PASS-WITH-CORROBORATION",
    "INVESTIGATE",
    "BLOCKED",
    "structural",
    "not-possible",
    "deployed-model-lag",
}


def _analyses_files() -> list[Path]:
    return [p for p in sorted(ANALYSES_DIR.glob("*.md")) if p.name.lower() != "readme.md"]


@pytest.mark.parametrize("path", _analyses_files(), ids=lambda p: p.name)
def test_analysis_has_required_fields(path: Path) -> None:
    meta, _ = parse_frontmatter(path.read_text())
    assert meta, f"{path.name} has no frontmatter"
    missing = REQUIRED_FIELDS - set(meta.keys())
    # `policy_id` may be None for structural runs; allow it if the field key exists
    assert not missing, f"{path.name} missing required fields: {missing}"


@pytest.mark.parametrize("path", _analyses_files(), ids=lambda p: p.name)
def test_analysis_verdict_is_recognized(path: Path) -> None:
    meta, _ = parse_frontmatter(path.read_text())
    verdict = meta.get("verdict")
    assert verdict in VALID_VERDICTS, (
        f"{path.name} has unrecognized verdict={verdict!r}; "
        f"add to VALID_VERDICTS or fix the archive"
    )


@pytest.mark.parametrize("path", _analyses_files(), ids=lambda p: p.name)
def test_analysis_reform_dict_is_valid_json_when_present(path: Path) -> None:
    """The CRM publication router forwards `reform_dict` verbatim into the
    bill-tracker's publish-reform workflow — a non-JSON value would fail
    silently downstream. Optional field: absent is fine (pre-July-2026
    archives, structural/not-possible runs)."""
    import json

    meta, _ = parse_frontmatter(path.read_text())
    reform_dict = meta.get("reform_dict")
    if reform_dict is None:
        return
    assert isinstance(reform_dict, str), f"{path.name} reform_dict must be a string block scalar"
    parsed = json.loads(reform_dict)
    assert isinstance(parsed, dict), f"{path.name} reform_dict must be a JSON object"


@pytest.mark.parametrize("path", _analyses_files(), ids=lambda p: p.name)
def test_analysis_jurisdiction_is_dict_with_country(path: Path) -> None:
    meta, _ = parse_frontmatter(path.read_text())
    j = meta.get("jurisdiction")
    assert isinstance(j, dict), f"{path.name} jurisdiction must be a nested dict"
    assert j.get("country") in ("us", "uk", "ca"), (
        f"{path.name} jurisdiction.country={j.get('country')!r} — must be us/uk/ca"
    )
