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

BROWSER_LANGUAGES = {"ts", "tsx", "js", "jsx", "javascript", "typescript"}
PUBLIC_API_HOST = re.compile(r"api\.policyengine\.org|policyengine-api[a-z0-9-]*\.[a-z0-9.-]*run\.app")
# A credential-looking name with a prefix that bundlers put into browser code.
PUBLIC_PREFIX_CREDENTIAL = re.compile(
    r"\b(?:NEXT_PUBLIC|VITE)_[A-Z0-9_]*(?:AUTH0|SECRET|TOKEN|CLIENT|CREDENTIAL|POLICYENGINE_API)[A-Z0-9_]*"
)
FENCE = re.compile(r"^```([A-Za-z0-9_+-]*)\n(.*?)^```", re.DOTALL | re.MULTILINE)


def skill_text() -> str:
    assert SKILL_FILE.is_file(), f"{SKILL_FILE.relative_to(REPO_ROOT)} is missing"
    return SKILL_FILE.read_text()


def skill_frontmatter() -> dict:
    text = skill_text()
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md has no YAML frontmatter"
    return yaml.safe_load(match.group(1))


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    return [(language.lower(), body) for language, body in FENCE.findall(text)]


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


def test_no_browser_language_example_names_a_public_api_host() -> None:
    offenders = [
        body
        for language, body in fenced_blocks(skill_text())
        if language in BROWSER_LANGUAGES and PUBLIC_API_HOST.search(body)
    ]
    assert offenders == []


def test_skill_never_puts_a_credential_in_a_public_prefix_variable() -> None:
    assert PUBLIC_PREFIX_CREDENTIAL.findall(skill_text()) == []


def test_public_prefix_credential_pattern_catches_bundled_names() -> None:
    for unsafe in (
        "NEXT_PUBLIC_POLICYENGINE_API_AUTH0_CLIENT_SECRET",
        "VITE_AUTH0_CLIENT_ID",
        "NEXT_PUBLIC_API_TOKEN",
        "VITE_POLICYENGINE_API_URL",
    ):
        assert PUBLIC_PREFIX_CREDENTIAL.search(unsafe), unsafe
    for safe in ("NEXT_PUBLIC_*", "VITE_*", "NEXT_PUBLIC_MODAL_URL", "POLICYENGINE_API_AUTH0_CLIENT_SECRET"):
        assert not PUBLIC_PREFIX_CREDENTIAL.search(safe), safe


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


def test_template_retries_a_refused_request_once_with_a_new_token() -> None:
    token_module = load_token_module()
    opener = RecordingOpener()
    opener.refuse_next_api_requests = 1
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store={}, clock=Clock(), opener=opener
    )
    answer = token_module.call_public_api(tokens, "POST", "/us/calculate", {"household": {}})
    assert answer == {"status": "ok", "message": None, "result": {}}
    assert [header for _, _, header in opener.api_requests] == [
        "Bearer token-1",
        "Bearer token-2",
    ]


def test_template_stops_after_a_second_refusal() -> None:
    token_module = load_token_module()
    opener = RecordingOpener()
    opener.refuse_next_api_requests = 2
    tokens = token_module.PublicApiTokenProvider(
        make_settings(token_module), shared_store={}, clock=Clock(), opener=opener
    )
    with pytest.raises(urllib.error.HTTPError) as refusal:
        token_module.call_public_api(tokens, "GET", "/us/metadata")
    assert refusal.value.code == 401
    assert len(opener.api_requests) == 2


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
