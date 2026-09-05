"""Exercise report consistency and the period ambiguity observed in real PR reviews."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review-program/scripts"
SPEC = importlib.util.spec_from_file_location(
    "review_diagnostics", SCRIPTS / "review_diagnostics.py"
)
DIAGNOSTICS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAGNOSTICS)


@pytest.fixture
def review(tmp_path):
    report = tmp_path / "code.md"
    report.write_text("""# Role report

## C1 — Eligibility error

The observed benefit is 0; the source-supported result is 100.

### Reproduction

```python
## This is code, not a new finding
assert benefit == 100
```

## A1 — Boundary coverage

Add the exact threshold case.

## Validation

Two tests passed.
""")
    source = tmp_path / "source.html"
    source.write_text("Official rule")
    manifest = {
        "version": 1,
        "worktree_root": str(tmp_path),
        "sources": [
            {
                "url": "https://agency.example/rule",
                "path": str(source),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ],
    }
    (tmp_path / "sources.json").write_text(json.dumps(manifest))
    data = {
        "version": 1,
        "metadata": {
            "repository": "PolicyEngine/test",
            "pr_number": 7,
            "head": "a" * 40,
            "merge_base": "b" * 40,
            "mode": "full",
            "scope": "changed behavior and affected dependencies",
            "worktree_root": str(tmp_path),
        },
        "status": "COMPLETE",
        "roles": [{"path": "code.md", "status": "DONE"}],
        "source_manifest": "sources.json",
        "findings": [
            {
                "id": "C1",
                "severity": "critical",
                "path": "code.md",
                "heading": "C1 — Eligibility error",
            }
        ],
        "gaps": [],
        "validation": "Two tests passed; CI NOT RUN. One source.",
        "timing": {"elapsed_seconds": 5.2},
    }
    return tmp_path, data


def assemble(review, prefix="pr-7"):
    root, data = review
    input_path = root / "assembly.json"
    input_path.write_text(json.dumps(data))
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "assemble_review.py"),
            "--input",
            str(input_path),
            "--run-root",
            str(root),
            "--prefix",
            prefix,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_filename_prefix_keeps_spaces_and_single_dots(review):
    root, _ = review
    assert assemble(review, "pr 7.v2").returncode == 0
    assert (root / "pr 7.v2-review-summary.md").is_file()


def test_preserves_finding_and_derives_both_reports(review):
    root, _ = review
    result = assemble(review)
    assert result.returncode == 0, result.stderr
    full = (root / "pr-7-review-full-report.md").read_text()
    summary = (root / "pr-7-review-summary.md").read_text()
    assert "### Reproduction\n\n```python\n## This is code" in full
    assert "Boundary coverage" not in full
    for text in (full, summary):
        assert "REQUEST_CHANGES" in text
        assert "1 critical" in text
    assert "https://agency.example/rule" in full


@pytest.mark.parametrize("state", ["RESOLVED", "WITHDRAWN"])
def test_closed_findings_visible_but_not_open(review, state):
    root, data = review
    data["findings"][0]["status"] = state
    assert assemble(review).returncode == 0
    result = json.loads((root / "pr-7-review-result.json").read_text())
    assert result["counts"]["critical"] == 0
    assert result["severity"] == "APPROVE"
    assert f"({state})" in (root / "pr-7-review-full-report.md").read_text()


@pytest.mark.parametrize("cause", ["gap", "role", "unverified"])
def test_missing_checks_cannot_become_clean_approval(review, cause):
    root, data = review
    if cause == "gap":
        data["findings"] = []
        data["gaps"] = ["2026 amount could not be verified"]
    elif cause == "role":
        data["findings"] = []
        data["roles"][0]["status"] = "PARTIAL"
    else:
        data["findings"][0]["status"] = "UNVERIFIED"
    assert assemble(review).returncode == 0
    result = json.loads((root / "pr-7-review-result.json").read_text())
    assert result["status"] == "PARTIAL"
    assert result["severity"] == "COMMENT"
    assert result["gaps"]


@pytest.mark.parametrize(
    "invalid", ["duplicate", "missing_heading", "running", "stale_source", "outside"]
)
def test_bad_assembly_preserves_existing_outputs(review, invalid):
    root, data = review
    full = root / "pr-7-review-full-report.md"
    full.write_text("Prior report to preserve")
    if invalid == "duplicate":
        data["findings"] *= 2
    elif invalid == "missing_heading":
        data["findings"][0]["heading"] = "Absent finding"
    elif invalid == "running":
        data["roles"][0]["status"] = "RUNNING"
    elif invalid == "stale_source":
        (root / "source.html").write_text("Different bytes")
    else:
        data["roles"][0]["path"] = "../outside.md"
    assert assemble(review).returncode != 0
    assert full.read_text() == "Prior report to preserve"
    assert not (root / "pr-7-review-summary.md").exists()


def test_monthly_annual_total_differs_from_monthly_value():
    variable = SimpleNamespace(definition_period="month", value_type=float)
    total = DIAGNOSTICS.normalize_inputs(
        {"2026": {"annual_total": 2238}}, variable, "2026"
    )
    monthly = DIAGNOSTICS.normalize_inputs(
        {"2026": {"monthly_value": 2238}}, variable, "2026"
    )
    assert len(total) == len(monthly) == 12
    assert total["2026-01"] == 186.5
    assert sum(total.values()) == 2238
    assert monthly["2026-12"] == 2238


def test_ambiguous_monthly_input_and_overlap_are_rejected():
    variable = SimpleNamespace(definition_period="month", value_type=float)
    with pytest.raises(ValueError, match="explicit months"):
        DIAGNOSTICS.normalize_inputs(2238, variable, "2026")
    with pytest.raises(ValueError, match="Overlapping"):
        DIAGNOSTICS.normalize_inputs(
            {"2026": {"annual_total": 2238}, "2026-01": 100}, variable, "2026"
        )
    uneven = {"2026-01": 100, "2026-02": 0}
    assert DIAGNOSTICS.normalize_inputs(uneven, variable, "2026") == uneven


def test_does_not_divide_flags_or_guess_annual_values_from_months():
    with pytest.raises(ValueError, match="float variable"):
        DIAGNOSTICS.normalize_inputs(
            {"2026": {"annual_total": True}},
            SimpleNamespace(definition_period="month", value_type=bool),
            "2026",
        )
    with pytest.raises(ValueError, match="does not match"):
        DIAGNOSTICS.normalize_inputs(
            {"2026-01": 40},
            SimpleNamespace(definition_period="year", value_type=int),
            "2026",
        )


def test_normalization_preserves_entity_membership_and_checks_variable_entity():
    person = SimpleNamespace(plural="people", roles=None)
    household = SimpleNamespace(
        plural="households", roles=[SimpleNamespace(key="member", plural="members")]
    )
    system = SimpleNamespace(
        entities=[person, household],
        variables={
            "age": SimpleNamespace(
                entity=person, definition_period="year", value_type=int
            ),
            "state_code": SimpleNamespace(
                entity=household, definition_period="year", value_type=str
            ),
        },
    )
    situation = {
        "people": {"p": {"age": 40}},
        "households": {"h": {"members": ["p"], "state_code": "MO"}},
    }
    result = DIAGNOSTICS.normalize_situation(situation, system, "2026")
    assert result["households"]["h"]["members"] == ["p"]
    assert result["people"]["p"]["age"] == {"2026": 40}
    assert situation["people"]["p"]["age"] == 40
    situation["people"]["p"]["state_code"] = "MO"
    with pytest.raises(ValueError, match="belongs to households"):
        DIAGNOSTICS.normalize_situation(situation, system, "2026")
