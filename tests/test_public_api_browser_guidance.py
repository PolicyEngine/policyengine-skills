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
TEXT_SUFFIXES = {
    ".md", ".json", ".yaml", ".yml", ".py", ".sh", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html", ".vue", ".svelte",
}
BROWSER_FILE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html", ".vue", ".svelte"}

BROWSER_LANGUAGES = {
    "ts", "tsx", "js", "jsx", "javascript", "typescript", "mjs", "cjs", "html", "htm", "vue", "svelte", "astro",
}
# A fenced example of server-side TypeScript or JavaScript may name the Public API
# when the line before its fence is this marker.
SERVER_CODE_MARKER = "<!-- server-code -->"
# The Public API only: not household.api.policyengine.org (the household API) or
# v2.api.policyengine.org (the v2 alpha), hence the left boundary.
PUBLIC_API_HOST = re.compile(
    r"(?<![\w.-])api\.policyengine\.org"
    r"|policyengine-api(?:-staging)?-[a-z0-9]+(?:-[a-z]{2})?\.a\.run\.app"
    r"|policyengine-api(?:-staging)?-[0-9]+\.[a-z0-9-]+\.run\.app"
)
# ``` or ~~~ fences of three or more characters, closed by the same fence.
FENCE = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<language>[A-Za-z0-9_+-]*)[^\n]*\n(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
# An *_AUDIENCE name holds API v1's Auth0 identifier for a browser's sign-in, not an
# address to call, so it is left out.
PUBLIC_PREFIX_SET_TO_PUBLIC_API = re.compile(
    r"\b(?:NEXT_PUBLIC|VITE|REACT_APP)_(?![A-Z0-9_]*AUDIENCE)[A-Z0-9_]+[\"']?\s*(?:[=:]|\|\||\?\?)\s*[\"'`]?https?://"
    r"(?:api\.policyengine\.org|(?:[a-z0-9-]+---)?policyengine-api[a-z0-9-]*\.[a-z0-9.-]*run\.app)"
)
# A public-prefix name that holds a secret, that is an unqualified token or key
# (NEXT_PUBLIC_API_KEY, VITE_ACCESS_TOKEN), or that is named for the Public API's
# address or server client. A browser's own sign-in settings (VITE_AUTH0_DOMAIN,
# VITE_AUTH0_CLIENT_ID, NEXT_PUBLIC_AUTH0_AUDIENCE) and other services' public
# tokens named for their service (NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN) are public by design.
PUBLIC_PREFIX_CREDENTIAL = re.compile(
    r"\b(?:NEXT_PUBLIC|VITE|REACT_APP)_(?=(?:API_)?(?:ACCESS_|BEARER_|AUTH_)?(?:TOKEN|KEY)\b"
    r"|[A-Z0-9_]*(?:SECRET|PASSWORD|PRIVATE_KEY|CREDENTIAL"
    r"|(?<![A-Z])(?:POLICYENGINE_API(?!_V2)|PE_API|PUBLIC_API|API_V1)"
    r"|(?<![A-Z])POLICYENGINE_(?:API_)?(?:TOKEN|KEY|CLIENT)"
    r"|AUTH0[A-Z0-9_]*(?:TOKEN|M2M)))[A-Z0-9_]+"
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
    offenders: list[str] = []
    for block in FENCE.finditer(text):
        line_before = text[: block.start()].rstrip("\n").rsplit("\n", 1)[-1]
        if SERVER_CODE_MARKER in line_before:
            continue
        body = block.group("body")
        if block.group("language").lower() in BROWSER_LANGUAGES:
            if PUBLIC_API_HOST.search(body):
                offenders.append(body)
        else:
            # A Markdown or text block can hold a nested example.
            offenders.extend(browser_blocks_naming_the_public_api(body))
    return offenders


def test_no_browser_language_example_names_the_public_api() -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in scanned_files()
        if path.suffix == ".md" and browser_blocks_naming_the_public_api(path.read_text())
    ]
    assert offenders == [], f"browser-language examples that call the Public API: {offenders}"


def test_no_code_file_in_the_catalog_names_the_public_api() -> None:
    # Templates and examples shipped as files (for example under skills/*/templates/).
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in scanned_files()
        if path.suffix in BROWSER_FILE_SUFFIXES and PUBLIC_API_HOST.search(path.read_text())
    ]
    assert offenders == []


