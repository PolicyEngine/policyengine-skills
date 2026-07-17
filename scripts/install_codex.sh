#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
TARGET_DIR="$CODEX_HOME/skills"

mkdir -p "$TARGET_DIR"

# Prune dangling symlinks left by earlier catalog layouts. Only touch links
# that (a) no longer resolve and (b) pointed into a policyengine-skills
# checkout — unrelated skills in the target dir are left alone.
pruned=0
for link in "$TARGET_DIR"/*; do
  if [ -L "$link" ] && [ ! -e "$link" ]; then
    case "$(readlink "$link")" in
      *policyengine-skills/skills/*)
        rm "$link"
        pruned=$((pruned + 1))
        ;;
    esac
  fi
done
if [ "$pruned" -gt 0 ]; then
  printf 'Pruned %s stale policyengine-skills symlinks\n' "$pruned"
fi

count=0
while IFS= read -r skill_file; do
  skill_dir="$(dirname "$skill_file")"
  skill_name="$(basename "$skill_dir")"
  target="$TARGET_DIR/$skill_name"
  rm -rf "$target"
  ln -s "$skill_dir" "$target"
  count=$((count + 1))
done < <(find "$ROOT/skills" -type f -name SKILL.md | sort)

printf 'Installed %s skills into %s\n' "$count" "$TARGET_DIR"
