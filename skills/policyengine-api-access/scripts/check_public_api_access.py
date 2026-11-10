#!/usr/bin/env python3
"""Flag browser code in a dashboard's repository that reaches the PolicyEngine Public API directly.

Reads files only; changes nothing and calls no API.

    python3 check_public_api_access.py [REPO_DIR] [--strict] [--explain]

Exit status: 0 when there are no errors, 1 when there are errors (warnings also count
with --strict), 2 for bad input. --explain also prints how each code file was classified.

The Public API (api.policyengine.org) serves only PolicyEngine's servers. Pages call
www.policyengine.org's dashboard API through @policyengine/api-client, and servers send
their own credential (the policyengine-api-access skill). Rules:

    PA1 error    browser code names the Public API: api.policyengine.org or one of its Cloud
                 Run addresses, also when the host is built from string parts
    PA2 error    a NEXT_PUBLIC_, VITE_, REACT_APP_, GATSBY_ or EXPO_PUBLIC_ variable, which
                 bundlers copy into pages, holds or is named for a Public API address or
                 credential; or build config copies a client secret into the bundle
    PA3 warning  deploy or build config names the Public API (a rewrite that forwards pages'
                 requests without a credential, or an address inlined into the bundle)
    PA4 warning  browser code builds a path only the Public API serves
                 (/{country}/economy/{policy}/over/{baseline}, /{country}/calculate-full)

Browser code is every JavaScript, TypeScript, Vue, Svelte, Astro and HTML file, except:
- server code: top-level backend/, server/, scripts/, functions/ and similar directories;
  api/ at the root of a project that is not Next.js (Vercel functions); Next.js route
  handlers, pages/api/, middleware, instrumentation and pages/_document; *.server.* files;
  modules that start with "use server" or import "server-only"; and, in a Next.js project,
  modules reached only from server components (the App Router's default), never from a
  "use client" module or a Pages Router page. A Next.js module nothing imports counts as
  browser code;
- tests, stories, build output, dependencies and comment-only lines.
Python is never browser code.

A finding that is deliberate is declared on its line, the line above or the comment block
directly above, with a reason:
    // public-api-ok: PA1 the methodology note names the address the figures came from
A declaration without a reason (or one starting TODO) does not count. Every accepted
declaration is printed, so reviewers see each exception.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

SKIPPED_DIRECTORIES = {
    ".git", "node_modules", ".next", "out", "dist", "build", ".vercel", ".turbo", ".cache", "coverage",
    ".venv", "venv", "__pycache__", ".vite", ".svelte-kit", ".nuxt", ".output", "storybook-static",
}
BROWSER_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro",
                    ".html", ".htm"}
MODULE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte")
CONFIG_SUFFIXES = {".json", ".yml", ".yaml", ".toml", ".sh", ".bash"}
LOCK_FILES = {"package-lock.json", "bun.lock", "bun.lockb", "yarn.lock", "pnpm-lock.yaml"}
DEPLOY_CONFIG_FILES = {"vercel.json", "now.json", "netlify.toml", "_redirects"}
BUILD_CONFIG_FILE = re.compile(r"^[\w.-]+\.config\.(?:js|mjs|cjs|ts|mts|cts)$")
BUNDLER_CONFIG_FILE = re.compile(r"^(?:next|vite|astro|nuxt|svelte|remix|webpack|rollup)\.config\.")
# Directories whose code runs on a server, when they sit at the top of the repository or of
# a project (a directory with a package.json).
SERVER_DIRECTORIES = {"backend", "server", "scripts", "functions", "lambda", "serverless", "supabase", "netlify"}
TEST_DIRECTORIES = {"__tests__", "tests", "test", "e2e", "cypress", "playwright", "__mocks__"}
TEST_FILE = re.compile(r"\.(?:test|spec|stories)\.[a-z]+$|^(?:setupTests|vitest\.setup|jest\.setup)\.")

# The Public API only: not household.api.policyengine.org (the household API),
# v2.api.policyengine.org (the v2 alpha) or other services' Cloud Run addresses.
PUBLIC_API_HOST = re.compile(
    r"(?<![\w.-])api\.policyengine\.org(?![\w-])"
    r"|(?<![\w.-])(?:[a-z0-9-]+---)?policyengine-api(?:-staging)?-[a-z0-9]+(?:-[a-z]{2,4})?\.a\.run\.app"
    r"|(?<![\w.-])policyengine-api(?:-staging)?-[0-9]+\.[a-z0-9-]+\.run\.app",
    re.IGNORECASE,
)
# Hosts built from parts: 'https://api.' + 'policyengine.org' is joined before matching.
STRING_JOIN = re.compile(r"[\"'`]\s*\+\s*[\"'`]")
ARRAY_JOIN = re.compile(r"\[\s*([\"'`])api\1\s*,\s*([\"'`])policyengine\2\s*,\s*([\"'`])org\3\s*\]", re.IGNORECASE)
TEMPLATE_API_SUBDOMAIN = re.compile(r"(?<![\w.-])api\.\$\{", re.IGNORECASE)
DOMAIN_LITERAL = re.compile(r"([\"'`])\.?policyengine\.org\1", re.IGNORECASE)
TEMPLATE_DOMAIN = re.compile(r"\$\{[^}`\n]+\}\.policyengine\.org(?![\w-])", re.IGNORECASE)
API_LITERAL = re.compile(r"([\"'`])api\1")
CALCULATE_FULL_PATH = re.compile(r"/calculate-full(?![\w-])")
ECONOMY_SEGMENT = re.compile(r"/economy/")
OVER_SEGMENT = re.compile(r"/over/")

PUBLIC_VARIABLE = re.compile(r"\b(?:NEXT_PUBLIC|VITE|REACT_APP|GATSBY|EXPO_PUBLIC)_([A-Z0-9_]+)")
PUBLIC_ASSIGNMENT = re.compile(
    r"\b((?:NEXT_PUBLIC|VITE|REACT_APP|GATSBY|EXPO_PUBLIC)_([A-Z0-9_]+))[\"']?\s*(?:\?=|:=|=|:)\s*(.*)$"
)
NAME_SECRET = re.compile(r"SECRET|PASSWORD|PRIVATE_KEY|CREDENTIAL")
NAME_PUBLIC_API = re.compile(r"(?:^|_)(?:POLICYENGINE_API|PE_API|PUBLIC_API|API_V1)(?:_|$)")
NAME_AUTH0_TOKEN = re.compile(r"AUTH0\w*(?:TOKEN|M2M)|(?:TOKEN|M2M)\w*AUTH0")
SERVER_TENANT = re.compile(r"(?<![\w.-])policyengine-api(?:-staging)?\.uk\.auth0\.com", re.IGNORECASE)
JSON_WEB_TOKEN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")
SERVER_CREDENTIAL_REFERENCE = re.compile(r"\bPOLICYENGINE_API_AUTH0_[A-Z_]+|\b[A-Z0-9_]*CLIENT_SECRET\b")

SERVER_ONLY_IMPORT = re.compile(r"""\bimport\s+(["'])server-only\1""")
# Every pattern below scans in linear time: "... from '<module>'", a side-effect import,
# a dynamic import and require(). A "from '<x>'" that is not an import only adds a
# module to the graph when <x> resolves to a file, which counts more code as browser code.
IMPORT_SPECIFIER = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*|\bimport\s*\(\s*|\brequire\s*\(\s*)(["'])([^"'\n]{1,300})\1"""
)
DECLARATION = re.compile(r"public-api-ok:\s*(PA[1-4])\b(.*)$")
RULES = ("PA1", "PA2", "PA3", "PA4")
COMMENT_PREFIXES = {
    "script": ("//", "/*", "*", "<!--"),
    "hash": ("#",),
    "none": (),
}

PA1_MESSAGE = ("browser code names the Public API ({host}). Pages call www.policyengine.org's dashboard API "
               "through @policyengine/api-client instead (policyengine-api-access skill)")
PA1_PARTS_MESSAGE = ("browser code builds the Public API's address from parts. Pages call www.policyengine.org's "
                     "dashboard API through @policyengine/api-client instead (policyengine-api-access skill)")
PA2_NAME_MESSAGE = ("{name}: bundlers copy {prefix}_ variables into the page, so the name must not hold a Public "
                    "API credential or address. Keep server credentials in server-only variables")
PA2_VALUE_MESSAGE = "{name} is set to {what}, and bundlers copy {prefix}_ variables into the page"
PA2_CONFIG_MESSAGE = ("build config reads {reference}; next.config env and Vite define copy what they read into "
                      "the page. Read it only in server code")
PA3_MESSAGE = ("deploy or build config names the Public API ({host}): a rewrite forwards pages' requests without "
               "a server credential, and env or define copies the address into the page")
PA4_MESSAGE = ("browser code builds a path only the Public API serves ({path}); pages call the dashboard API "
               "through @policyengine/api-client instead")


@dataclass
class Finding:
    rule: str
    severity: str
    path: Path
    line: int
    message: str


@dataclass
class Declaration:
    rule: str
    path: Path
    line: int
    reason: str


@dataclass
class Project:
    root: Path
    is_next: bool
    base_url: Path | None = None
    aliases: list[tuple[str, list[Path]]] = field(default_factory=list)


def severity_of(rule: str) -> str:
    return "error" if rule in {"PA1", "PA2"} else "warning"


def is_skipped_directory(name: str) -> bool:
    return name in SKIPPED_DIRECTORIES


def is_test_file(relative_path: Path) -> bool:
    return any(part in TEST_DIRECTORIES for part in relative_path.parts[:-1]) or bool(
        TEST_FILE.search(relative_path.name)
    )


def is_env_file(name: str) -> bool:
    return name == ".env" or name.startswith(".env.")


def comment_style(relative_path: Path) -> str:
    name = relative_path.name
    if relative_path.suffix in BROWSER_SUFFIXES:
        return "script"
    if is_env_file(name) or relative_path.suffix in {".yml", ".yaml", ".toml", ".sh", ".bash"} or name in {
        "Dockerfile", "_redirects"
    } or name.endswith(".dockerfile"):
        return "hash"
    return "none"


def is_comment(line: str, style: str) -> bool:
    prefixes = COMMENT_PREFIXES[style]
    return bool(prefixes) and line.lstrip().startswith(prefixes)


def list_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if not is_skipped_directory(name))
        for name in sorted(names):
            path = Path(directory) / name
            if path.is_file():
                files.append(path.relative_to(root))
    return files


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


JSON_STRING_OR_COMMENT = re.compile(r'("(?:\\.|[^"\\\n])*")|//[^\n]*|/\*(?:[^*]|\*(?!/))*\*/')


def load_jsonc(text: str) -> dict:
    """Parses tsconfig-style JSON, which allows comments and trailing commas."""
    try:
        value = json.loads(text)
    except ValueError:
        # Drop comments outside strings, so "https://..." values survive, then trailing commas.
        without_comments = JSON_STRING_OR_COMMENT.sub(lambda match: match.group(1) or "", text)
        without_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", without_comments)
        try:
            value = json.loads(without_trailing_commas)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def leading_directive(text: str) -> str | None:
    """Returns "use client" or "use server" when the module starts with that directive."""
    position = 0
    length = len(text)
    while position < length:
        if text[position].isspace():
            position += 1
        elif text.startswith("//", position):
            end = text.find("\n", position)
            position = length if end == -1 else end + 1
        elif text.startswith("/*", position):
            end = text.find("*/", position + 2)
            position = length if end == -1 else end + 2
        else:
            break
    for directive in ("use client", "use server"):
        for quote in ("'", '"'):
            if text.startswith(f"{quote}{directive}{quote}", position):
                return directive
    return None


def find_projects(root: Path, files: list[Path]) -> list[Project]:
    projects: list[Project] = []
    for relative_path in files:
        if relative_path.name != "package.json":
            continue
        project_root = relative_path.parent
        package = load_jsonc(read_text(root / relative_path))
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        has_next_config = any((root / project_root / f"next.config.{suffix}").is_file()
                              for suffix in ("js", "mjs", "cjs", "ts", "mts"))
        project = Project(root=project_root, is_next=has_next_config or "next" in dependencies)
        for config_name in ("tsconfig.json", "jsconfig.json"):
            config_path = root / project_root / config_name
            if not config_path.is_file():
                continue
            options = load_jsonc(read_text(config_path)).get("compilerOptions", {})
            if isinstance(options.get("baseUrl"), str):
                project.base_url = project_root / options["baseUrl"]
            for pattern, targets in (options.get("paths") or {}).items():
                if isinstance(targets, list):
                    base = project.base_url if project.base_url is not None else project_root
                    project.aliases.append(
                        (pattern.rstrip("*"), [base / str(target).rstrip("*") for target in targets])
                    )
            break
        if not project.aliases:
            # Next.js's own default; also tried for projects without a tsconfig.
            default_targets = [project_root, project_root / "src"]
            project.aliases = [("@/", default_targets), ("~/", default_targets)]
        projects.append(project)
    # Deepest first, so a file belongs to its nearest project.
    return sorted(projects, key=lambda project: len(project.root.parts), reverse=True)


def project_of(relative_path: Path, projects: list[Project]) -> Project | None:
    for project in projects:
        if project.root == Path(".") or relative_path.is_relative_to(project.root):
            return project
    return None


def path_within(relative_path: Path, project_root: Path) -> tuple[str, ...]:
    if project_root == Path("."):
        return relative_path.parts
    return relative_path.relative_to(project_root).parts


def is_server_path(relative_path: Path, project: Project | None) -> bool:
    parts = relative_path.parts
    if ".github" in parts[:-1]:
        return True
    if len(parts) > 1 and parts[0] in SERVER_DIRECTORIES:
        return True
    if re.search(r"\.server\.[a-z]+$", relative_path.name):
        return True
    if project is None:
        return False
    inner = path_within(relative_path, project.root)
    if len(inner) > 1 and inner[0] in SERVER_DIRECTORIES:
        return True
    if not project.is_next:
        return len(inner) > 1 and inner[0] == "api"
    within_source = inner[1:] if inner and inner[0] == "src" else inner
    stem = relative_path.name.split(".")[0]
    if len(within_source) == 1 and stem in {"middleware", "instrumentation"}:
        return True
    if len(within_source) > 1 and within_source[0] == "pages" and (
        within_source[1] == "api" or within_source[1].split(".")[0] == "_document"
    ):
        return True
    return bool(within_source) and within_source[0] == "app" and stem == "route"


def is_pages_router_page(relative_path: Path, project: Project) -> bool:
    inner = path_within(relative_path, project.root)
    within_source = inner[1:] if inner and inner[0] == "src" else inner
    return len(within_source) > 1 and within_source[0] == "pages"


def is_app_router_file(relative_path: Path, project: Project) -> bool:
    inner = path_within(relative_path, project.root)
    within_source = inner[1:] if inner and inner[0] == "src" else inner
    return len(within_source) > 1 and within_source[0] == "app"


def resolve_import(specifier: str, importer: Path, project: Project, known_files: set[Path]) -> Path | None:
    if specifier.startswith(("./", "../")):
        bases = [Path(os.path.normpath(importer.parent / specifier))]
    else:
        bases = [
            Path(os.path.normpath(target / specifier[len(prefix):]))
            for prefix, targets in project.aliases
            if prefix and specifier.startswith(prefix)
            for target in targets
        ]
        if not bases and project.base_url is not None:
            bases = [Path(os.path.normpath(project.base_url / specifier))]
    for base in bases:
        candidates = [base]
        if base.name:  # an import of "." or ".." names a directory's index only
            candidates += [base.with_name(base.name + suffix) for suffix in MODULE_SUFFIXES]
        if base.suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            candidates += [base.with_suffix(suffix) for suffix in (".ts", ".tsx", ".mts", ".cts")]
        candidates += [base / f"index{suffix}" for suffix in MODULE_SUFFIXES]
        for candidate in candidates:
            if candidate in known_files:
                return candidate
    return None


def classify(root: Path, files: list[Path], texts: dict[Path, str]) -> dict[Path, str]:
    """Returns 'browser', 'server', 'test' or 'config' for each browser-language file."""
    projects = find_projects(root, files)
    code_files = [path for path in files if path.suffix in BROWSER_SUFFIXES]
    known_files = set(code_files)
    kinds: dict[Path, str] = {}
    next_files: dict[Path, Project] = {}
    for relative_path in code_files:
        project = project_of(relative_path, projects)
        text = texts[relative_path]
        if is_test_file(relative_path):
            kinds[relative_path] = "test"
        elif BUILD_CONFIG_FILE.match(relative_path.name):
            kinds[relative_path] = "config"
        elif (
            is_server_path(relative_path, project)
            or leading_directive(text) == "use server"
            or SERVER_ONLY_IMPORT.search(text)
        ):
            kinds[relative_path] = "server"
        elif project is not None and project.is_next and relative_path.suffix in MODULE_SUFFIXES:
            next_files[relative_path] = project
        else:
            kinds[relative_path] = "browser"

    imports: dict[Path, list[Path]] = {}
    for relative_path, project in next_files.items():
        resolved = (
            resolve_import(match.group(2), relative_path, project, known_files)
            for match in IMPORT_SPECIFIER.finditer(texts[relative_path])
        )
        imports[relative_path] = [target for target in resolved if target is not None]

    def reachable(starts: list[Path], stop) -> set[Path]:
        seen: set[Path] = set()
        queue = deque(starts)
        while queue:
            current = queue.popleft()
            if current in seen or current not in next_files or stop(current):
                continue
            seen.add(current)
            queue.extend(imports.get(current, []))
        return seen

    def is_client_module(path: Path) -> bool:
        return leading_directive(texts[path]) == "use client"

    browser_starts = [
        path for path, project in next_files.items()
        if is_client_module(path) or is_pages_router_page(path, project)
    ]
    browser_modules = reachable(browser_starts, stop=lambda path: False)
    server_starts = [
        path for path, project in next_files.items()
        if path not in browser_modules and is_app_router_file(path, project)
    ]
    server_modules = reachable(server_starts, stop=is_client_module)
    for relative_path in next_files:
        if relative_path in browser_modules or relative_path not in server_modules:
            kinds[relative_path] = "browser"
        else:
            kinds[relative_path] = "server"
    return kinds


def declaration_for(lines: list[str], index: int, rule: str, style: str) -> tuple[str | None, str | None]:
    """Returns (reason, problem) for a public-api-ok declaration covering this line."""
    candidates = [index, index - 1]
    above = index - 2
    while above >= 0 and is_comment(lines[above + 1], style) and is_comment(lines[above], style):
        candidates.append(above)
        above -= 1
    for candidate in candidates:
        if candidate < 0:
            continue
        match = DECLARATION.search(lines[candidate])
        if match and match.group(1) == rule:
            reason = re.sub(r"(\*/|-->)\s*$", "", match.group(2)).strip(" \t:;,.-—")
            if not reason or reason.upper().startswith("TODO"):
                return None, f"the public-api-ok declaration on line {candidate + 1} gives no reason"
            return reason, None
    return None, None


class Collector:
    def __init__(self) -> None:
        self.findings: dict[tuple[Path, int, str], Finding] = {}
        self.declarations: dict[tuple[Path, int, str], Declaration] = {}

    def report(self, relative_path: Path, lines: list[str], index: int, rule: str, message: str, style: str) -> None:
        key = (relative_path, index + 1, rule)
        if key in self.findings or key in self.declarations:
            return
        reason, problem = declaration_for(lines, index, rule, style)
        if reason is not None:
            self.declarations[key] = Declaration(rule, relative_path, index + 1, reason)
            return
        if problem:
            message = f"{message} ({problem})"
        self.findings[key] = Finding(rule, severity_of(rule), relative_path, index + 1, message)


def joined_with_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Joins adjacent string literals ('a' + 'b' becomes 'ab'); returns the text and offset breakpoints."""
    pieces: list[str] = []
    breakpoints: list[tuple[int, int]] = [(0, 0)]
    joined_length = 0
    previous_end = 0
    for match in STRING_JOIN.finditer(text):
        pieces.append(text[previous_end:match.start()])
        joined_length += match.start() - previous_end
        previous_end = match.end()
        breakpoints.append((joined_length, previous_end))
    pieces.append(text[previous_end:])
    return "".join(pieces), breakpoints


def original_offset(joined_offset: int, breakpoints: list[tuple[int, int]]) -> int:
    original = joined_offset
    for joined_start, original_start in breakpoints:
        if joined_start > joined_offset:
            break
        original = original_start + (joined_offset - joined_start)
    return original


def check_browser_file(relative_path: Path, text: str, collector: Collector) -> None:
    lines = text.splitlines()
    style = "script"

    def line_index(offset: int) -> int:
        return text.count("\n", 0, offset)

    def live(index: int) -> bool:
        return index < len(lines) and not is_comment(lines[index], style)

    flagged_lines: set[int] = set()
    joined, breakpoints = joined_with_offsets(text)
    for match in PUBLIC_API_HOST.finditer(joined):
        index = line_index(original_offset(match.start(), breakpoints))
        if live(index):
            flagged_lines.add(index)
            collector.report(relative_path, lines, index, "PA1", PA1_MESSAGE.format(host=match.group(0)), style)
    built_from_parts = list(ARRAY_JOIN.finditer(text))
    if DOMAIN_LITERAL.search(text):
        built_from_parts += TEMPLATE_API_SUBDOMAIN.finditer(text)
    if API_LITERAL.search(text):
        built_from_parts += TEMPLATE_DOMAIN.finditer(text)
    for match in built_from_parts:
        index = line_index(match.start())
        if live(index) and index not in flagged_lines:
            flagged_lines.add(index)
            collector.report(relative_path, lines, index, "PA1", PA1_PARTS_MESSAGE, style)
    for index, line in enumerate(lines):
        if index in flagged_lines or not live(index):
            continue
        path_match = CALCULATE_FULL_PATH.search(line)
        if path_match:
            collector.report(relative_path, lines, index, "PA4",
                             PA4_MESSAGE.format(path="/{country}/calculate-full"), style)
        elif ECONOMY_SEGMENT.search(line) and OVER_SEGMENT.search(line):
            collector.report(relative_path, lines, index, "PA4",
                             PA4_MESSAGE.format(path="/{country}/economy/{policy}/over/{baseline}"), style)


def check_variables(relative_path: Path, text: str, collector: Collector) -> None:
    lines = text.splitlines()
    style = comment_style(relative_path)
    is_bundler_config = bool(BUNDLER_CONFIG_FILE.match(relative_path.name))
    for index, line in enumerate(lines):
        if is_comment(line, style):
            continue
        for match in PUBLIC_VARIABLE.finditer(line):
            name, tail = match.group(0), match.group(1)
            if NAME_SECRET.search(tail) or NAME_PUBLIC_API.search(tail) or NAME_AUTH0_TOKEN.search(tail):
                prefix = name[: len(name) - len(tail) - 1]
                collector.report(relative_path, lines, index, "PA2",
                                 PA2_NAME_MESSAGE.format(name=name, prefix=prefix), style)
        assignment = PUBLIC_ASSIGNMENT.search(line)
        if assignment:
            name, tail, value = assignment.group(1), assignment.group(2), assignment.group(3)
            prefix = name[: len(name) - len(tail) - 1]
            what = None
            host = PUBLIC_API_HOST.search(value)
            if host and "AUDIENCE" not in tail:
                what = f"the Public API's address ({host.group(0)})"
            elif SERVER_TENANT.search(value):
                what = "the Public API's server Auth0 tenant"
            elif JSON_WEB_TOKEN.search(value):
                what = "a token"
            elif SERVER_CREDENTIAL_REFERENCE.search(value):
                what = f"a server credential ({SERVER_CREDENTIAL_REFERENCE.search(value).group(0)})"
            if what:
                collector.report(relative_path, lines, index, "PA2",
                                 PA2_VALUE_MESSAGE.format(name=name, what=what, prefix=prefix), style)
        if is_bundler_config:
            reference = SERVER_CREDENTIAL_REFERENCE.search(line)
            if reference:
                collector.report(relative_path, lines, index, "PA2",
                                 PA2_CONFIG_MESSAGE.format(reference=reference.group(0)), style)


def check_deploy_config(relative_path: Path, text: str, collector: Collector) -> None:
    lines = text.splitlines()
    style = comment_style(relative_path)
    for index, line in enumerate(lines):
        if is_comment(line, style):
            continue
        host = PUBLIC_API_HOST.search(line)
        if host:
            collector.report(relative_path, lines, index, "PA3", PA3_MESSAGE.format(host=host.group(0)), style)


def scans_variables(relative_path: Path) -> bool:
    name = relative_path.name
    if name in LOCK_FILES:
        return False
    return (
        relative_path.suffix in BROWSER_SUFFIXES
        or relative_path.suffix in CONFIG_SUFFIXES
        or is_env_file(name)
        or name in {"Dockerfile", "_redirects"}
        or name.endswith(".dockerfile")
    )


def scan(root: Path, explain: list[tuple[str, Path]] | None = None) -> tuple[list[Finding], list[Declaration]]:
    files = list_files(root)
    texts = {path: read_text(root / path) for path in files if path.suffix in BROWSER_SUFFIXES}
    kinds = classify(root, files, texts)
    collector = Collector()
    for relative_path in files:
        kind = kinds.get(relative_path)
        if explain is not None and kind is not None:
            explain.append((kind, relative_path))
        if kind == "test" or (kind is None and is_test_file(relative_path)):
            continue
        text = texts.get(relative_path)
        if kind == "browser":
            check_browser_file(relative_path, text, collector)
        if kind == "config" or relative_path.name in DEPLOY_CONFIG_FILES:
            text = text if text is not None else read_text(root / relative_path)
            check_deploy_config(relative_path, text, collector)
        if scans_variables(relative_path):
            text = text if text is not None else read_text(root / relative_path)
            check_variables(relative_path, text, collector)
    findings = sorted(collector.findings.values(), key=lambda finding: (finding.path, finding.line, finding.rule))
    declarations = sorted(collector.declarations.values(), key=lambda item: (item.path, item.line, item.rule))
    return findings, declarations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", default=".", help="repository directory to scan")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    parser.add_argument("--explain", action="store_true", help="also print how each code file was classified")
    arguments = parser.parse_args()
    root = Path(arguments.repo)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    explained: list[tuple[str, Path]] | None = [] if arguments.explain else None
    findings, declarations = scan(root, explained)
    for finding in findings:
        print(f"{finding.severity} {finding.rule} {finding.path.as_posix()}:{finding.line}: {finding.message}")
    for declaration in declarations:
        print(f"declared {declaration.rule} {declaration.path.as_posix()}:{declaration.line}: {declaration.reason}")
    for kind, relative_path in explained or []:
        print(f"{kind} {relative_path.as_posix()}")
    errors = sum(finding.severity == "error" for finding in findings)
    warnings = len(findings) - errors
    print(f"{errors} errors, {warnings} warnings, {len(declarations)} declared exceptions")
    return 1 if errors or (arguments.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
