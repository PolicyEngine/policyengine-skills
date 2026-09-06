"""Protect caller completion decisions and report preservation, not policy accuracy.

Real PR runs assess findings, input plausibility and runtime; see benchmark.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review-program/scripts"


@pytest.fixture
def review(tmp_path):
    report = tmp_path / "code.md"
    report.write_text("""# Role report

## C1 — Selected report section

Opaque reviewer text. This fixture makes no policy claim.

### Reproduction

```python
## This is code, not a new finding
print("preserve this text")
```

## A1 — Unselected report section

This section must not enter the consolidated finding.

## Validation

Model tests NOT RUN in this mechanical fixture.
""")
    manifest = {"version": 1, "worktree_root": str(tmp_path), "sources": []}
    (tmp_path / "sources.json").write_text(json.dumps(manifest))
    data = {
        "version": 1,
        "metadata": {
            "repository": "PolicyEngine/test",
            "pr_number": 7,
            "head": "a" * 40,
            "merge_base": "b" * 40,
            "mode": "full",
            "scope": "Report automation only; no policy review",
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
                "heading": "C1 — Selected report section",
            }
        ],
        "gaps": [],
        "validation": "Model tests and CI NOT RUN; no policy sources checked.",
        "timing": {"elapsed_seconds": 5.2},
    }
    return tmp_path, data


def assemble(review):
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
            "pr-7",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_preserves_finding_and_derives_both_reports(review):
    root, _ = review
    result = assemble(review)
    assert result.returncode == 0, result.stderr
    full = (root / "pr-7-review-full-report.md").read_text()
    summary = (root / "pr-7-review-summary.md").read_text()
    selected_body = (
        (root / "code.md")
        .read_text()
        .split("## C1 — Selected report section\n", 1)[1]
        .split("\n## A1 —", 1)[0]
        .strip()
    )
    assert selected_body in full
    assert "Unselected report section" not in full
    for text in (full, summary):
        assert "REQUEST_CHANGES" in text
        assert "1 critical" in text
    # These labels are the encode-policy-v2 handoff, not cosmetic line positions.
    assert "Review status: COMPLETE" in summary
    assert "Review severity: REQUEST_CHANGES" in summary
    assert "Still-open critical count: 1" in summary


def test_withdrawn_finding_does_not_keep_the_fix_loop_running(review):
    state = "WITHDRAWN"
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
    assert result["confirmed_critical_ids"] == []
    assert result["confirmed_critical_count"] == 0


def test_unfinished_role_cannot_replace_previous_review(review):
    root, data = review
    outputs = [root / "pr-7-review-full-report.md", root / "pr-7-review-summary.md"]
    for path in outputs:
        path.write_text("Prior completed review")
    data["roles"][0]["status"] = "RUNNING"
    assert assemble(review).returncode != 0
    assert all(path.read_text() == "Prior completed review" for path in outputs)


def test_carries_prior_ids_without_rewriting_and_allocates_new_ids(review):
    root, data = review
    prior = root / "prior.md"
    prior.write_text("## C9 — Prior finding (OPEN)\n\nOriginal evidence.\n")
    original_role = (root / "code.md").read_bytes()
    data["prior_reports"] = ["prior.md"]
    data["reserved_ids"] = ["C9", "C12"]  # C12 was withdrawn in the baseline.
    data["findings"][0].pop("id")
    data["findings"].append(
        {
            "id": "C9",
            "severity": "critical",
            "status": "UNVERIFIED",
            "path": "prior.md",
            "heading": "C9 — Prior finding (OPEN)",
            "addendum": "Required scenario premise remains unresolved.",
        }
    )
    assert assemble(review).returncode == 0
    result = json.loads((root / "pr-7-review-result.json").read_text())
    assert result["confirmed_critical_ids"] == ["C13"]
    assert result["counts"]["critical"] == 2
    assert result["status"] == "PARTIAL"
    assert (root / "code.md").read_bytes() == original_role
    assert prior.read_text() == "## C9 — Prior finding (OPEN)\n\nOriginal evidence.\n"
    full = (root / "pr-7-review-full-report.md").read_text()
    assert "C9 — Prior finding (UNVERIFIED)" in full
    assert "Required scenario premise remains unresolved." in full


def test_summary_stays_short_without_losing_full_report_evidence(review):
    root, data = review
    data["findings"] = []
    data["notes"] = ["Reused passing tests at reviewed head."]
    assert assemble(review).returncode == 0
    assert (
        json.loads((root / "pr-7-review-result.json").read_text())["status"]
        == "COMPLETE"
    )
    data["findings"] = [
        {
            "severity": "suggestion",
            "path": "code.md",
            "heading": "C1 — Selected report section",
        }
        for _ in range(30)
    ]
    data["gaps"] = [f"Required unresolved check {i}" for i in range(10)]
    data["validation"] = "Long validation log\n" * 100
    assert assemble(review).returncode == 0
    summary = (root / "pr-7-review-summary.md").read_text()
    full = (root / "pr-7-review-full-report.md").read_text()
    assert len(summary.splitlines()) <= 20
    assert "S30" in full and "Required unresolved check 9" in full
    assert data["validation"].strip() in full
