#!/usr/bin/env python3
"""Flag deploy settings in a repository that have caused PolicyEngine cost incidents.

Reads files only; changes nothing and calls no cloud API.

    python3 check_deploy_config.py [REPO_DIR] [--strict]

Exit status: 0 when there are no errors, 1 when there are errors (warnings also
count with --strict), 2 for bad input.

A line opts out of one rule with a reason on that line or the line above:
    # cost-ok: <rule id> <why this is intended, and until when>
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCANNED_SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".toml", ".json", ".tf", ".bash", ""}
SKIPPED_DIRECTORIES = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "__pycache__"}
SECRET_NAME = r"[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|WEBHOOK)[A-Z0-9_]*"


@dataclass
class Finding:
    rule: str
    severity: str
    path: Path
    line: int
    message: str


def opted_out(lines: list[str], index: int, rule: str) -> bool:
    nearby = lines[index] + (lines[index - 1] if index > 0 else "")
    return re.search(rf"cost-ok:\s*{rule}\b", nearby) is not None


def logical_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Join shell continuation lines (ending in a backslash), keeping the first line's index."""
    joined: list[tuple[int, str]] = []
    start, parts = 0, []
    for index, line in enumerate(lines):
        if not parts:
            start = index
        parts.append(line.rstrip("\\").rstrip())
        if not line.rstrip().endswith("\\"):
            joined.append((start, " ".join(parts)))
            parts = []
    if parts:
        joined.append((start, " ".join(parts)))
    return joined


def is_test_file(path: Path) -> bool:
    return any(part in {"tests", "test", "__tests__"} for part in path.parts[:-1]) or path.name.startswith(
        "test_"
    ) or path.name.endswith(("_test.py", ".test.ts", ".test.js"))


def first_line(lines: list[str], pattern: str) -> int | None:
    for index, line in enumerate(lines):
        if re.search(pattern, line):
            return index
    return None


def check_file(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()

    def add(rule: str, severity: str, index: int, message: str) -> None:
        if not opted_out(lines, index, rule):
            findings.append(Finding(rule, severity, path, index + 1, message))

    # CR1: a revision-level Cloud Run minimum on revisions that also get a traffic tag.
    # Cloud Run keeps every tagged revision started, so each deploy leaves its own warm
    # instance behind (simulation API Dec 2025, uk-budget-api-2026 Oct 2026).
    revision_minimum = first_line(lines, r"--min-instances[= ]+[\"']?[1-9]")
    tagged = first_line(lines, r"--tag[= ]|--tag$|\btag:\s|--update-tags|--set-tags")
    if revision_minimum is not None and tagged is not None:
        add("CR1", "error", revision_minimum,
            "revision-level --min-instances >= 1 in a file that also tags revisions: every tagged "
            "revision keeps its own warm instance. Use service-level --min N with --min-instances 0.")

    compares_before_adding = re.search(r"secrets\s+versions\s+access\b", text) is not None
    for index, line in logical_lines(lines):
        # MO1: Modal containers kept warm in code (literal values; a variable is left to review).
        match = re.search(r"\b(min_containers|keep_warm|buffer_containers)\s*=\s*([1-9][0-9]*|True)\b", line)
        if match and path.suffix == ".py":
            add("MO1", "error", index,
                f"Modal {match.group(1)}={match.group(2)} keeps containers running while idle. "
                "Default to 0; for a launch window use a Cron that calls update_autoscaler with a hard stop.")

        # CL1: a delete or stop whose failure is hidden, so a cleanup step can report success
        # while deleting nothing (Artifact Registry cleanup, Oct 2026).
        if re.search(r"\b(delete|untag|stop|destroy|remove-tags)\b", line) and re.search(
            r"(gcloud|modal|gsutil|bq)\b", line
        ) and re.search(r"2>\s*/dev/null|\|\|\s*true\b|>\s*/dev/null\s+2>&1|&>\s*/dev/null", line):
            add("CL1", "error", index,
                "cleanup command hides its errors (2>/dev/null or || true): a failed deletion is "
                "reported as success. Let it fail, or count and report failures.")

        # SE1: a secret written into plain environment variables (ri-ctc HF_TOKEN, 2025-26).
        if re.search(rf"--(?:set|update)-env-vars[= ][\"']?[^\n]*\b{SECRET_NAME}=", line):
            add("SE1", "error", index,
                "secret-like value passed with --set-env-vars/--update-env-vars is stored in plain "
                "text in every revision. Use --set-secrets with Secret Manager.")

        # SE2: a deploy that adds a secret version on every run (745 identical versions, 2026).
        if re.search(r"secrets\s+versions\s+add\b", line) and not compares_before_adding:
            add("SE2", "warning", index,
                "deploy adds a Secret Manager version; every stored version is billed. Add one only "
                "when the value differs from the latest version.")

    # CI1: a workflow that starts Modal work on pushes or pull requests and cancels older
    # runs. Cancelling the GitHub run does not refund containers already started.
    if path.suffix in {".yml", ".yaml"} and "/.github/workflows/" in f"/{path.as_posix()}":
        starts_modal = first_line(lines, r"\bmodal\s+(run|deploy)\b|--backend\s+modal|modal_[a-z_]+\.py")
        on_push = re.search(r"^\s*(push|pull_request)\s*:", text, re.M) or re.search(
            r"^on:\s*\[?[^\n]*\b(push|pull_request)\b", text, re.M
        )
        cancels = re.search(r"cancel-in-progress:\s*true", text)
        if starts_modal is not None and on_push and cancels:
            add("CI1", "warning", starts_modal,
                "Modal work starts on push/pull_request with cancel-in-progress: cancelled runs still "
                "pay for the containers they started. Trigger on a label or manual dispatch, or debounce.")

    # CR2: no maximum instance count in a Cloud Run deploy (the default allows 100).
    if re.search(r"gcloud\s+run\s+deploy\b", text) and not re.search(r"--max-instances|--max[= ]", text):
        index = first_line(lines, r"gcloud\s+run\s+deploy\b") or 0
        add("CR2", "warning", index,
            "gcloud run deploy without --max-instances or --max: the service can scale to the "
            "default limit. Set a cap from the observed peak.")
    return findings


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIPPED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix not in SCANNED_SUFFIXES and path.name != "Dockerfile":
            continue
        if path.suffix == "" and path.name != "Dockerfile" and not path.name.startswith("deploy"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if path.resolve() == Path(__file__).resolve() or is_test_file(path.relative_to(root)):
            continue
        findings.extend(check_file(path.relative_to(root), text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", default=".", help="repository directory to scan")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    arguments = parser.parse_args()
    root = Path(arguments.repo)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    findings = scan(root)
    for finding in findings:
        print(f"{finding.severity} {finding.rule} {finding.path}:{finding.line}: {finding.message}")
    errors = sum(finding.severity == "error" for finding in findings)
    warnings = len(findings) - errors
    print(f"{errors} errors, {warnings} warnings")
    return 1 if errors or (arguments.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
