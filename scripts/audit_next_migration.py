#!/usr/bin/env python3
"""Audit Next.js repos for common Vite and basePath migration regressions."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".git",
    ".next",
    ".turbo",
    ".vercel",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
}

SOURCE_SUFFIXES = {
    ".cjs",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".mts",
    ".ts",
    ".tsx",
}

IGNORE_MARKERS = {
    "policyengine-audit-ignore-line",
    "next-migration-audit-ignore-line",
}

ROOT_FETCH_RE = re.compile(
    r"\bfetch\s*\(\s*(['\"`])/(data|api|snapshots)(?:/|\$\{|\1)"
)
ROOT_AXIOS_RE = re.compile(
    r"\baxios\.(?:get|post|put|patch|delete)\s*\(\s*(['\"`])/(data|api)(?:/|\$\{|\1)"
)
ROOT_SRC_RE = re.compile(
    r"\bsrc\s*=\s*(?:\{\s*)?(['\"`])/(assets|images|logos)(?:/|\$\{)"
)
ROOT_ICON_RE = re.compile(
    r"\b(?:icon|apple|shortcut)\s*:\s*(['\"`])/(?![a-z]{2}/)[^'\"`]+\.(?:ico|png|svg|webp)\1"
)
NEXT_PUBLIC_LOCALHOST_RE = re.compile(
    r"process\.env\.NEXT_PUBLIC_[A-Z0-9_]+\s*\|\|\s*['\"]https?://localhost(?::\d+)?"
)


@dataclass(frozen=True)
class Finding:
    code: str
    path: Path
    line: int
    message: str

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root)
        return f"{self.code}: {rel}:{self.line}: {self.message}"


@dataclass(frozen=True)
class NextProject:
    root: Path
    package_json: Path
    has_base_path: bool


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")


def load_package_json(path: Path) -> dict:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIP_DIRS]
        directory = Path(dirpath)
        for filename in filenames:
            yield directory / filename


def has_next_dependency(package_json: Path) -> bool:
    package = load_package_json(package_json)
    deps = package.get("dependencies", {})
    dev_deps = package.get("devDependencies", {})
    return "next" in deps or "next" in dev_deps


def has_base_path(project_root: Path) -> bool:
    for config in project_root.glob("next.config.*"):
        text = read_text(config)
        if re.search(r"\bbasePath\s*[:=]", text):
            return True
        if "NEXT_PUBLIC_BASE_PATH" in text:
            return True
    return False


def find_next_projects(root: Path) -> list[NextProject]:
    projects: list[NextProject] = []
    for package_json in iter_files(root):
        if package_json.name != "package.json":
            continue
        if has_next_dependency(package_json):
            project_root = package_json.parent
            projects.append(
                NextProject(
                    root=project_root,
                    package_json=package_json,
                    has_base_path=has_base_path(project_root),
                )
            )
    return projects


def line_is_ignored(line: str) -> bool:
    return any(marker in line for marker in IGNORE_MARKERS)


def line_is_development_guarded(lines: list[str], index: int) -> bool:
    start = max(0, index - 4)
    context = "\n".join(lines[start : index + 1])
    return (
        "NODE_ENV === 'development'" in context
        or 'NODE_ENV === "development"' in context
        or "NODE_ENV !== 'production'" in context
        or 'NODE_ENV !== "production"' in context
    )


def is_source_file(path: Path) -> bool:
    return path.suffix in SOURCE_SUFFIXES


def is_safe_base_path_image_source(lines: list[str], index: int, text: str) -> bool:
    if "assetPath(" in text or "publicAssetPath(" in text or "appPath(" in text:
        return True

    file_text = "\n".join(lines)
    imports_base_path_image = "BasePathImage" in file_text

    start = max(0, index - 5)
    context = "\n".join(lines[start : index + 1])
    if "<BasePathImage" in context:
        return True
    if imports_base_path_image and "<Image" in context:
        return True

    return False


def scan_source_file(project: NextProject, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = read_text(path).splitlines()

    for index, line in enumerate(lines):
        if line_is_ignored(line):
            continue
        line_number = index + 1

        if "import.meta.env" in line:
            findings.append(
                Finding(
                    "vite-env",
                    path,
                    line_number,
                    "Next.js client/server code should use process.env.NEXT_PUBLIC_* instead of import.meta.env.",
                )
            )

        if re.search(r"\bVITE_[A-Z0-9_]+\b", line):
            findings.append(
                Finding(
                    "vite-env",
                    path,
                    line_number,
                    "VITE_* environment variables do not get exposed by Next.js; use NEXT_PUBLIC_* for browser values.",
                )
            )

        if "/vite.svg" in line and not (project.root / "public" / "vite.svg").exists():
            findings.append(
                Finding(
                    "stale-vite-favicon",
                    path,
                    line_number,
                    "Stale /vite.svg reference will 404; remove it or add an intentional asset.",
                )
            )

        if NEXT_PUBLIC_LOCALHOST_RE.search(line) and not line_is_development_guarded(
            lines, index
        ):
            findings.append(
                Finding(
                    "localhost-production-fallback",
                    path,
                    line_number,
                    "NEXT_PUBLIC_* production fallback points at localhost; gate localhost behind NODE_ENV=development or use a deployed URL.",
                )
            )

        if not project.has_base_path:
            continue

        if ROOT_FETCH_RE.search(line):
            findings.append(
                Finding(
                    "basepath-root-fetch",
                    path,
                    line_number,
                    "Root-relative data/API fetch will miss Next basePath; prefix with NEXT_PUBLIC_BASE_PATH or an appPath helper.",
                )
            )

        if ROOT_AXIOS_RE.search(line):
            findings.append(
                Finding(
                    "basepath-root-fetch",
                    path,
                    line_number,
                    "Root-relative axios data/API call will miss Next basePath; prefix with NEXT_PUBLIC_BASE_PATH or an appPath helper.",
                )
            )

        if ROOT_SRC_RE.search(line) and not is_safe_base_path_image_source(lines, index, line):
            findings.append(
                Finding(
                    "basepath-root-asset",
                    path,
                    line_number,
                    "Root-relative image asset will miss Next basePath; use assetPath/publicAssetPath or an equivalent helper.",
                )
            )

        if ROOT_ICON_RE.search(line):
            findings.append(
                Finding(
                    "basepath-root-icon",
                    path,
                    line_number,
                    "Root-relative metadata icon will miss Next basePath in mounted deployments.",
                )
            )

    return findings


def scan_vercel_configs(root: Path, projects: list[NextProject]) -> list[Finding]:
    if not projects:
        return []

    findings: list[Finding] = []
    for vercel_json in iter_files(root):
        if vercel_json.name != "vercel.json":
            continue
        try:
            config = json.loads(read_text(vercel_json))
        except json.JSONDecodeError:
            continue

        output_directory = config.get("outputDirectory")
        if isinstance(output_directory, str) and re.search(r"(^|/)dist/?$", output_directory):
            findings.append(
                Finding(
                    "vercel-next-dist-output",
                    vercel_json,
                    1,
                    "Next.js builds output .next, not dist; remove outputDirectory or set it to the correct Next output.",
                )
            )

        output_is_static_export = isinstance(output_directory, str) and re.search(
            r"(^|/)out/?$", output_directory
        )
        if (
            "framework" in config
            and config.get("framework") is None
            and output_directory
            and not output_is_static_export
        ):
            findings.append(
                Finding(
                    "vercel-next-framework-null",
                    vercel_json,
                    1,
                    "Next.js Vercel config should not keep framework=null unless this is an intentional static export.",
                )
            )

    return findings


def audit(root: Path) -> list[Finding]:
    projects = find_next_projects(root)
    findings: list[Finding] = []

    for project in projects:
        for path in iter_files(project.root):
            if is_source_file(path):
                findings.extend(scan_source_file(project, path))

    findings.extend(scan_vercel_configs(root, projects))
    return sorted(findings, key=lambda finding: (str(finding.path), finding.line, finding.code))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to audit. Defaults to the current directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    findings = audit(root)

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "code": finding.code,
                        "path": str(finding.path.relative_to(root)),
                        "line": finding.line,
                        "message": finding.message,
                    }
                    for finding in findings
                ],
                indent=2,
            )
        )
    elif findings:
        print("PolicyEngine Next migration audit found issues:", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding.format(root)}", file=sys.stderr)
        print(
            "\nUse // policyengine-audit-ignore-line only for intentional exceptions.",
            file=sys.stderr,
        )
    else:
        print("PolicyEngine Next migration audit passed.")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
