#!/usr/bin/env python3
"""Flag deploy settings in a tool's repository that have caused PolicyEngine cost incidents.

Reads files only; changes nothing and calls no cloud API.

    python3 check_deploy_config.py [REPO_DIR] [--strict]

Exit status: 0 when there are no errors, 1 when there are errors (warnings also
count with --strict), 2 for bad input.

A setting that differs from the defaults on purpose is declared on its line, the line
above, or in the comment block directly above, with a reason and, for anything
temporary, an end date:
    min_containers=2,  # cost-ok: MO1 launch-day traffic needs no cold start; until 2026-11-30
The declaration silences that one rule there. A declaration with no reason (or one starting
TODO), or whose date has passed, does not count: the rule reports as usual and says why.
Every accepted declaration is printed, so reviewers see each exception.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SCANNED_SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".toml", ".json", ".tf", ".bash", ""}
SKIPPED_DIRECTORIES = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "__pycache__"}
SECRET_NAME = r"[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|WEBHOOK)[A-Z0-9_]*"
RULES = {"CR1", "CR2", "CR3", "MO1", "MO2", "RS1", "CL1", "SE1", "SE2", "SE3", "CI1"}
# Reservations at or above these need a measured reason (RS1).
LARGE_CPU = 4
LARGE_MEMORY_MIB = 16 * 1024


@dataclass
class Finding:
    rule: str
    severity: str
    path: Path
    line: int
    message: str


@dataclass
class Declaration:
    rule: str
    path: Path
    line: int
    reason: str
    until: date | None


def find_declaration(lines: list[str], index: int, rule: str) -> tuple[int, str] | None:
    """Return (line index, text after the rule ID) of a cost-ok declaration for this rule."""
    candidates = [index, index - 1]
    above = index - 2
    while above >= 0 and is_comment(lines[above + 1]) and is_comment(lines[above]):
        candidates.append(above)
        above -= 1
    for candidate in candidates:
        if candidate < 0:
            continue
        match = re.search(rf"cost-ok:\s*{rule}\b(.*)$", lines[candidate])
        if match:
            return candidate, match.group(1)
    return None


def parse_declaration(text: str) -> tuple[str, date | None, str | None]:
    """Split a declaration into (reason, end date, problem)."""
    until = None
    until_match = re.search(r"\buntil\s+(\d{4}-\d{2}-\d{2})\b", text)
    if until_match:
        try:
            until = date.fromisoformat(until_match.group(1))
        except ValueError:
            return "", None, f"end date {until_match.group(1)} is not a real date"
        text = text[: until_match.start()] + text[until_match.end() :]
    reason = text.strip(" \t:;,.-—")
    if not reason or reason.upper().startswith("TODO"):
        return reason, until, "it gives no reason"
    return reason, until, None


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


def is_comment(line: str) -> bool:
    return line.lstrip().startswith(("#", "//"))


def first_line(lines: list[str], pattern: str) -> int | None:
    for index, line in enumerate(lines):
        if not is_comment(line) and re.search(pattern, line):
            return index
    return None


def mebibytes(number: str, unit: str) -> float:
    factors = {"": 1, "Mi": 1, "M": 1e6 / 1024**2, "Gi": 1024, "G": 1e9 / 1024**2, "Ti": 1024**2}
    return float(number) * factors.get(unit, 1)


def modal_decorators(lines: list[str]) -> list[tuple[int, str]]:
    """Return (line index, full text) of each @<app>.function / @<app>.cls decorator."""
    decorators = []
    for index, line in enumerate(lines):
        if not re.match(r"\s*@\w+\.(function|cls)\b", line):
            continue
        text, depth, cursor = "", 0, index
        while cursor < len(lines):
            text += lines[cursor] + "\n"
            depth += lines[cursor].count("(") - lines[cursor].count(")")
            if depth <= 0:
                break
            cursor += 1
        decorators.append((index, text))
    return decorators


def check_file(path: Path, text: str, today: date | None = None, ignores_gha_creds: bool = False) -> tuple[list[Finding], list[Declaration]]:
    today = today or date.today()
    findings: list[Finding] = []
    declarations: list[Declaration] = []
    lines = text.splitlines()

    def add(rule: str, severity: str, index: int, message: str) -> None:
        declared = find_declaration(lines, index, rule)
        if declared is None:
            findings.append(Finding(rule, severity, path, index + 1, message))
            return
        declared_index, declared_text = declared
        reason, until, problem = parse_declaration(declared_text)
        if problem:
            findings.append(Finding(rule, severity, path, declared_index + 1,
                                    f"cost-ok declaration for {rule} is not accepted: {problem}. "
                                    f"Write why the setting is needed. ({message})"))
        elif until and until < today:
            findings.append(Finding(rule, severity, path, declared_index + 1,
                                    f"declared exception for {rule} ended on {until.isoformat()}: remove "
                                    f"the setting, or give a new reason and date. ({message})"))
        else:
            declarations.append(Declaration(rule, path, declared_index + 1, reason, until))

    is_modal_python = path.suffix == ".py" and re.search(r"^\s*(import modal|from modal\b)", text, re.M)

    # CR1: a revision-level Cloud Run minimum on revisions that also get a traffic tag.
    # Cloud Run keeps every tagged revision started, so each deploy leaves its own warm
    # instance behind (simulation API Dec 2025, uk-budget-api-2026 Oct 2026).
    revision_minimum = first_line(lines, r"--min-instances[= ]+[\"']?[1-9]")
    tagged = first_line(lines, r"--tag[= ]|--tag$|\btag:\s|--update-tags|--set-tags")
    cr1_applies = revision_minimum is not None and tagged is not None
    if cr1_applies:
        add("CR1", "error", revision_minimum,
            "revision-level --min-instances >= 1 in a file that also tags revisions: every tagged "
            "revision keeps its own warm instance. Use service-level --min N with --min-instances 0.")

    compares_before_adding = re.search(r"secrets\s+versions\s+access\b", text) is not None
    for index, line in logical_lines(lines):
        if is_comment(line):
            continue
        # CR3: any non-zero Cloud Run minimum: instances billed while nobody uses the tool.
        minimum = re.search(r"--min(?:-instances)?[= ]+[\"']?([1-9][0-9]*)\b", line) or re.search(
            r"\b(?:minScale|min_instance_count)[\"']?\s*[:=]\s*[\"']?([1-9][0-9]*)\b", line)
        if minimum and not (cr1_applies and "--min-instances" in line):
            add("CR3", "error", index,
                f"Cloud Run minimum of {minimum.group(1)} keeps instances billed while idle. Default to 0; "
                "if the tool needs it, declare it with a reason and an end date.")

        # MO1: Modal containers kept warm in code (literal values; a variable is left to review).
        match = re.search(r"\b(min_containers|keep_warm|buffer_containers)\s*=\s*([1-9][0-9]*|True)\b", line)
        if match and path.suffix == ".py":
            add("MO1", "error", index,
                f"Modal {match.group(1)}={match.group(2)} keeps containers running while idle. "
                "Default to 0; for a launch window use a Cron that calls update_autoscaler with a hard stop.")

        # RS1: a large CPU or memory reservation. Modal bills the higher of reserved and used.
        if is_modal_python:
            cpu = re.search(r"\bcpu\s*=\s*([0-9]+(?:\.[0-9]+)?)\b", line)
            memory = re.search(r"\bmemory\s*=\s*([0-9]+)(?:\s*\*\s*([0-9]+))?\b", line)
            if cpu and float(cpu.group(1)) >= LARGE_CPU:
                add("RS1", "warning", index,
                    f"Modal cpu={cpu.group(1)} reserves {cpu.group(1)} cores; Modal bills the higher of "
                    "reserved and used. Size from a measured run and declare the measurement.")
            if memory and int(memory.group(1)) * int(memory.group(2) or 1) >= LARGE_MEMORY_MIB:
                mib = int(memory.group(1)) * int(memory.group(2) or 1)
                add("RS1", "warning", index,
                    f"Modal memory={mib} MiB; Modal bills the higher of reserved and used. Size from a "
                    "measured peak and declare it.")
        cloud_run_cpu = re.search(r"--cpu[= ]+[\"']?([0-9]+(?:\.[0-9]+)?)(m?)\b", line)
        cloud_run_memory = re.search(r"--memory[= ]+[\"']?([0-9]+(?:\.[0-9]+)?)(Mi|M|Gi|G|Ti)?\b", line)
        if cloud_run_cpu and float(cloud_run_cpu.group(1)) / (1000 if cloud_run_cpu.group(2) else 1) >= LARGE_CPU:
            add("RS1", "warning", index,
                f"Cloud Run --cpu {cloud_run_cpu.group(1)}: size from a measured run and declare the measurement.")
        if cloud_run_memory and mebibytes(cloud_run_memory.group(1), cloud_run_memory.group(2) or "") >= LARGE_MEMORY_MIB:
            add("RS1", "warning", index,
                f"Cloud Run --memory {cloud_run_memory.group(1)}{cloud_run_memory.group(2) or ''}: size from a "
                "measured peak and declare it.")

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

    # MO2: a Modal function with no max_containers, so nothing in the tool limits a burst.
    if is_modal_python:
        for index, decorator in modal_decorators(lines):
            if "max_containers" not in decorator and "schedule=" not in decorator:
                add("MO2", "warning", index,
                    "Modal function without max_containers: set the most containers the tool may run "
                    "at once, so its worst hour has a known price.")

    if path.suffix in {".yml", ".yaml"} and "/.github/workflows/" in f"/{path.as_posix()}":
        # CI1: a workflow that starts Modal work on pushes or pull requests and cancels older
        # runs. Cancelling the GitHub run does not refund containers already started.
        starts_modal = first_line(lines, r"\bmodal\s+(run|deploy)\b|--backend\s+modal|modal_[a-z_]+\.py")
        on_push = re.search(r"^\s*(push|pull_request)\s*:", text, re.M) or re.search(
            r"^on:\s*\[?[^\n]*\b(push|pull_request)\b", text, re.M
        )
        cancels = re.search(r"cancel-in-progress:\s*true", text)
        if starts_modal is not None and on_push and cancels:
            add("CI1", "warning", starts_modal,
                "Modal work starts on push/pull_request with cancel-in-progress: cancelled runs still "
                "pay for the containers they started. Trigger on a label or manual dispatch, or debounce.")

        # SE3: a JSON key written into the workspace by google-github-actions/auth, then a
        # commit of everything (a PolicyEngine repo committed its key this way, Jul 2026).
        json_key = first_line(lines, r"credentials_json\s*:")
        commits_everything = re.search(
            r"git\s+add\s+(-A|--all|\.(\s|$))|git\s+commit\s+(?:[^\n]*\s)?(--all\b|-[a-zA-Z]*a[a-zA-Z]*\b)"
            r"|EndBug/add-and-commit|stefanzweifel/git-auto-commit-action", text, re.M)
        skips_file = re.search(r"create_credentials_file\s*:\s*false", text)
        if json_key is not None and commits_everything and not skips_file and not ignores_gha_creds:
            add("SE3", "error", json_key,
                "google-github-actions/auth writes the JSON key to gha-creds-*.json in the workspace, "
                "and this workflow commits everything. Add gha-creds-*.json to .gitignore, or use "
                "workload identity federation.")

    # CR2: no maximum instance count in a Cloud Run deploy (the default allows 100).
    if re.search(r"gcloud\s+run\s+deploy\b", text) and not re.search(r"--max-instances|--max[= ]", text):
        index = first_line(lines, r"gcloud\s+run\s+deploy\b") or 0
        add("CR2", "warning", index,
            "gcloud run deploy without --max-instances or --max: the service can scale to the "
            "default limit. Set a cap from the observed peak.")

    for index, line in enumerate(lines):
        for named in re.findall(r"cost-ok:\s*([A-Za-z0-9]*)", line):
            if named not in RULES:
                findings.append(Finding("??", "warning", path, index + 1,
                                        f"cost-ok must start with a rule ID ({', '.join(sorted(RULES))}), "
                                        f"not {named or 'nothing'}"))
    return findings, declarations


def scan(root: Path, today: date | None = None) -> tuple[list[Finding], list[Declaration]]:
    findings: list[Finding] = []
    declarations: list[Declaration] = []
    gitignore = root / ".gitignore"
    ignores_gha_creds = gitignore.is_file() and "gha-creds" in gitignore.read_text(encoding="utf-8", errors="replace")
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
        file_findings, file_declarations = check_file(path.relative_to(root), text, today, ignores_gha_creds)
        findings.extend(file_findings)
        declarations.extend(file_declarations)
    return findings, declarations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", default=".", help="repository directory to scan")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    arguments = parser.parse_args()
    root = Path(arguments.repo)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    findings, declarations = scan(root)
    for finding in findings:
        print(f"{finding.severity} {finding.rule} {finding.path}:{finding.line}: {finding.message}")
    for declaration in declarations:
        until = f" (until {declaration.until.isoformat()})" if declaration.until else ""
        print(f"declared {declaration.rule} {declaration.path}:{declaration.line}: {declaration.reason}{until}")
    errors = sum(finding.severity == "error" for finding in findings)
    warnings = len(findings) - errors
    print(f"{errors} errors, {warnings} warnings, {len(declarations)} declared exceptions")
    return 1 if errors or (arguments.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
