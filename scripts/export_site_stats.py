"""Export catalog counts for the policyengine.org /claude-plugin page.

The app-v2 page (website/src/app/[countryId]/claude-plugin/) imports a small
stats module; regenerate it here whenever the catalog changes and copy the
JSON into policyengine-app-v2 (see CONTRIBUTING.md "Keeping the website in
sync").

Usage:
    python3 scripts/export_site_stats.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def count(pattern: str, base: str) -> int:
    return len(list((ROOT / base).glob(pattern)))


def main() -> None:
    stats = {
        "skills": count("*/SKILL.md", "skills"),
        "agents": count("**/*.md", "targets/claude/agents"),
        "commands": count("*.md", "targets/claude/commands"),
        "bundles": count("*.json", "bundles"),
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
