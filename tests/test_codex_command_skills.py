from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
COMMAND_SKILLS = {
    "encode-policy-v2": Path("skills/encode-policy-v2/SKILL.md"),
    "review-program": Path("skills/review-program/SKILL.md"),
    "fix-pr": Path("skills/fix-pr/SKILL.md"),
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


def parse_description(path: Path) -> str:
    match = FRONTMATTER_RE.match(path.read_text())
    assert match, f"{path} is missing YAML frontmatter"

    lines = match.group("body").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue

        _, _, value = line.partition(":")
        value = value.strip()

        if value in {"|", "|-", "|+", ">", ">-", ">+"}:
            collected: list[str] = []
            for continuation in lines[index + 1 :]:
                if continuation.startswith("  "):
                    collected.append(continuation.strip())
                    continue
                break
            separator = " " if value.startswith(">") else "\n"
            return separator.join(collected).strip()

        return value.strip("\"'")

    raise AssertionError(f"{path} is missing description")


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


def test_skill_descriptions_fit_codex_limit() -> None:
    repo_root = Path(__file__).resolve().parent.parent

    for skill_path in repo_root.glob("skills/**/SKILL.md"):
        description = parse_description(skill_path)
        assert len(description) <= 1024, (
            f"{skill_path.relative_to(repo_root)} description exceeds Codex limit"
        )


def assert_installer_replaces_stale_skill_directories(
    tmp_path: Path, script_name: str, home_var: str, home_dir_name: str
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    skill_home = tmp_path / home_dir_name
    stale_skill = skill_home / "skills" / "policyengine-canada"
    stale_skill.mkdir(parents=True)
    (stale_skill / "SKILL.md").write_text("---\nname: stale\n---\n")

    subprocess.run(
        [str(repo_root / "scripts" / script_name)],
        check=True,
        env={**os.environ, home_var: str(skill_home)},
    )

    installed = skill_home / "skills" / "policyengine-canada"
    assert installed.is_symlink()
    assert installed.resolve() == (
        repo_root / "skills" / "policyengine-canada"
    )


def test_install_codex_replaces_stale_skill_directories(tmp_path: Path) -> None:
    assert_installer_replaces_stale_skill_directories(
        tmp_path, "install_codex.sh", "CODEX_HOME", "codex"
    )


def test_install_claude_replaces_stale_skill_directories(tmp_path: Path) -> None:
    assert_installer_replaces_stale_skill_directories(
        tmp_path, "install_claude_skills.sh", "CLAUDE_HOME", "claude"
    )


def test_install_codex_repo_routing_preserves_existing_agents(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    repos_root = tmp_path / "repos"
    us_repo = repos_root / "policyengine-us"
    app_repo = repos_root / "policyengine-app-v2"
    us_repo.mkdir(parents=True)
    app_repo.mkdir(parents=True)
    (us_repo / "AGENTS.md").write_text("# Existing Guidance\n\nKeep this section.\n")

    subprocess.run(
        [str(repo_root / "scripts" / "install_codex_repo_routing.sh")],
        check=True,
        env={**os.environ, "CODEX_REPOS_ROOT": str(repos_root)},
    )

    us_agents = (us_repo / "AGENTS.md").read_text()
    app_agents = (app_repo / "AGENTS.md").read_text()

    assert "<!-- BEGIN POLICYENGINE CODEX ROUTING -->" in us_agents
    assert "$policyengine-us" in us_agents
    assert "# Existing Guidance" in us_agents
    assert "$policyengine-app" in app_agents
    assert "$policyengine-design" in app_agents


def test_install_codex_repo_routing_rejects_malformed_managed_block(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    repos_root = tmp_path / "repos"
    us_repo = repos_root / "policyengine-us"
    us_repo.mkdir(parents=True)
    original = (
        "<!-- BEGIN POLICYENGINE CODEX ROUTING -->\n"
        "old managed content without an end marker\n"
        "# Existing Guidance\n"
    )
    target = us_repo / "AGENTS.md"
    target.write_text(original)

    result = subprocess.run(
        [str(repo_root / "scripts" / "install_codex_repo_routing.sh")],
        check=False,
        env={**os.environ, "CODEX_REPOS_ROOT": str(repos_root)},
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "without matching" in result.stderr
    assert target.read_text() == original
