"""Tests for skills/policyengine-api-access/scripts/check_public_api_access.py.

Each test writes a small dashboard repository into a temporary directory and
scans it. The check must report browser code that names the Public API
(api.policyengine.org or its Cloud Run addresses) and Public API addresses or
credentials in variables that bundlers copy into pages, and must stay quiet
on server code: Python backends, Next.js route handlers and server
components, scripts, Vercel functions and tests.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "policyengine-api-access"
SCRIPT = SKILL_DIR / "scripts" / "check_public_api_access.py"
WORKFLOW_TEMPLATE = SKILL_DIR / "templates" / "public-api-checks.yml"

NEXT_PACKAGE = json.dumps({"dependencies": {"next": "15.0.0", "react": "19.0.0"}})
VITE_PACKAGE = json.dumps({"devDependencies": {"vite": "6.0.0"}, "dependencies": {"react": "19.0.0"}})
NEXT_TSCONFIG = json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"]}}})


def load_checker():
    assert SCRIPT.is_file(), f"{SCRIPT.relative_to(REPO_ROOT)} is missing"
    spec = importlib.util.spec_from_file_location("check_public_api_access", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_public_api_access"] = module
    spec.loader.exec_module(module)
    return module


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


def findings_in(root: Path) -> list[tuple[str, str, str]]:
    """(rule, severity, path) for each finding, sorted."""
    findings, _ = load_checker().scan(root)
    return sorted((finding.rule, finding.severity, finding.path.as_posix()) for finding in findings)


def vite_app(**files: str) -> dict[str, str]:
    return {"package.json": VITE_PACKAGE, "index.html": "<div id=root></div>", **files}


def next_app(prefix: str = "", **files: str) -> dict[str, str]:
    base = {"package.json": NEXT_PACKAGE, "next.config.mjs": "export default {};\n", "tsconfig.json": NEXT_TSCONFIG}
    return {f"{prefix}{name}": content for name, content in {**base, **files}.items()}


# --- PA1: browser code names the Public API ------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "const BASE = 'https://api.policyengine.org';\n",
        'fetch("https://api.policyengine.org/us/calculate", { method: "POST" });\n',
        "const url = `https://API.PolicyEngine.org/${country}/metadata`;\n",
        "const url = '//api.policyengine.org/us/metadata';\n",
        "const url = 'https://policyengine-api-43j3ckhyaa-uc.a.run.app/us/calculate';\n",
        "const url = 'https://policyengine-api-staging-43j3ckhyaa-uc.a.run.app';\n",
        "const url = 'https://candidate---policyengine-api-43j3ckhyaa-uc.a.run.app';\n",
        "const url = 'https://policyengine-api-123456789012.us-central1.run.app';\n",
        "const url = 'https://api.' +\n  'policyengine.org/us/calculate';\n",
        "const url = \"https://api.policyengine\" + '.org';\n",
        "const host = ['api', 'policyengine', 'org'].join('.');\n",
        "const DOMAIN = 'policyengine.org';\nfetch(`https://api.${DOMAIN}/us/calculate`);\n",
        "const SUBDOMAIN = 'api';\nfetch(`https://${SUBDOMAIN}.policyengine.org/us/calculate`);\n",
    ],
)
def test_vite_browser_code_naming_the_public_api_is_an_error(tmp_path: Path, source: str) -> None:
    write_tree(tmp_path, vite_app(**{"src/api/policyengine.ts": source}))
    assert findings_in(tmp_path) == [("PA1", "error", "src/api/policyengine.ts")]


def test_next_module_imported_by_a_client_component_is_browser_code(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        next_app(
            "frontend/",
            **{
                "app/page.tsx": "import Calculator from '@/components/Calculator';\nexport default function Page() { return <Calculator />; }\n",
                "components/Calculator.tsx": "'use client';\nimport { calculate } from '../lib/api';\nexport default function Calculator() { return null; }\n",
                "lib/api.ts": "import { HOST } from '@/lib/constants';\nexport const calculate = () => fetch(`${HOST}/us/calculate`);\n",
                "lib/constants.ts": "export const HOST = 'https://api.policyengine.org';\n",
            },
        ),
    )
    assert findings_in(tmp_path) == [("PA1", "error", "frontend/lib/constants.ts")]


def test_next_module_shared_by_server_and_client_code_is_browser_code(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        next_app(
            **{
                "app/page.tsx": "import { HOST } from '@/lib/host';\nimport Chart from './Chart';\nexport default function Page() { return <Chart />; }\n",
                "app/Chart.tsx": '"use client";\nimport { HOST } from "@/lib/host";\nexport default function Chart() { return null; }\n',
                "lib/host.ts": "export const HOST = 'https://api.policyengine.org';\n",
            },
        ),
    )
    assert findings_in(tmp_path) == [("PA1", "error", "lib/host.ts")]


def test_next_module_nothing_imports_counts_as_browser_code(tmp_path: Path) -> None:
    write_tree(tmp_path, next_app(**{"lib/unused.ts": "export const HOST = 'https://api.policyengine.org';\n"}))
    assert findings_in(tmp_path) == [("PA1", "error", "lib/unused.ts")]


def test_pages_router_page_is_browser_code(tmp_path: Path) -> None:
    write_tree(tmp_path, next_app(**{"pages/index.tsx": "fetch('https://api.policyengine.org/us/metadata');\n"}))
    assert findings_in(tmp_path) == [("PA1", "error", "pages/index.tsx")]


@pytest.mark.parametrize("name", ["index.html", "public/embed.html", "src/App.vue", "src/App.svelte", "src/main.jsx"])
def test_other_browser_files_are_checked(tmp_path: Path, name: str) -> None:
    write_tree(tmp_path, vite_app(**{name: "<script>fetch('https://api.policyengine.org/us/metadata')</script>\n"}))
    assert findings_in(tmp_path) == [("PA1", "error", name)]


def test_static_site_without_package_json_is_browser_code(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.js": "fetch('https://api.policyengine.org/uk/metadata');\n"})
    assert findings_in(tmp_path) == [("PA1", "error", "app.js")]


# --- Server code and other files the check leaves alone ----------------------


@pytest.mark.parametrize(
    "files",
    [
        {"backend/app/api/policyengine_client.py": "BASE = 'https://api.policyengine.org'\n"},
        {"backend/uk.py": "requests.post('https://api.policyengine.org/uk/calculate')\n"},
        {"scripts/precompute.mjs": "await fetch('https://api.policyengine.org/us/calculate');\n"},
        {"frontend/scripts/fetch-metadata.js": "fetch('https://api.policyengine.org/us/metadata');\n",
         "frontend/package.json": VITE_PACKAGE},
        {"api/calculate.js": "export default () => fetch('https://api.policyengine.org/us/calculate');\n"},
        {"server/index.ts": "fetch('https://api.policyengine.org/us/metadata');\n"},
        {"src/lib/api.test.ts": "expect(url).toBe('https://api.policyengine.org/us/calculate');\n"},
        {"src/__tests__/live.ts": "fetch('https://api.policyengine.org/us/metadata');\n"},
        {"tests/live.spec.js": "fetch('https://api.policyengine.org/us/metadata');\n"},
        {"src/lib/api.ts": "// This used to call https://api.policyengine.org directly.\nexport {};\n"},
        {"src/lib/api.ts": "/**\n * Replaces `api.policyengine.org/us/calculate`.\n */\nexport {};\n"},
        {"src/lib/api.ts": "fetch('https://household.api.policyengine.org/us/calculate');\n"},
        {"src/lib/api.ts": "fetch('https://v2.api.policyengine.org/households');\n"},
        {"src/lib/api.ts": "fetch('https://www.policyengine.org/api/household/calculate');\n"},
        {"src/lib/api.ts": "fetch('https://policyengine-household-api-abc123defg-uc.a.run.app/us/calculate');\n"},
        {"README.md": "The dashboard used to call https://api.policyengine.org.\n"},
        {"node_modules/old/index.js": "fetch('https://api.policyengine.org');\n"},
        {"dist/assets/index.js": "fetch('https://api.policyengine.org');\n"},
        {".next/static/chunk.js": "fetch('https://api.policyengine.org');\n"},
        {"out/index.html": "<script>fetch('https://api.policyengine.org')</script>\n"},
        {".vite/deps/chunk.js": "fetch('https://api.policyengine.org');\n"},
        {"src/server/handler.server.ts": "fetch('https://api.policyengine.org/us/metadata');\n"},
    ],
)
def test_server_code_tests_comments_and_other_hosts_are_not_reported(tmp_path: Path, files: dict[str, str]) -> None:
    write_tree(tmp_path, vite_app(**files))
    assert findings_in(tmp_path) == []


def test_next_server_code_is_not_reported(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        next_app(
            **{
                "app/page.tsx": "import { loadMetadata } from '@/lib/metadata';\nexport default async function Page() { await loadMetadata(); return null; }\n",
                "lib/metadata.ts": "export const loadMetadata = () => fetch('https://api.policyengine.org/us/metadata');\n",
                "app/api/calculate/route.ts": "export async function POST() { return fetch('https://api.policyengine.org/us/calculate'); }\n",
                "app/actions.ts": "'use server';\nexport async function run() { return fetch('https://api.policyengine.org/us/policy'); }\n",
                "app/Form.tsx": "'use client';\nimport { run } from './actions';\nimport { token } from '@/lib/token';\nexport default function Form() { return null; }\n",
                "lib/token.ts": "import 'server-only';\nexport const token = () => fetch('https://api.policyengine.org/health');\n",
                "middleware.ts": "export function middleware() { return fetch('https://api.policyengine.org/health'); }\n",
                "pages/api/legacy.ts": "export default () => fetch('https://api.policyengine.org/us/metadata');\n",
            },
        ),
    )
    assert findings_in(tmp_path) == []


def test_api_directory_in_a_next_project_is_not_assumed_to_be_server_code(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        next_app(
            **{
                "components/Calculator.tsx": "'use client';\nimport { calculate } from '../api/client';\nexport default function Calculator() { return null; }\n",
                "api/client.ts": "export const calculate = () => fetch('https://api.policyengine.org/us/calculate');\n",
            },
        ),
    )
    assert findings_in(tmp_path) == [("PA1", "error", "api/client.ts")]


# --- PA2: a Public API address or credential in a variable pages receive ------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        (".env.production", "NEXT_PUBLIC_API_URL=https://api.policyengine.org\n"),
        (".env", "VITE_API_BASE='https://policyengine-api-staging-43j3ckhyaa-uc.a.run.app'\n"),
        (".env.local", "VITE_POLICYENGINE_API_AUTH0_CLIENT_SECRET=placeholder\n"),
        (".env", "NEXT_PUBLIC_AUTH0_CLIENT_SECRET=placeholder\n"),
        (".env", "VITE_AUTH0_DOMAIN=policyengine-api.uk.auth0.com\n"),
        (".env", "NEXT_PUBLIC_API_KEY=eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4QGNsaWVudHMifQ.c2lnbmF0dXJl\n"),
        (".env", "REACT_APP_PE_API_TOKEN=placeholder\n"),
        ("src/config.ts", "export const token = import.meta.env.VITE_POLICYENGINE_API_TOKEN;\n"),
        ("app/server.ts", "const secret = process.env.NEXT_PUBLIC_PUBLIC_API_SECRET;\n"),
        (".github/workflows/deploy.yml", "env:\n  NEXT_PUBLIC_POLICYENGINE_API_URL: ${{ vars.API_URL }}\n"),
        (".github/workflows/deploy.yml", "env:\n  VITE_API_URL: https://api.policyengine.org\n"),
        ("vercel.json", '{"build": {"env": {"NEXT_PUBLIC_API_URL": "https://api.policyengine.org"}}}\n'),
        ("next.config.mjs", "export default { env: { POLICYENGINE_API_AUTH0_CLIENT_SECRET: process.env.POLICYENGINE_API_AUTH0_CLIENT_SECRET } };\n"),
        ("vite.config.ts", "export default { define: { SECRET: JSON.stringify(process.env.MODAL_CLIENT_SECRET) } };\n"),
        ("next.config.js", "module.exports = { env: { NEXT_PUBLIC_TOKEN: process.env.POLICYENGINE_API_AUTH0_CLIENT_ID } };\n"),
        ("Dockerfile", "ARG NEXT_PUBLIC_POLICYENGINE_API_AUTH0_CLIENT_ID\n"),
    ],
)
def test_public_api_address_or_credential_in_a_bundled_variable_is_an_error(
    tmp_path: Path, name: str, content: str
) -> None:
    write_tree(tmp_path, vite_app(**{name: content}))
    assert ("PA2", "error", name) in findings_in(tmp_path)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        (".env", "NEXT_PUBLIC_MAPBOX_TOKEN=pk.placeholder\n"),
        (".env", "NEXT_PUBLIC_API_URL=https://policyengine--my-tool-fastapi-app.modal.run\n"),
        (".env", "NEXT_PUBLIC_MODAL_CPID_URL=https://policyengine--cpid.modal.run\n"),
        (".env.example", "POLICYENGINE_API_URL=https://api.policyengine.org\nPOLICYENGINE_API_AUTH0_CLIENT_SECRET=\n"),
        (".env", "VITE_AUTH0_DOMAIN=auth.policyengine.org\nVITE_AUTH0_CLIENT_ID=placeholder\n"),
        (".env", "# NEXT_PUBLIC_API_URL=https://api.policyengine.org is no longer used\n"),
        (".github/workflows/ci.yml", "env:\n  POLICYENGINE_API_AUTH0_CLIENT_SECRET: ${{ secrets.POLICYENGINE_API_AUTH0_CLIENT_SECRET }}\n"),
        ("README.md", "Never set NEXT_PUBLIC_POLICYENGINE_API_AUTH0_CLIENT_SECRET.\n"),
        ("backend/settings.py", "SECRET = os.environ['POLICYENGINE_API_AUTH0_CLIENT_SECRET']\n"),
        ("app/api/route.ts", "const secret = process.env.POLICYENGINE_API_AUTH0_CLIENT_SECRET;\n"),
    ],
)
def test_ordinary_public_variables_and_server_secrets_are_not_reported(
    tmp_path: Path, name: str, content: str
) -> None:
    write_tree(tmp_path, vite_app(**{name: content}))
    assert findings_in(tmp_path) == []


# --- PA3 and PA4: warnings ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("vercel.json", '{"rewrites": [{"source": "/pe/:path*", "destination": "https://api.policyengine.org/:path*"}]}\n'),
        ("next.config.mjs", "export default { async rewrites() { return [{ source: '/pe/:p*', destination: 'https://api.policyengine.org/:p*' }]; } };\n"),
        ("netlify.toml", '[[redirects]]\nfrom = "/pe/*"\nto = "https://api.policyengine.org/:splat"\n'),
    ],
)
def test_build_or_deploy_config_naming_the_public_api_is_a_warning(tmp_path: Path, name: str, content: str) -> None:
    write_tree(tmp_path, vite_app(**{name: content}))
    assert findings_in(tmp_path) == [("PA3", "warning", name)]


@pytest.mark.parametrize(
    "source",
    [
        "fetch(`${import.meta.env.VITE_API_URL}/${country}/economy/${policyId}/over/${baselineId}?region=us`);\n",
        "fetch(BASE + '/us/calculate-full', { method: 'POST' });\n",
    ],
)
def test_browser_code_building_a_public_api_path_is_a_warning(tmp_path: Path, source: str) -> None:
    write_tree(tmp_path, vite_app(**{"src/api.ts": source}))
    assert findings_in(tmp_path) == [("PA4", "warning", "src/api.ts")]


def test_server_code_building_a_public_api_path_is_not_reported(tmp_path: Path) -> None:
    write_tree(tmp_path, vite_app(**{"scripts/compare.mjs": "fetch(`${BASE}/us/economy/${reform}/over/2`);\n"}))
    assert findings_in(tmp_path) == []


# --- Declared exceptions ---------------------------------------------------------


def test_declared_exception_silences_one_rule_and_is_listed(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        vite_app(
            **{
                "src/Footer.tsx": (
                    "// public-api-ok: PA1 link text naming the old address in the changelog page\n"
                    "export const note = 'Results used to come from api.policyengine.org';\n"
                ),
            }
        ),
    )
    findings, declarations = load_checker().scan(tmp_path)
    assert findings == []
    assert [(declaration.rule, declaration.path.as_posix(), declaration.line) for declaration in declarations] == [
        ("PA1", "src/Footer.tsx", 2)
    ]


def test_declaration_without_a_reason_does_not_count(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        vite_app(**{"src/api.ts": "const BASE = 'https://api.policyengine.org'; // public-api-ok: PA1\n"}),
    )
    findings, declarations = load_checker().scan(tmp_path)
    assert [(finding.rule, finding.severity) for finding in findings] == [("PA1", "error")]
    assert "no reason" in findings[0].message
    assert declarations == []


# --- Command line, dependencies and the workflow template --------------------------


def run_checker(*arguments: str) -> subprocess.CompletedProcess:
    assert SCRIPT.is_file(), f"{SCRIPT.relative_to(REPO_ROOT)} is missing"
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False)


def test_command_line_exit_status_and_output(tmp_path: Path) -> None:
    clean = write_tree(tmp_path / "clean", vite_app(**{"src/api.ts": "export {};\n"}))
    failing = write_tree(tmp_path / "failing", vite_app(**{"src/api.ts": "const BASE = 'https://api.policyengine.org';\n"}))
    warning_only = write_tree(
        tmp_path / "warning", vite_app(**{"vercel.json": '{"rewrites": [{"destination": "https://api.policyengine.org/:p*"}]}\n'})
    )

    clean_run = run_checker(str(clean))
    assert clean_run.returncode == 0, clean_run.stdout + clean_run.stderr
    assert clean_run.stdout.strip().endswith("0 errors, 0 warnings, 0 declared exceptions")

    failing_run = run_checker(str(failing))
    assert failing_run.returncode == 1
    assert failing_run.stdout.startswith("error PA1 src/api.ts:1: ")

    assert run_checker(str(warning_only)).returncode == 0
    assert run_checker(str(warning_only), "--strict").returncode == 1
    assert run_checker(str(tmp_path / "missing")).returncode == 2


def test_checker_uses_only_the_standard_library() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT.relative_to(REPO_ROOT)} is missing"
    tree = ast.parse(SCRIPT.read_text())
    imported = {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported - set(sys.stdlib_module_names)


def test_workflow_template_runs_a_pinned_copy_with_read_only_permissions() -> None:
    assert WORKFLOW_TEMPLATE.is_file(), f"{WORKFLOW_TEMPLATE.relative_to(REPO_ROOT)} is missing"
    import yaml

    workflow = yaml.safe_load(WORKFLOW_TEMPLATE.read_text())
    assert workflow["permissions"] == {"contents": "read"}
    # PyYAML reads the bare key `on` as True.
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers
    (job,) = workflow["jobs"].values()
    check_step = next(step for step in job["steps"] if "run" in step and "check_public_api_access.py" in step["run"])
    assert check_step["env"] == {"CHECKER_COMMIT": "CHECKER_COMMIT_SHA"}
    assert (
        "https://raw.githubusercontent.com/PolicyEngine/policyengine-skills/${CHECKER_COMMIT}/"
        "skills/policyengine-api-access/scripts/check_public_api_access.py" in check_step["run"]
    )
    assert "python3 /tmp/check_public_api_access.py ." in check_step["run"]


def test_skill_tells_dashboards_how_to_add_the_check() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text()
    section = text.split("## Check it in CI", 1)
    assert len(section) == 2, "SKILL.md has no '## Check it in CI' section"
    for expected in ("scripts/check_public_api_access.py", "templates/public-api-checks.yml", "CHECKER_COMMIT", "public-api-ok"):
        assert expected in section[1], expected
    for rule in ("PA1", "PA2", "PA3", "PA4"):
        assert f"| {rule} |" in section[1], rule


@pytest.mark.parametrize(
    "relative_path",
    ["targets/claude/agents/dashboard/dashboard-scaffold.md", "targets/claude/commands/new-tool.md"],
)
def test_new_dashboards_get_the_check_in_their_ci(relative_path: str) -> None:
    text = (REPO_ROOT / relative_path).read_text()
    assert "skills/policyengine-api-access/scripts/check_public_api_access.py" in text


# --- Inputs found while running the check on PolicyEngine's dashboards ---------------


def test_config_files_with_urls_in_strings_still_parse(tmp_path: Path) -> None:
    package = json.dumps({"homepage": "https://example.org/tool", "dependencies": {"next": "15.0.0"}})
    tsconfig = (
        '{\n  "$schema": "https://json.schemastore.org/tsconfig", // the schema\n'
        '  "compilerOptions": {"baseUrl": ".", "paths": {"#lib/*": ["./src/lib/*"]},},\n}\n'
    )
    write_tree(
        tmp_path,
        {
            "package.json": package,
            "tsconfig.json": tsconfig,
            "src/app/page.tsx": "import { load } from '#lib/load';\nexport default function Page() { return null; }\n",
            "src/lib/load.ts": "export const load = () => fetch('https://api.policyengine.org/us/metadata');\n",
        },
    )
    # A Next.js project whose server component alone reaches the module: server code.
    assert findings_in(tmp_path) == []


def test_large_files_with_many_comments_scan_quickly(tmp_path: Path) -> None:
    leading_comments = "".join(f"/* block {number} */\n// line {number}\n" for number in range(300))
    prose = " ".join(f"import word{number} and more words" for number in range(3000))
    write_tree(
        tmp_path,
        next_app(**{"lib/data.ts": f"{leading_comments}export const text = `{prose}`;\n"}),
    )
    script_run = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True, timeout=20, check=False
    )
    assert script_run.returncode == 0, script_run.stdout
