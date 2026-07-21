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

    bundle_dir = repo_root / "bundles"
    expected_plugins = len(list(bundle_dir.glob("*.json")))
    assert len(manifest["plugins"]) == expected_plugins == 8

    for plugin in manifest["plugins"]:
        assert plugin.get("source") == "./", f"{plugin['name']} missing source=./"
        assert "hooks" not in plugin, (
            f"{plugin['name']} has a hooks entry; Claude Code rejects both hooks: null "
            "and file-path strings in marketplace entries - hooks/hooks.json at the "
            "plugin root is auto-loaded instead"
        )

    assert (output_dir / "skills" / "policyengine" / "SKILL.md").exists()
    assert (output_dir / "skills" / "policyengine-us" / "SKILL.md").exists()
    assert (output_dir / "commands" / "create-pr.md").exists()
    assert (output_dir / "agents" / "country-models" / "rules-engineer.md").exists()
    assert (output_dir / "hooks" / "hooks.json").exists()
    assert (output_dir / "GENERATED_FROM").read_text().strip() == "test-sha"


def test_bundle_versions_align_with_marketplace_template() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    template = json.loads(
        (repo_root / "targets" / "claude" / "marketplace.template.json").read_text()
    )
    expected = template["version"]

    for bundle_path in sorted((repo_root / "bundles").glob("*.json")):
        bundle = json.loads(bundle_path.read_text())
        assert bundle.get("version") == expected, (
            f"{bundle_path.name} version {bundle.get('version')} != template {expected}"
        )
