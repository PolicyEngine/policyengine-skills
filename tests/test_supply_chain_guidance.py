from __future__ import annotations

import re
import subprocess
from pathlib import Path


UNPUBLISHED_DESIGN_TOKENS_INSTALL_RE = re.compile(
    r"\b(?:npm|pnpm|yarn|bun)\s+(?:install|add)\s+@policyengine/design-tokens\b"
)


def test_tracked_files_do_not_install_unpublished_design_tokens_package() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        check=True,
        cwd=repo_root,
        text=True,
        capture_output=True,
    ).stdout.splitlines()

    offenders: list[str] = []
    for relative_path in tracked_files:
        path = repo_root / relative_path
        text = path.read_text(errors="ignore")
        if UNPUBLISHED_DESIGN_TOKENS_INSTALL_RE.search(text):
            offenders.append(relative_path)

    assert offenders == []
