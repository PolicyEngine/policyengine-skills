"""The policyengine-api-access skill: where it is listed, what it teaches, and its token template.

The skill tells dashboard developers and agents how to reach the Public API
(api.policyengine.org) once it serves only PolicyEngine's servers: pages use
www.policyengine.org's dashboard API through ``@policyengine/api-client``, and
servers send their own Auth0 client-credentials token. The operation paths,
header names, tenants and refusal bodies below are copied from merged code in
PolicyEngine/policyengine-app-v2 (``website/src/app/api/``,
``website/src/lib/dashboardApi/``, ``packages/public-api-forwarding/`` and
``packages/api-client/``) and PolicyEngine/policyengine-api
(``policyengine_api/request_caller.py``,
``policyengine_api/libs/server_credentials.py``), so an edit to the skill
cannot drift from them unnoticed.

``templates/public_api_token.py`` is the token cache servers copy. Its tests
use a fake opener and a dict as the shared store, so they never call Auth0 or
the Public API.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import re
import subprocess
import sys
import threading
import urllib.error
from pathlib import Path
from types import ModuleType

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "policyengine-api-access"
SKILL_DIR = REPO_ROOT / "skills" / SKILL_NAME
SKILL_FILE = SKILL_DIR / "SKILL.md"
TOKEN_TEMPLATE = SKILL_DIR / "templates" / "public_api_token.py"

# Bundles whose users build dashboards or tools, or call the Public API.
# analysis-tools is the bundle the create-dashboard workflow installs.
BUNDLES_WITH_SKILL = (
    "analysis-tools",
    "api-development",
    "app-development",
    "complete",
    "dashboard-builder",
)

DASHBOARD_API_OPERATIONS = (
    "POST /api/household/calculate",
    "POST /api/policies",
    "GET /api/economy/compare",
    "GET /api/metadata/{country}",
)
API_CLIENT_METHODS = (
    "createPolicyEngineApiClient",
    "calculateHousehold",
    "createPolicy",
    "getEconomyComparison",
    "compareEconomy",
    "getMetadata",
    "PolicyEngineApiError",
    "EconomyComparisonTimeoutError",
)
SERVER_CONTRACT_FACTS = (
    "Authorization: Bearer",
    "PolicyEngine-User-Authorization",
    "PolicyEngine-Unauthenticated-User",
    "policyengine-api.uk.auth0.com",
    "policyengine-api-staging.uk.auth0.com",
    "https://api.policyengine.org/",
    "https://staging-api.policyengine.org/",
    "PUBLIC_API_SERVER_CLIENT_IDS",
    "POLICYENGINE_API_URL",
    "POLICYENGINE_API_AUTH0_DOMAIN",
    "POLICYENGINE_API_AUTH0_AUDIENCE",
    "POLICYENGINE_API_AUTH0_CLIENT_ID",
    "POLICYENGINE_API_AUTH0_CLIENT_SECRET",
    "vercel env pull",
    '{"status":"error","message":"Authentication is required"}',
    '{"status":"error","message":"Authentication is unavailable"}',
    "Pages on this origin may not call the dashboard API.",
    "appZoneRoutes.ts",
    "*-policy-engine.vercel.app",
)
HANDLED_STATUSES = ("401", "403", "429", "503")


def skill_text() -> str:
    assert SKILL_FILE.is_file(), f"{SKILL_FILE.relative_to(REPO_ROOT)} is missing"
    return SKILL_FILE.read_text()


def skill_frontmatter() -> dict:
    text = skill_text()
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md has no YAML frontmatter"
    return yaml.safe_load(match.group(1))


def test_frontmatter_names_the_skill_and_its_category() -> None:
    frontmatter = skill_frontmatter()
    assert frontmatter["name"] == SKILL_NAME
    assert frontmatter["metadata"]["category"] == "apps"
    description = frontmatter["description"]
    assert len(description) <= 1024
    for trigger in ("api.policyengine.org", "dashboard", "@policyengine/api-client"):
        assert trigger in description, f"description lacks the trigger {trigger!r}"


@pytest.mark.parametrize("bundle_name", BUNDLES_WITH_SKILL)
def test_bundle_ships_the_skill(bundle_name: str) -> None:
    bundle = json.loads((REPO_ROOT / "bundles" / f"{bundle_name}.json").read_text())
    assert f"./skills/{SKILL_NAME}" in bundle["skills"]


def test_catalog_lists_the_skill() -> None:
    catalog = (REPO_ROOT / "skills" / "README.md").read_text()
    assert f"| **{SKILL_NAME}** |" in catalog


def test_wrapper_build_ships_the_skill_and_template(tmp_path: Path) -> None:
    output_dir = tmp_path / "policyengine-claude"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "build_claude_wrapper.py"),
            "--source-root",
            str(REPO_ROOT),
            "--output-root",
            str(output_dir),
        ],
        check=True,
    )
    assert (output_dir / "skills" / SKILL_NAME / "SKILL.md").is_file()
    assert (output_dir / "skills" / SKILL_NAME / "templates" / "public_api_token.py").is_file()
    manifest = json.loads((output_dir / ".claude-plugin" / "marketplace.json").read_text())
    plugins_with_skill = {
        plugin["name"]
        for plugin in manifest["plugins"]
        if f"./skills/{SKILL_NAME}" in plugin.get("skills", [])
    }
    assert plugins_with_skill == set(BUNDLES_WITH_SKILL)


@pytest.mark.parametrize("operation", DASHBOARD_API_OPERATIONS)
def test_skill_names_each_dashboard_api_operation(operation: str) -> None:
    assert operation in skill_text()


@pytest.mark.parametrize("name", API_CLIENT_METHODS)
def test_skill_names_the_browser_client_exports(name: str) -> None:
    assert name in skill_text()


@pytest.mark.parametrize("fact", SERVER_CONTRACT_FACTS)
def test_skill_states_the_server_contract(fact: str) -> None:
    assert fact in skill_text()


@pytest.mark.parametrize("status_code", HANDLED_STATUSES)
def test_skill_says_how_to_handle_each_refusal(status_code: str) -> None:
    error_section = skill_text().split("## Errors", 1)
    assert len(error_section) == 2, "SKILL.md has no '## Errors' section"
    assert re.search(rf"^\| {status_code} ", error_section[1], re.MULTILINE), (
        f"the errors table has no row for {status_code}"
    )


def test_skill_points_servers_at_the_token_template() -> None:
    assert "templates/public_api_token.py" in skill_text()


# --- templates/public_api_token.py -----------------------------------------


def load_token_module() -> ModuleType:
    assert TOKEN_TEMPLATE.is_file(), f"{TOKEN_TEMPLATE.relative_to(REPO_ROOT)} is missing"
    spec = importlib.util.spec_from_file_location("public_api_token", TOKEN_TEMPLATE)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves the module's annotations through sys.modules.
    sys.modules["public_api_token"] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status = status_code
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class RecordingOpener:
    """Answers token requests with fresh tokens and Public API requests with 200."""

    def __init__(self, token_lifetime_seconds: int = 86_400) -> None:
        self.token_lifetime_seconds = token_lifetime_seconds
        self.token_requests: list[dict] = []
        self.api_requests: list[tuple[str, str, str | None]] = []
        self.refuse_next_api_requests = 0

    def open(self, request, timeout=None):  # noqa: ANN001 - urllib's opener signature
        if request.full_url.endswith("/oauth/token"):
            self.token_requests.append(json.loads(request.data))
            return FakeResponse(
                200,
                {
                    "access_token": f"token-{len(self.token_requests)}",
                    "expires_in": self.token_lifetime_seconds,
                    "token_type": "Bearer",
                },
            )
        self.api_requests.append(
            (request.get_method(), request.full_url, request.get_header("Authorization"))
        )
        if self.refuse_next_api_requests > 0:
            self.refuse_next_api_requests -= 1
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {"WWW-Authenticate": "Bearer"},
                None,
            )
        return FakeResponse(200, {"status": "ok", "message": None, "result": {}})


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def make_settings(token_module: ModuleType, api_url: str = "https://api.example.test"):
    return token_module.PublicApiSettings.from_environment(
        {
            "POLICYENGINE_API_URL": api_url,
            "POLICYENGINE_API_AUTH0_DOMAIN": "tenant.example.test",
            "POLICYENGINE_API_AUTH0_AUDIENCE": "https://audience.example.test/",
            "POLICYENGINE_API_AUTH0_CLIENT_ID": "placeholder-client-id",
            "POLICYENGINE_API_AUTH0_CLIENT_SECRET": "placeholder-client-secret",
        }
    )


def test_template_requests_one_token_for_many_requests() -> None:
    token_module = load_token_module()
    opener = RecordingOpener()
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store={}, clock=Clock(), opener=opener
    )
    assert [tokens.access_token() for _ in range(5)] == ["token-1"] * 5
    assert len(opener.token_requests) == 1
    assert opener.token_requests[0] == {
        "grant_type": "client_credentials",
        "client_id": "placeholder-client-id",
        "client_secret": "placeholder-client-secret",
        "audience": "https://audience.example.test/",
    }


def test_template_shares_one_token_between_instances() -> None:
    token_module = load_token_module()
    shared_store: dict = {}
    opener = RecordingOpener()
    first_instance = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store=shared_store, clock=Clock(), opener=opener
    )
    second_instance = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store=shared_store, clock=Clock(), opener=opener
    )
    assert first_instance.access_token() == second_instance.access_token() == "token-1"
    assert len(opener.token_requests) == 1
    assert "placeholder-client-secret" not in json.dumps(shared_store)


def test_template_replaces_the_token_five_minutes_before_it_expires() -> None:
    token_module = load_token_module()
    clock = Clock()
    opener = RecordingOpener(token_lifetime_seconds=86_400)
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store={}, clock=clock, opener=opener
    )
    assert tokens.access_token() == "token-1"
    clock.now += 86_400 - 301
    assert tokens.access_token() == "token-1"
    clock.now += 2
    assert tokens.access_token() == "token-2"


def test_template_raises_a_refused_request_without_requesting_another_token() -> None:
    # A 401 means the client is not on the allow list, or its tenant or audience is
    # wrong; a new token would be refused too, and each one counts against the
    # tenant's monthly machine-to-machine allowance (app-v2's forwarder never retries).
    token_module = load_token_module()
    opener = RecordingOpener()
    opener.refuse_next_api_requests = 3
    shared_store: dict = {}
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store=shared_store, clock=Clock(), opener=opener
    )
    for _ in range(3):
        with pytest.raises(urllib.error.HTTPError) as refusal:
            token_module.call_public_api(tokens, "POST", "/us/calculate", {"household": {}})
        assert refusal.value.code == 401
    assert len(opener.token_requests) == 1
    assert [header for _, _, header in opener.api_requests] == ["Bearer token-1"] * 3
    assert tokens.access_token() == "token-1"


def test_template_turns_a_redirected_token_request_into_an_error() -> None:
    token_module = load_token_module()

    class RedirectingTokenEndpoint(RecordingOpener):
        def open(self, request, timeout=None):  # noqa: ANN001 - urllib's opener signature
            raise urllib.error.HTTPError(
                request.full_url, 307, "Temporary Redirect", {"Location": "https://elsewhere.test/"}, None
            )

    shared_store: dict = {}
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store=shared_store, clock=Clock(), opener=RedirectingTokenEndpoint()
    )
    with pytest.raises(token_module.PublicApiTokenError, match="307"):
        tokens.access_token()
    assert shared_store == {}
    # By default the provider uses the opener that refuses every redirect.
    assert token_module.PublicApiTokenProvider(make_settings(token_module)).opener is token_module.NO_REDIRECT_OPENER


def test_template_refuses_partial_settings() -> None:
    token_module = load_token_module()
    with pytest.raises(token_module.PublicApiSettingsError):
        token_module.PublicApiSettings.from_environment(
            {"POLICYENGINE_API_URL": "https://api.example.test"}
        )


class RedirectingHandler(http.server.BaseHTTPRequestHandler):
    requested_paths: list[str] = []

    def do_GET(self) -> None:  # noqa: N802 - http.server's method name
        RedirectingHandler.requested_paths.append(self.path)
        self.send_response(307)
        self.send_header("Location", "/elsewhere")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        return None


def test_template_never_follows_a_redirect() -> None:
    token_module = load_token_module()
    RedirectingHandler.requested_paths = []
    server = http.server.HTTPServer(("127.0.0.1", 0), RedirectingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        api_url = f"http://127.0.0.1:{server.server_address[1]}"
        tokens = token_module.PublicApiTokenProvider(
            make_settings(token_module, api_url=api_url),
            shared_store={},
            clock=Clock(),
            opener=RecordingOpener(),
        )
        tokens.access_token()
        with pytest.raises(urllib.error.HTTPError) as refusal:
            token_module.call_public_api(
                tokens, "GET", "/us/metadata", opener=token_module.NO_REDIRECT_OPENER
            )
        assert refusal.value.code == 307
        assert RedirectingHandler.requested_paths == ["/us/metadata"]
    finally:
        server.shutdown()
        server.server_close()


def test_skill_describes_the_dashboard_api_firewall_refusal() -> None:
    # Vercel's firewall rules on www.policyengine.org (tracker 2.3 · 6), observed in
    # production on 2026-11-10: over a limit it answers 429 itself, as text/plain
    # "Too Many Requests", with no Retry-After and no CORS headers.
    text = skill_text()
    for fact in (
        "fixed 60-second windows",
        "Too Many Requests",
        "no `Retry-After`",
        "no CORS headers",
        "`RATE_LIMIT_WAIT_MILLISECONDS`",
    ):
        assert fact in text, fact
    # The merged client (PolicyEngine/policyengine-app-v2#1543, in the first publish)
    # exports RATE_LIMIT_WAIT_MILLISECONDS and does not count 429s as gateway failures.
    assert "DEFAULT_RATE_LIMIT_WAIT_MILLISECONDS" not in text
    assert "count the 429" not in text
    error_rows = [row for row in text.split("## Errors", 1)[1].splitlines() if row.startswith("| 429 ")]
    assert len(error_rows) == 2, "the errors table needs a 429 row for the firewall and one for the load balancer"


def test_dashboard_manifest_lists_the_skill() -> None:
    # tests/pipeline/test_when_to_use_guide.py reads skill IDs from this committed
    # file, so a guide that names the skill fails until the manifest is rebuilt.
    manifest = json.loads((REPO_ROOT / "dashboard" / "src" / "data" / "manifest.json").read_text())
    matches = [entry for entry in manifest["artifacts"] if entry["kind"] == "skill" and entry["id"] == SKILL_NAME]
    assert len(matches) == 1, f"dashboard/src/data/manifest.json lists {SKILL_NAME} {len(matches)} times"
    artifact = matches[0]
    assert artifact["path"] == f"skills/{SKILL_NAME}/SKILL.md"
    assert sorted(artifact["bundles"]) == sorted(BUNDLES_WITH_SKILL)


def test_errors_table_tells_a_refused_server_token_from_a_refused_user_token() -> None:
    # API v1's user routes answer an invalid or expired forwarded
    # PolicyEngine-User-Authorization token with their own 401 and
    # WWW-Authenticate: Bearer error="invalid_token"; the server's own token is
    # refused with a plain "WWW-Authenticate: Bearer".
    errors = skill_text().split("## Errors", 1)[1]
    rows_401 = [row for row in errors.splitlines() if row.startswith("| 401 ")]
    assert len(rows_401) == 2, "the errors table needs a 401 row for each credential"
    assert any('error="invalid_token"' in row and "PolicyEngine-User-Authorization" in row for row in rows_401)
    assert not any("retry once with a new" in row for row in rows_401)


# --- Review round 2 ------------------------------------------------------------


def test_template_modal_wiring_adds_the_module_to_the_image() -> None:
    # Modal 1.0 stopped copying imported local modules into containers, so the
    # image must add the template's module, or the function fails at start.
    token_module = load_token_module()
    docstring = token_module.__doc__
    assert 'add_local_python_source("public_api_token")' in docstring
    assert "image=" in docstring


def test_template_settings_never_print_the_client_secret() -> None:
    token_module = load_token_module()
    settings = make_settings(token_module)
    assert "placeholder-client-secret" not in repr(settings)
    assert settings.client_secret == "placeholder-client-secret"


def test_template_keeps_working_when_the_shared_store_fails() -> None:
    token_module = load_token_module()

    class FailingStore:
        def get(self, key, default=None):  # noqa: ANN001, ANN201
            raise ConnectionError("store unavailable")

        def __setitem__(self, key, value):  # noqa: ANN001
            raise ConnectionError("store unavailable")

    opener = RecordingOpener()
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store=FailingStore(), clock=Clock(), opener=opener
    )
    assert [tokens.access_token() for _ in range(3)] == ["token-1"] * 3
    assert len(opener.token_requests) == 1


def test_template_replaces_a_short_token_halfway_through_its_life() -> None:
    token_module = load_token_module()
    clock = Clock()
    opener = RecordingOpener(token_lifetime_seconds=400)
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store={}, clock=clock, opener=opener
    )
    assert tokens.access_token() == "token-1"
    clock.now += 199
    assert tokens.access_token() == "token-1"
    clock.now += 2
    assert tokens.access_token() == "token-2"


def test_skill_says_the_calculation_returns_only_the_variables_asked_for() -> None:
    # The dashboard API's calculation is API v1's /{country}/calculate, which adds no
    # omitted variables (add_missing=False): outputs are asked for with null.
    text = skill_text()
    assert "/{country}/calculate" in text
    assert "with `null` for the year" in text


# --- Review round 3 ------------------------------------------------------------


def test_template_opener_protocol_takes_the_request_positionally_and_timeout_by_keyword() -> None:
    # urllib's OpenerDirector.open(fullurl, data=None, timeout=...) has data second,
    # so a Protocol with timeout second does not fit it under mypy.
    import inspect

    token_module = load_token_module()
    parameters = inspect.signature(token_module.Opener.open).parameters
    assert parameters["request"].kind is inspect.Parameter.POSITIONAL_ONLY
    assert parameters["timeout"].kind is inspect.Parameter.KEYWORD_ONLY


def test_template_says_how_to_drop_a_revoked_token() -> None:
    assert "revoked" in load_token_module().__doc__


def test_skill_household_example_asks_for_an_output() -> None:
    # The calculation adds no omitted variables, so an example that names no
    # output would get its inputs back unchanged.
    assert "household_net_income: { 2026: null }" in skill_text()


# --- Choosing how a dashboard gets its data ------------------------------------

TOOLS_SKILL_FILE = REPO_ROOT / "skills" / "policyengine-tools" / "SKILL.md"
PLANNER_FILE = REPO_ROOT / "targets" / "claude" / "agents" / "dashboard" / "dashboard-planner.md"
BACKEND_BUILDER_FILE = REPO_ROOT / "targets" / "claude" / "agents" / "dashboard" / "backend-builder.md"
NEW_TOOL_FILE = REPO_ROOT / "targets" / "claude" / "commands" / "new-tool.md"

# The four questions a dashboard builder asks, in order; each place that lists
# them names its outcome with these markers, so the places cannot drift apart.
DATA_PATTERN_ORDER = ("precomputed", "policyengine-api", "new dashboard operation", "custom-modal")
DATA_PATTERN_SECTIONS = (
    (TOOLS_SKILL_FILE, "## Data and backend patterns"),
    (PLANNER_FILE, "### Step 4: Determine Data Pattern"),
    (BACKEND_BUILDER_FILE, "## Backend Selection Priority"),
)
DATA_PATTERN_SECTION_IDS = ("policyengine-tools", "dashboard-planner", "backend-builder")

# www.policyengine.org's firewall limits per IP address a minute (tracker 2.3 · 6).
RATE_LIMITS_PER_MINUTE = {
    "household calculations": 30,
    "economy-comparison reads": 120,
    "policy creations and metadata reads": 300,
}


def single_spaced(text: str) -> str:
    """``text`` with every run of whitespace, line breaks included, as one space."""
    return " ".join(text.split())


def section_text(path: Path, heading: str) -> str:
    """The text under ``heading`` up to the next heading of any level."""
    text = path.read_text()
    assert heading in text, f"{path.relative_to(REPO_ROOT)} has no {heading!r} section"
    after_heading = text.split(heading, 1)[1]
    next_heading = re.search(r"\n#{1,6} ", after_heading)
    return after_heading[: next_heading.start()] if next_heading else after_heading


@pytest.mark.parametrize(("path", "heading"), DATA_PATTERN_SECTIONS, ids=DATA_PATTERN_SECTION_IDS)
def test_data_pattern_questions_come_in_the_same_order(path: Path, heading: str) -> None:
    questions = re.findall(r"^\d+\. (.+)$", section_text(path, heading), re.MULTILINE)
    assert len(questions) == len(DATA_PATTERN_ORDER), questions
    for question, marker in zip(questions, DATA_PATTERN_ORDER):
        assert marker in question, (marker, question)


@pytest.mark.parametrize(("path", "heading"), DATA_PATTERN_SECTIONS, ids=DATA_PATTERN_SECTION_IDS)
def test_model_version_and_rate_limits_are_not_reasons_for_an_own_backend(path: Path, heading: str) -> None:
    # The Public API's model lagging the newest country package is fixed by
    # updating the Public API, not by each dashboard running its own model.
    not_reasons = single_spaced(section_text(path, heading)).split("**Not reasons for", 1)
    assert len(not_reasons) == 2, "the section must say what is not a reason for an own backend"
    for topic in ("model", "rate limit"):
        assert topic in not_reasons[1], topic


def test_new_tool_says_model_version_is_no_reason_for_pattern_c() -> None:
    prefer_b = NEW_TOOL_FILE.read_text().split("**Prefer Pattern B**", 1)[1].split("\n\n", 1)[0]
    prefer_b = single_spaced(prefer_b.replace("\n> ", "\n"))
    assert "model" in prefer_b
    assert "Data and backend patterns" in prefer_b


def test_skill_keeps_pages_at_half_of_each_rate_limit() -> None:
    text = single_spaced(skill_text())
    for name, limit in RATE_LIMITS_PER_MINUTE.items():
        assert f"{limit} {name}" in text, f"the {name} limit is not stated"
        assert f"{limit // 2} {name}" in text, f"no budget of {limit // 2} {name} a minute"
    # compareEconomy reads every 5 seconds, so each running comparison is
    # 12 reads a minute; five at once is the 60-read budget.
    assert "12 reads a minute" in text
    assert "at most five comparisons at once" in text


def test_new_operation_section_says_when_to_ask_and_suggests_no_client() -> None:
    text = single_spaced(section_text(SKILL_FILE, "## Asking for a new dashboard operation"))
    assert "used unchanged" in text
    assert "own backend" in text
    assert "with its own client" not in text


def test_route_table_has_new_dashboard_backends_run_policyengine_themselves() -> None:
    table = section_text(SKILL_FILE, "## Which route to use")
    rows = [row for row in table.splitlines() if row.startswith("| A dashboard's own backend")]
    assert len(rows) == 1, rows
    assert "`policyengine`" in rows[0] and "own process" in rows[0], rows[0]


def test_planner_household_page_calculates_custom_inputs_through_the_dashboard_api() -> None:
    planner = PLANNER_FILE.read_text()
    household_page = single_spaced(planner.split("**Household page**", 1)[1].split("**Standard chrome", 1)[0])
    assert "spawn-and-poll" not in household_page
    assert "@policyengine/api-client" in household_page
    assert "`axes`" in household_page


def test_data_pattern_rule_fixes_gaps_in_the_model_or_the_public_api_first() -> None:
    # A structural reform becomes a contributed reform in the country package,
    # switched on by a parameter, so the dashboard API can run it once the
    # Public API's model includes it; a general gap is a change to the Public API.
    patterns = single_spaced(section_text(TOOLS_SKILL_FILE, "## Data and backend patterns"))
    assert "contributed reform" in patterns
    assert "`gov.contrib" in patterns
    assert "a change to the Public API" in patterns


def test_a_server_for_other_work_keeps_calculations_on_the_dashboard_api() -> None:
    # ACA-Calc's LLM explanation or an emailed CSV needs a server, but not one
    # that runs PolicyEngine.
    patterns = single_spaced(section_text(TOOLS_SKILL_FILE, "## Data and backend patterns"))
    assert "other than PolicyEngine results" in patterns
    assert "doesn't move its PolicyEngine calculations off the dashboard API" in patterns


def test_a_feature_over_the_budget_is_precomputed_before_it_gets_a_backend() -> None:
    text = single_spaced(skill_text())
    over_budget = text.split("can't fit this budget", 1)
    assert len(over_budget) == 2, "the skill must say what to do with a feature over the budget"
    advice = over_budget[1].split(". ", 1)[0]
    assert "precompute" in advice and "own backend" in advice, advice
    assert advice.index("precompute") < advice.index("own backend"), advice