def test_no_public_prefix_variable_holds_the_public_api_or_a_credential() -> None:
    offenders = []
    for path in scanned_files():
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if PUBLIC_PREFIX_SET_TO_PUBLIC_API.search(line) or PUBLIC_PREFIX_CREDENTIAL.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line_number}")
    assert offenders == []


def test_guards_catch_the_patterns_they_name() -> None:
    browser_examples = [
        "```ts\nconst API_BASE = 'https://api.policyengine.org';\n```\n",
        "  ```js\n  fetch(`https://api.policyengine.org/us/calculate`)\n  ```\n",
        "```tsx\nfetch('https://policyengine-api-staging-abc123defg-uc.a.run.app/us/metadata')\n```\n",
        "```ts\nfetch('https://policyengine-api-123456789012.us-central1.run.app/us/metadata')\n```\n",
        "~~~ts\nfetch('https://api.policyengine.org/us/metadata')\n~~~\n",
        "````tsx\nfetch('https://api.policyengine.org/us/metadata')\n````\n",
        "```html\n<script>fetch('https://api.policyengine.org/us/metadata')</script>\n```\n",
        "```vue\n<script setup>fetch('https://api.policyengine.org/uk/metadata')</script>\n```\n",
        "```svelte\n<script>fetch('https://api.policyengine.org/uk/metadata')</script>\n```\n",
        "```cjs\nfetch('https://api.policyengine.org/uk/metadata')\n```\n",
        "````markdown\nAn example:\n```ts\nfetch('https://api.policyengine.org/us/metadata')\n```\n````\n",
        "``` ts\nfetch('https://api.policyengine.org/us/metadata')\n```\n",
    ]
    for example in browser_examples:
        assert browser_blocks_naming_the_public_api(example), example
    not_browser_examples = [
        "```bash\ncurl https://api.policyengine.org/us/metadata\n```\n",
        "```ts\nfetch('https://household.api.policyengine.org/us/calculate')\n```\n",
        # Server-side TypeScript, marked as such, may name the Public API.
        "<!-- server-code -->\n```ts\nawait fetch('https://api.policyengine.org/us/calculate', { headers })\n```\n",
    ]
    for example in not_browser_examples:
        assert not browser_blocks_naming_the_public_api(example), example
    for unsafe in (
        "NEXT_PUBLIC_API_URL=https://api.policyengine.org",
        "VITE_API_URL: 'https://api.policyengine.org'",
        '"NEXT_PUBLIC_API_URL": "https://api.policyengine.org"',
        "`process.env.NEXT_PUBLIC_API_URL || 'https://api.policyengine.org'`",
        "NEXT_PUBLIC_POLICYENGINE_API_AUTH0_CLIENT_SECRET",
        "NEXT_PUBLIC_POLICYENGINE_API_AUTH0_CLIENT_ID",
        "VITE_PE_API_KEY",
        "VITE_AUTH0_CLIENT_SECRET",
        "VITE_API_TOKEN_SECRET",
        "`process.env.NEXT_PUBLIC_API_URL ?? 'https://api.policyengine.org'`",
        "NEXT_PUBLIC_API_KEY",
        "NEXT_PUBLIC_API_TOKEN",
        "NEXT_PUBLIC_BEARER_TOKEN",
        "VITE_ACCESS_TOKEN",
        "VITE_POLICYENGINE_TOKEN",
        "VITE_API_ACCESS_TOKEN",
        "NEXT_PUBLIC_API_BEARER_TOKEN",
    ):
        assert PUBLIC_PREFIX_SET_TO_PUBLIC_API.search(unsafe) or PUBLIC_PREFIX_CREDENTIAL.search(unsafe), unsafe
    for safe in (
        "NEXT_PUBLIC_API_URL=https://policyengine--my-tool-fastapi-app.modal.run",
        "never a `NEXT_PUBLIC_*` or `VITE_*` name",
        "NEXT_PUBLIC_API_V2_URL || 'https://v2.api.policyengine.org'",
        "VITE_HOUSEHOLD_API_URL=https://household.api.policyengine.org",
        # A browser's own sign-in settings, as app-v2 uses them, are public by design.
        "VITE_AUTH0_DOMAIN=auth.policyengine.org",
        "VITE_AUTH0_CLIENT_ID",
        "NEXT_PUBLIC_AUTH0_AUDIENCE",
        "NEXT_PUBLIC_MAPBOX_TOKEN",
        "NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN",
        # The browser sign-in audience is API v1's identifier, not an address to call.
        "NEXT_PUBLIC_AUTH0_AUDIENCE=https://api.policyengine.org/",
        "VITE_AUTH0_AUDIENCE: 'https://api.policyengine.org/'",
        # app-v2's v2 alpha address, and a token named for another service.
        "NEXT_PUBLIC_POLICYENGINE_API_V2_URL",
        "VITE_POLICYENGINE_MAPBOX_TOKEN",
    ):
        assert not PUBLIC_PREFIX_SET_TO_PUBLIC_API.search(safe), safe
        assert not PUBLIC_PREFIX_CREDENTIAL.search(safe), safe


