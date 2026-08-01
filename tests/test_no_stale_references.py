"""Anti-rot lint: patterns that killed the pre-rebuild catalog may not return.

Each entry pairs a regex with the reason it is banned. A line may opt out by
placing an HTML comment marker ``<!-- stale-ok -->`` on the line immediately
before it (for deliberate "this is the superseded thing" history notes).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (pattern, reason)
FORBIDDEN: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"hf://policyengine/policyengine-us-data"),
        "policyengine-us-data is archived; datasets resolve by name from the "
        "certified bundle (populace_us_2024 / populace_us_2024_acs_local)",
    ),
    (
        re.compile(r"(states|districts)/[A-Z]{2}(-\d+)?\.h5"),
        "per-state/district H5 files were removed; filter one national dataset "
        "by geography columns",
    ),
    (
        re.compile(r"@mantine/|Mantine"),
        "app-v2 has zero Mantine dependencies",
    ),
    (
        re.compile(r"USHouseholdInput|UKHouseholdInput|calculate_household_impact"),
        "deleted policyengine.py API; use pe.{us,uk}.calculate_household",
    ),
    (
        re.compile(r"changelog_entry\.yaml"),
        "deprecated changelog format; use towncrier fragments in changelog.d/",
    ),
    (
        re.compile(r"policyengine-app/src"),
        "policyengine-app (v1) is archived; use policyengine-app-v2 paths",
    ),
    (
        re.compile(r"\benhanced_cps_2024\b|\benhanced_frs_2023_24\b"),
        "superseded by Populace datasets (populace_us_2024 / populace_uk_2023); "
        "mark deliberate history notes with <!-- stale-ok -->",
    ),
    (
        re.compile(r"npm install @policyengine/design-system|design-system@"),
        "deprecated package; new work consumes @policyengine/ui-kit",
    ),
    (
        re.compile(r"(?<!uv )\bpip install\b"),
        "use uv pip install / uv run per repo standards",
    ),
    (
        re.compile(r"from policyengine_(us|uk) import [^\n]*\bMicrosimulation\b"),
        "direct country-package Microsimulation is deprecated for analysis "
        "(2026-08-01); use pe.{us,uk}.managed_microsimulation() from "
        "policyengine>=5.0.1 — deliberate deprecation notes take <!-- stale-ok -->",
    ),
]

SCAN_DIRS = ["skills", "targets", "docs", "bundles", "presets"]
SCAN_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".sh", ".html"}
STALE_OK = "<!-- stale-ok -->"


def iter_scan_files():
    for dirname in SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in SCAN_SUFFIXES:
                yield path


def test_no_stale_references() -> None:
    violations: list[str] = []
    for path in iter_scan_files():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, start=1):
            prev = lines[lineno - 2] if lineno >= 2 else ""
            if STALE_OK in prev or STALE_OK in line:
                continue
            for pattern, reason in FORBIDDEN:
                if pattern.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{lineno}: {pattern.pattern!r} — {reason}")
    assert not violations, "Stale references found:\n" + "\n".join(violations)
