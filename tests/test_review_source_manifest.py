"""Evidence reuse must preserve provenance and reject stale bytes independently."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/review-program/scripts/check_source_manifest.py"
)
SPEC = importlib.util.spec_from_file_location("check_source_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def evidence(tmp_path):
    worktree = tmp_path / "worktree"
    run = tmp_path / "run"
    worktree.mkdir()
    run.mkdir()

    def record(name, content):
        path = run / name
        path.write_bytes(content)
        return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}

    original = record("manual.html", b"original bytes, version one")
    text = record("manual.txt", b"Extracted source text")
    render = {**record("page-8.png", b"render bytes"), "page": 8, "dpi": 300}
    text["source_sha256"] = original["sha256"]
    render["source_sha256"] = original["sha256"]
    source = {
        **original,
        "url": "https://agency.example/manual",
        "text": text,
        "renders": [render],
    }
    data = {"version": 1, "worktree_root": str(worktree), "sources": [source]}
    manifest = run / "sources.json"
    manifest.write_text(json.dumps(data))
    return worktree, run, manifest, data


def inspect(evidence):
    worktree, run, manifest, _ = evidence
    return MODULE.check_manifest(manifest, worktree, run)


def test_reuses_valid_original_and_only_recorded_pages_without_writes(evidence):
    before = {p: p.read_bytes() for p in evidence[1].iterdir()}
    result = inspect(evidence)
    assert result["sources"] == evidence[3]["sources"]
    assert not result["rejected"] and not result["discarded_derivatives"]
    assert {p: p.read_bytes() for p in evidence[1].iterdir()} == before


def test_missing_extract_keeps_original_and_render(evidence):
    source = evidence[3]["sources"][0]
    Path(source["text"]["path"]).unlink()
    result = inspect(evidence)
    assert result["sources"][0]["sha256"] == source["sha256"]
    assert len(result["discarded_derivatives"]) == 1
    assert not result["rejected"]
    assert "text" not in result["sources"][0]
    assert result["sources"][0]["renders"] == source["renders"]


def test_changed_original_invalidates_all_its_cached_evidence(evidence):
    Path(evidence[3]["sources"][0]["path"]).write_bytes(b"modified bytes")
    result = inspect(evidence)
    assert result["sources"] == []
    assert "SHA-256 mismatch" in result["rejected"][0]["reason"]


def test_registering_new_original_does_not_revalidate_old_derivatives(evidence):
    source = evidence[3]["sources"][0]
    Path(source["path"]).write_bytes(b"New original version")
    source["sha256"] = hashlib.sha256(b"New original version").hexdigest()
    evidence[2].write_text(json.dumps(evidence[3]))
    result = inspect(evidence)
    assert len(result["sources"]) == 1
    assert "text" not in result["sources"][0]
    assert not result["sources"][0].get("renders")
    assert len(result["discarded_derivatives"]) == 2


def test_rejects_another_worktrees_manifest(evidence, tmp_path):
    with pytest.raises(ValueError, match="different worktree"):
        MODULE.check_manifest(evidence[2], tmp_path / "another-worktree", evidence[1])


def test_does_not_follow_source_symlink_outside_evidence_roots(evidence, tmp_path):
    source = Path(evidence[3]["sources"][0]["path"])
    outside = tmp_path / "another-worktrees-source"
    source.rename(outside)
    source.symlink_to(outside)
    result = inspect(evidence)
    assert result["sources"] == []
    assert "outside" in result["rejected"][0]["reason"]
