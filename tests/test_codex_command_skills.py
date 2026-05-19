from __future__ import annotations

import re
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
COMMAND_SKILLS = {
    "encode-policy-v2": Path("skills/workflows/encode-policy-v2-skill/SKILL.md"),
    "review-program": Path("skills/workflows/review-program-skill/SKILL.md"),
    "fix-pr": Path("skills/workflows/fix-pr-skill/SKILL.md"),
}


def parse_frontmatter(path: Path) -> dict[str, str]:
    match = FRONTMATTER_RE.match(path.read_text())
    assert match, f"{path} is missing YAML frontmatter"

    fields: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in match.group("body").splitlines():
        if line.startswith("  ") and current_key:
            current_lines.append(line.strip())
            continue

        if current_key:
            fields[current_key] = " ".join(current_lines).strip()
            current_key = None
            current_lines = []

        key, _, value = line.partition(":")
        value = value.strip()
        if value == "|":
            current_key = key
            current_lines = []
        else:
            fields[key] = value.strip("\"'")

    if current_key:
        fields[current_key] = " ".join(current_lines).strip()

    return fields


def test_codex_command_skills_exist_with_expected_names() -> None:
    repo_root = Path(__file__).resolve().parent.parent

    for expected_name, relative_path in COMMAND_SKILLS.items():
        fields = parse_frontmatter(repo_root / relative_path)
        assert fields["name"] == expected_name
        assert fields["description"]


def test_codex_command_skill_bodies_avoid_claude_command_tokens() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    disallowed = ("$ARGUMENTS", "TeamCreate", "TaskCreate", "AskUserQuestion", "subagent_type")

    for relative_path in COMMAND_SKILLS.values():
        text = (repo_root / relative_path).read_text()
        for token in disallowed:
            assert token not in text, f"{relative_path} contains Claude-only token {token}"


def test_review_program_skill_mentions_codex_review() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    path = repo_root / COMMAND_SKILLS["review-program"]
    text = path.read_text()
    fields = parse_frontmatter(path)

    assert "/review" in fields["description"]
    assert "Phase 6 consolidation is required" in text
