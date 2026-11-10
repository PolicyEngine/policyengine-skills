"""No skill, agent, command or doc tells browser code to call the Public API.

The Public API (api.policyengine.org) is becoming callable only by
PolicyEngine's own servers. Pages reach it through www.policyengine.org's
dashboard API with ``@policyengine/api-client``, and servers send their own
Auth0 client-credentials token; the policyengine-api-access skill says how.
These tests keep the rest of the catalog from teaching the old way:

- a browser-language example (TypeScript or JavaScript) never names a Public
  API host;
- no ``NEXT_PUBLIC_*`` or ``VITE_*`` variable is set to a Public API host, or
  named like a credential;
- the skills, agents and commands that guide dashboard and app work point to
  policyengine-api-access;
- the policyengine-api skill lists the Public API's routes as they are now.

Server-side, notebook and analysis examples that call the Public API (shell
``curl``, Python) are not checked here: they run outside a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("skills", "targets", "docs")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".sh", ".ts", ".tsx", ".js", ".mjs"}

BROWSER_LANGUAGES = {"ts", "tsx", "js", "jsx", "javascript", "typescript", "mjs"}
# The Public API only: not household.api.policyengine.org (the household API) or
# v2.api.policyengine.org (the v2 alpha), hence the left boundary.
PUBLIC_API_HOST = re.compile(
    r"(?<![\w.-])api\.policyengine\.org"
    r"|policyengine-api(?:-staging)?-[a-z0-9]+(?:-[a-z]{2})?\.a\.run\.app"
)
FENCE = re.compile(r"^[ \t]*```([A-Za-z0-9_+-]*)[^\n]*\n(.*?)^[ \t]*```", re.DOTALL | re.MULTILINE)
PUBLIC_PREFIX_SET_TO_PUBLIC_API = re.compile(
    r"\b(?:NEXT_PUBLIC|VITE)_[A-Z0-9_]+\s*[=:]\s*[\"'`]?https?://"
    r"(?:api\.policyengine\.org|(?:[a-z0-9-]+---)?policyengine-api[a-z0-9-]*\.[a-z0-9.-]*run\.app)"
)
PUBLIC_PREFIX_CREDENTIAL = re.compile(
    r"\b(?:NEXT_PUBLIC|VITE)_[A-Z0-9_]*(?:AUTH0|SECRET|TOKEN|CREDENTIAL)[A-Z0-9_]*"
)

ACCESS_SKILL = "policyengine-api-access"
# Files that guide dashboard, tool or app work and so must point to the access skill.
DASHBOARD_GUIDANCE = (
    "skills/policyengine/SKILL.md",
    "skills/policyengine-api/SKILL.md",
    "skills/policyengine-app/SKILL.md",
    "skills/policyengine-tools/SKILL.md",
    "targets/claude/agents/dashboard/backend-builder.md",
    "targets/claude/agents/dashboard/dashboard-integrator.md",
    "targets/claude/agents/dashboard/dashboard-planner.md",
    "targets/claude/agents/dashboard/dashboard-scaffold.md",
    "targets/claude/commands/new-tool.md",
    "targets/codex/agents/policyengine-app-v2/AGENTS.md",
    "docs/when-to-use.md",
)
API_SKILL = REPO_ROOT / "skills" / "policyengine-api" / "SKILL.md"
TOOLS_SKILL = REPO_ROOT / "skills" / "policyengine-tools" / "SKILL.md"


def scanned_files() -> list[Path]:
    return sorted(
        path
        for directory in SCAN_DIRS
        for path in (REPO_ROOT / directory).rglob("*")
        if path.is_file() and path.suffix in TEXT_SUFFIXES and "__pycache__" not in path.parts
    )


def browser_blocks_naming_the_public_api(text: str) -> list[str]:
    return [
        body
        for language, body in FENCE.findall(text)
        if language.lower() in BROWSER_LANGUAGES and PUBLIC_API_HOST.search(body)
    ]


def test_no_browser_language_example_names_the_public_api() -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in scanned_files()
        if path.suffix == ".md" and browser_blocks_naming_the_public_api(path.read_text())
    ]
    assert offenders == [], f"browser-language examples that call the Public API: {offenders}"


def test_no_public_prefix_variable_holds_the_public_api_or_a_credential() -> None:
    offenders = []
    for path in scanned_files():
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if PUBLIC_PREFIX_SET_TO_PUBLIC_API.search(line) or PUBLIC_PREFIX_CREDENTIAL.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line_number}")
    assert offenders == []


def test_guards_catch_the_patterns_they_name() -> None:
    browser_example = "```ts\nconst API_BASE = 'https://api.policyengine.org';\n```\n"
    indented_example = "  ```js\n  fetch(`https://api.policyengine.org/us/calculate`)\n  ```\n"
    cloud_run_example = "```tsx\nfetch('https://policyengine-api-staging-abc123defg-uc.a.run.app/us/metadata')\n```\n"
    shell_example = "```bash\ncurl https://api.policyengine.org/us/metadata\n```\n"
    household_api_example = "```ts\nfetch('https://household.api.policyengine.org/us/calculate')\n```\n"
    assert browser_blocks_naming_the_public_api(browser_example)
    assert browser_blocks_naming_the_public_api(indented_example)
    assert browser_blocks_naming_the_public_api(cloud_run_example)
    assert not browser_blocks_naming_the_public_api(shell_example)
    assert not browser_blocks_naming_the_public_api(household_api_example)
    for unsafe in (
        "NEXT_PUBLIC_API_URL=https://api.policyengine.org",
        "VITE_API_URL: 'https://api.policyengine.org'",
        "NEXT_PUBLIC_POLICYENGINE_API_AUTH0_CLIENT_SECRET",
        "VITE_API_TOKEN",
    ):
        assert PUBLIC_PREFIX_SET_TO_PUBLIC_API.search(unsafe) or PUBLIC_PREFIX_CREDENTIAL.search(unsafe), unsafe
    for safe in (
        "NEXT_PUBLIC_API_URL=https://policyengine--my-tool-fastapi-app.modal.run",
        "never a `NEXT_PUBLIC_*` or `VITE_*` name",
        "NEXT_PUBLIC_API_V2_URL || 'https://v2.api.policyengine.org'",
        "VITE_HOUSEHOLD_API_URL=https://household.api.policyengine.org",
    ):
        assert not PUBLIC_PREFIX_SET_TO_PUBLIC_API.search(safe), safe
        assert not PUBLIC_PREFIX_CREDENTIAL.search(safe), safe


@pytest.mark.parametrize("relative_path", DASHBOARD_GUIDANCE)
def test_dashboard_guidance_points_to_the_access_skill(relative_path: str) -> None:
    assert ACCESS_SKILL in (REPO_ROOT / relative_path).read_text()


def test_api_skill_lists_the_public_routes_as_they_are_now() -> None:
    text = API_SKILL.read_text()
    # The Public API removed these (policyengine_api/migration_flags.py).
    for removed_path in ("/specification", "/liveness-check", "/readiness-check"):
        assert removed_path not in text, removed_path
    for public_path in ("/health", "/v2/openapi.json"):
        assert public_path in text, public_path


def test_api_skill_does_not_send_frontends_to_the_public_api() -> None:
    text = API_SKILL.read_text()
    assert "JS frontends" not in text
    assert "server credential" in text


def test_tools_skill_pattern_b_uses_the_dashboard_api() -> None:
    text = TOOLS_SKILL.read_text()
    pattern_b = re.search(r"^- \*\*B — .*?(?=^- \*\*C — )", text, re.DOTALL | re.MULTILINE)
    assert pattern_b, "the tools skill has no Pattern B entry"
    assert "@policyengine/api-client" in pattern_b.group(0)
    assert "https://api.policyengine.org" not in pattern_b.group(0)
