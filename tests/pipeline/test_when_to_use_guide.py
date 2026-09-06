"""Regression test for docs/when-to-use.md.

Guarantees:
1. Every recommended-status command in the catalog is mentioned in the guide.
2. Every command mentioned in the guide still exists in the catalog.
3. The guide's "Skills to almost always load" section names skills that exist.

Runs against the built manifest so it catches catalog drift automatically.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

MANIFEST_PATH = ROOT / "dashboard" / "src" / "data" / "manifest.json"
GUIDE_PATH = ROOT / "docs" / "when-to-use.md"

# Commands intentionally excluded from the guide (e.g., niche utilities that
# don't fit the workflow model).
EXCLUDED_COMMANDS: set[str] = set()


def _guide_text() -> str:
    return GUIDE_PATH.read_text()


def _guide_body_before_gaps() -> str:
    """Return the guide text up to the '## Gaps identified' section.

    The gaps section names hypothetical candidate commands; we don't want to
    validate those against the current catalog.
    """
    text = _guide_text()
    marker = "## Gaps identified"
    idx = text.find(marker)
    return text[:idx] if idx > -1 else text


def _slash_commands_in_guide() -> set[str]:
    """Find `/command` references in the guide body (excluding the gaps section).

    Uses a negative-lookbehind to avoid matching path segments like
    `~/PolicyEngine/foo`.
    """
    text = _guide_body_before_gaps()
    return set(re.findall(r"(?<![/\w])/([a-z][a-z0-9-]{2,})", text))


def _all_recommended_commands() -> list[dict]:
    m = json.loads(MANIFEST_PATH.read_text())
    return [
        a for a in m["artifacts"]
        if a["kind"] == "command" and a["registry_status"] == "recommended"
    ]


def _all_command_ids() -> set[str]:
    m = json.loads(MANIFEST_PATH.read_text())
    return {a["id"] for a in m["artifacts"] if a["kind"] == "command"}


def _all_skill_ids() -> set[str]:
    m = json.loads(MANIFEST_PATH.read_text())
    return {a["id"] for a in m["artifacts"] if a["kind"] == "skill"}


def test_guide_exists() -> None:
    assert GUIDE_PATH.exists(), "docs/when-to-use.md must exist"


def test_every_recommended_command_is_mentioned() -> None:
    """If a command is `recommended` in the catalog, users should be able to
    find it in the guide."""
    guide_cmds = _slash_commands_in_guide()
    missing = []
    for cmd in _all_recommended_commands():
        if cmd["id"] in EXCLUDED_COMMANDS:
            continue
        if cmd["id"] not in guide_cmds:
            missing.append(cmd["id"])
    assert not missing, (
        f"Recommended commands missing from docs/when-to-use.md: {missing}. "
        f"Either add a row/paragraph to the guide or add them to EXCLUDED_COMMANDS "
        f"here (with a comment explaining why)."
    )


def test_no_broken_command_references() -> None:
    """Every /command reference in the guide must resolve to a real command."""
    guide_cmds = _slash_commands_in_guide()
    # Claude skills also expose slash commands; workflows need no duplicate command file.
    catalog_cmds = _all_command_ids() | _all_skill_ids()
    # Filter for slash-command-looking tokens we intended as commands. Some
    # /... references in the guide are paths (e.g., `/tmp/...`) or URL paths.
    KNOWN_NON_COMMAND_PREFIXES = {
        "tmp", "usr", "home", "us", "uk", "ca", "en",  # url or path noise
        "loop", "loops",  # loop is a plugin skill, not a command
        "code-review",  # provided by claude-code, not this plugin
        "compact", "clear", "help",  # claude-code built-ins
    }
    broken = []
    for c in guide_cmds:
        if c in KNOWN_NON_COMMAND_PREFIXES:
            continue
        if c not in catalog_cmds:
            broken.append(c)
    assert not broken, (
        f"Guide references /command that no longer exists in the catalog: {broken}. "
        f"Update the guide, or add to KNOWN_NON_COMMAND_PREFIXES in this test if "
        f"it's not intended as a slash command."
    )


def test_skills_section_references_real_skills() -> None:
    """Skills mentioned by name in the guide should resolve to real skill IDs.

    Restricts to the 'Skills to almost always load' and 'Skills for specific
    work' sections; ignores prose mentions elsewhere that may refer to repos
    or template syntax rather than skill IDs.
    """
    text = _guide_text()
    # Extract just the skills-focused sections.
    start = text.find("## Skills to almost always load")
    end = text.find("## Common workflows")
    if start == -1 or end == -1 or start >= end:
        return  # sections restructured; skip
    section = text[start:end]

    skills_in_section = set(re.findall(
        r"`(policyengine-[a-z0-9-]+|microdf|microimpute|microcalibrate|l0)`",
        section,
    ))
    catalog_skills = _all_skill_ids()
    braced = set(re.findall(r"`policyengine-\{([a-z,]+)\}`", section))
    for group in braced:
        for country in group.split(","):
            skills_in_section.add(f"policyengine-{country.strip()}")
    missing = [s for s in skills_in_section if s not in catalog_skills]
    assert not missing, (
        f"'Skills to load' sections mention skills that don't exist in the "
        f"catalog: {missing}. Either fix the guide or delete the entry."
    )
