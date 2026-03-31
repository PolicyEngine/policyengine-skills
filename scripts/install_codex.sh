#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
TARGET_DIR="$CODEX_HOME/skills"

mkdir -p "$TARGET_DIR"

count=0
while IFS= read -r skill_file; do
  skill_dir="$(dirname "$skill_file")"
  skill_name="$(basename "$skill_dir")"
  ln -sfn "$skill_dir" "$TARGET_DIR/$skill_name"
  count=$((count + 1))
done < <(find "$ROOT/skills" -type f -name SKILL.md | sort)

printf 'Installed %s skills into %s\n' "$count" "$TARGET_DIR"