def test_dashboard_scaffold_loads_the_access_skill() -> None:
    text = (REPO_ROOT / "targets/claude/agents/dashboard/dashboard-scaffold.md").read_text()
    loading = text.split("## First: Load Required Skills", 1)
    assert len(loading) == 2
    assert "`Skill: policyengine-api-access`" in loading[1].split("\n## ", 1)[0]


def test_custom_backend_guidance_agrees_with_what_the_dashboard_api_offers() -> None:
    # The dashboard API compares a parameter reform with current law across the
    # economy, so that alone is no reason for a custom Modal backend.
    tools_text = TOOLS_SKILL.read_text()
    pattern_c = re.search(r"^- \*\*C — .*?(?=^\S)", tools_text, re.DOTALL | re.MULTILINE)
    assert pattern_c, "the tools skill has no Pattern C entry"
    assert "society-wide microsim," not in pattern_c.group(0)
    assert "structural" in pattern_c.group(0)
    new_tool = (REPO_ROOT / "targets/claude/commands/new-tool.md").read_text()
    assert "unless the tool needs microsimulation,\n> custom reforms" not in new_tool
    assert "structural" in new_tool.split("**Prefer Pattern B**", 1)[1].split("\n\n", 1)[0]


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


def test_vue_and_svelte_files_are_scanned() -> None:
    assert {".vue", ".svelte"} <= TEXT_SUFFIXES


INTEGRATOR = REPO_ROOT / "targets/claude/agents/dashboard/dashboard-integrator.md"


def test_integrator_varies_a_household_in_one_calculation() -> None:
    # The dashboard API allows 30 household calculations a minute from one address,
    # so a chart over 20 incomes is one calculation with axes, not 20.
    step = INTEGRATOR.read_text().split("### Step 6", 1)
    assert len(step) == 2
    variation = step[1].split("\n### ", 1)[0]
    assert "axes" in variation
    assert "30 household calculations a minute" in variation


def test_integrator_types_the_household_for_the_client() -> None:
    assert "`buildHouseholdDict` returns `Household`" in INTEGRATOR.read_text()


def test_contributing_documents_the_server_code_marker() -> None:
    assert SERVER_CODE_MARKER in (REPO_ROOT / "CONTRIBUTING.md").read_text()


BACKEND_BUILDER = REPO_ROOT / "targets/claude/agents/dashboard/backend-builder.md"


def test_calculated_household_is_read_through_a_typed_helper() -> None:
    # With an `unknown` index signature, result.households.household... does not
    # compile under strict mode, so transformers read through readVariable().
    assert "export function readVariable(" in BACKEND_BUILDER.read_text()
    integrator = INTEGRATOR.read_text()
    assert "readVariable(" in integrator
    assert "result.households.household.household_net_income[year]" not in integrator


def test_integrator_debounces_calculations_and_runs_for_every_country() -> None:
    integrator = INTEGRATOR.read_text()
    assert "useDebouncedValue" in integrator.split("### Step 4", 1)[1].split("\n### ", 1)[0]
    variation = integrator.split("### Step 6", 1)[1].split("\n### ", 1)[0]
    assert "useDebouncedValue" in variation
    assert "countryId === 'uk'" in variation


def test_first_401_row_does_not_claim_a_malformed_anonymous_header_gets_the_same_answer() -> None:
    skill = (REPO_ROOT / "skills/policyengine-api-access/SKILL.md").read_text()
    rows_401 = [row for row in skill.split("## Errors", 1)[1].splitlines() if row.startswith("| 401 ")]
    assert rows_401 and not any("malformed `PolicyEngine-Unauthenticated-User`" in row for row in rows_401)
