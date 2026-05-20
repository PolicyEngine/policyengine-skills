#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_ROOT="${CODEX_REPOS_ROOT:-$HOME/vscode}"
TEMPLATE_DIR="$ROOT/targets/codex/agents"
BEGIN_MARKER="<!-- BEGIN POLICYENGINE CODEX ROUTING -->"
END_MARKER="<!-- END POLICYENGINE CODEX ROUTING -->"

if [ ! -d "$TEMPLATE_DIR" ]; then
  echo "No Codex routing templates found at $TEMPLATE_DIR" >&2
  exit 1
fi

installed=0
skipped=0

while IFS= read -r template; do
  repo_name="$(basename "$(dirname "$template")")"
  repo_dir="$REPOS_ROOT/$repo_name"

  if [ ! -d "$repo_dir" ]; then
    skipped=$((skipped + 1))
    continue
  fi

  target="$repo_dir/AGENTS.md"
  block="$(mktemp)"
  {
    printf '%s\n' "$BEGIN_MARKER"
    cat "$template"
    printf '%s\n' "$END_MARKER"
  } > "$block"

  if [ -f "$target" ]; then
    if grep -q "$BEGIN_MARKER" "$target"; then
      if ! grep -q "$END_MARKER" "$target"; then
        echo "Found $BEGIN_MARKER without matching $END_MARKER in $target" >&2
        rm "$block"
        exit 1
      fi
      awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
        $0 == begin { skipping = 1; next }
        $0 == end { skipping = 0; next }
        !skipping { print }
      ' "$target" > "$target.tmp"
      cat "$block" "$target.tmp" > "$target"
      rm "$target.tmp"
    else
      {
        cat "$block"
        printf '\n'
        cat "$target"
      } > "$target.tmp"
      mv "$target.tmp" "$target"
    fi
  else
    cp "$block" "$target"
  fi

  rm "$block"
  installed=$((installed + 1))
done < <(find "$TEMPLATE_DIR" -mindepth 2 -maxdepth 2 -name AGENTS.md | sort)

printf 'Installed Codex routing into %s repo(s) under %s; skipped %s missing repo(s)\n' "$installed" "$REPOS_ROOT" "$skipped"
