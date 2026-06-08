from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


UNPUBLISHED_DESIGN_TOKENS_PACKAGE = "@policyengine/" "design-tokens"
UNPUBLISHED_DESIGN_TOKENS_INSTALL_RE = re.compile(
    rf"\b(?:npm|pnpm|yarn|bun)\s+(?:i|install|add)\b[^\n`]*"
    rf"{re.escape(UNPUBLISHED_DESIGN_TOKENS_PACKAGE)}(?=$|[\s`'\";),@])"
)


def find_unpublished_design_tokens_install_offenders(paths: list[Path]) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        text = path.read_text(errors="ignore")
        if UNPUBLISHED_DESIGN_TOKENS_INSTALL_RE.search(text):
            offenders.append(str(path))

    return offenders


def tracked_files(repo_root: Path) -> list[Path]:
    relative_paths = subprocess.run(
        ["git", "ls-files"],
        check=True,
        cwd=repo_root,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    return [repo_root / relative_path for relative_path in relative_paths]


def test_unpublished_design_tokens_regex_catches_registry_installs() -> None:
    unsafe_commands = [
        f"npm install {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
        f"npm i {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
        f"npm install --save {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
        f"bun add -d {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
        f"pnpm add --workspace {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
        f"bun add react {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
        f"yarn add {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}@latest",
    ]

    for command in unsafe_commands:
        assert UNPUBLISHED_DESIGN_TOKENS_INSTALL_RE.search(command), command


def test_unpublished_design_tokens_regex_allows_local_paths() -> None:
    safe_commands = [
        "bun add ./path/to/design-tokens",
        "npm install ../policyengine-app-v2/design-tokens",
        f"npm install {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}-extra",
        f"rg {UNPUBLISHED_DESIGN_TOKENS_PACKAGE}",
    ]

    for command in safe_commands:
        assert not UNPUBLISHED_DESIGN_TOKENS_INSTALL_RE.search(command), command


def test_tracked_files_do_not_install_unpublished_design_tokens_package() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    offenders = find_unpublished_design_tokens_install_offenders(tracked_files(repo_root))

    assert offenders == []


def test_generated_claude_wrapper_does_not_install_unpublished_design_tokens_package(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = tmp_path / "policyengine-claude"

    subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "build_claude_wrapper.py"),
            "--source-root",
            str(repo_root),
            "--output-root",
            str(output_dir),
            "--source-sha",
            "test-sha",
        ],
        check=True,
    )

    generated_files = [path for path in output_dir.rglob("*") if path.is_file()]
    offenders = find_unpublished_design_tokens_install_offenders(generated_files)

    assert offenders == []
