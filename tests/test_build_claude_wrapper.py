from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_claude_wrapper(tmp_path: Path) -> None:
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

    manifest_path = output_dir / ".claude-plugin" / "marketplace.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["name"] == "policyengine-claude"
    assert len(manifest["plugins"]) == 9

    assert (output_dir / "skills" / "domain-knowledge" / "policyengine-us-skill" / "SKILL.md").exists()
    assert (output_dir / "commands" / "create-pr.md").exists()
    assert (output_dir / "agents" / "api" / "api-reviewer.md").exists()
    assert (output_dir / "hooks" / "hooks.json").exists()
    assert (output_dir / "GENERATED_FROM").read_text().strip() == "test-sha"
