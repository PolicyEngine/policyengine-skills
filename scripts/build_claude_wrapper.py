#!/usr/bin/env python3
"""Build the generated PolicyEngine Claude wrapper from the source repo."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_bundles(source_root: Path) -> list[dict]:
    bundle_dir = source_root / "bundles"
    bundles: list[dict] = []
    for bundle_path in sorted(bundle_dir.glob("*.json")):
        bundle = load_json(bundle_path)
        validate_bundle(source_root, bundle_path, bundle)
        bundles.append(bundle)
    return bundles


def validate_bundle(source_root: Path, bundle_path: Path, bundle: dict) -> None:
    for key in ("skills", "commands", "agents"):
        for rel_path in bundle.get(key, []):
            source_path = resolve_source_path(source_root, rel_path)
            if not source_path.exists():
                raise FileNotFoundError(f"{bundle_path}: missing path {rel_path}")

    hooks = bundle.get("hooks")
    if hooks and not resolve_source_path(source_root, hooks).exists():
        raise FileNotFoundError(f"{bundle_path}: missing hooks path {hooks}")


def resolve_source_path(source_root: Path, rel_path: str) -> Path:
    normalized = rel_path[2:] if rel_path.startswith("./") else rel_path

    if normalized.startswith("commands/"):
        return source_root / "targets" / "claude" / normalized
    if normalized.startswith("agents/"):
        return source_root / "targets" / "claude" / normalized
    if normalized.startswith("hooks/"):
        return source_root / "targets" / "claude" / normalized
    if normalized.startswith("lessons/"):
        return source_root / "targets" / "claude" / normalized
    return source_root / normalized


def copy_tree_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def build_wrapper(source_root: Path, output_root: Path, source_sha: str | None = None) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    template = load_json(source_root / "targets" / "claude" / "marketplace.template.json")
    bundles = load_bundles(source_root)
    manifest = dict(template)
    manifest["plugins"] = bundles

    copy_tree_if_exists(source_root / "skills", output_root / "skills")
    copy_tree_if_exists(source_root / "targets" / "claude" / "commands", output_root / "commands")
    copy_tree_if_exists(source_root / "targets" / "claude" / "agents", output_root / "agents")
    copy_tree_if_exists(source_root / "targets" / "claude" / "hooks", output_root / "hooks")
    copy_tree_if_exists(source_root / "targets" / "claude" / "lessons", output_root / "lessons")

    claude_plugin_dir = output_root / ".claude-plugin"
    claude_plugin_dir.mkdir(parents=True, exist_ok=True)
    (claude_plugin_dir / "marketplace.json").write_text(json.dumps(manifest, indent=2) + "\n")

    readme_src = source_root / "targets" / "claude" / "README.md"
    if readme_src.exists():
        shutil.copy2(readme_src, output_root / "README.md")

    license_src = source_root / "LICENSE"
    if license_src.exists():
        shutil.copy2(license_src, output_root / "LICENSE")

    generated_from = source_sha or os.environ.get("GITHUB_SHA") or "local"
    (output_root / "GENERATED_FROM").write_text(f"{generated_from}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=".", help="Path to policyengine-skills repo")
    parser.add_argument("--output-root", required=True, help="Directory for generated wrapper output")
    parser.add_argument("--source-sha", default=None, help="Source commit SHA for GENERATED_FROM")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_wrapper(Path(args.source_root).resolve(), Path(args.output_root).resolve(), args.source_sha)


if __name__ == "__main__":
    main()
