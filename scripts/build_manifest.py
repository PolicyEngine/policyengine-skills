#!/usr/bin/env python3
"""Build the ecosystem dashboard manifest by scanning the repo.

Walks the skills, agents, commands, and bundle definitions in this repo and
emits a single JSON manifest consumed by the React dashboard under
``dashboard/``. The manifest captures:

- One entry per artifact (skill, agent, command, bundle) with parsed
  frontmatter metadata.
- Bundle membership for skills, agents, and commands.
- Workflow edges inferred from text references inside commands and agents
  (which agents/skills each command invokes, which skills each agent invokes).
- Overlap pairs ranked by TF-IDF cosine similarity over name + description +
  body text, so duplicates surface without any embedding API.
- Coverage gaps (skills with no bundle, agents nobody calls, commands that
  reference missing artifacts, etc.).

The script needs PyYAML, which ``pyproject.toml`` lists, so run it as
``uv run python scripts/build_manifest.py``; the dashboard's ``predev`` and
``prebuild`` hooks do the same. Without PyYAML it stops with an error before
it writes anything. The dashboard needs what only a full YAML parser gives
it: nested fields, such as each analysis's ``jurisdiction``, and numbers that
arrive as numbers, which the Analyses page formats.

A rebuild with no content change rewrites nothing but ``generated_at``, on
macOS or Linux, whatever the string-hash seed, the Python version (3.11 on) or
the locale.
``--check`` builds the manifest without writing it and exits 1 if the copy on
disk differs anywhere but ``generated_at``; CI runs it on Linux.
``--output PATH`` writes or checks a manifest somewhere other than the
dashboard's data directory.
"""

from __future__ import annotations

import argparse
import decimal
import difflib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # main() stops with PYYAML_MISSING before it writes anything.
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "targets" / "claude" / "agents"
COMMANDS_DIR = ROOT / "targets" / "claude" / "commands"
BUNDLES_DIR = ROOT / "bundles"
ANALYSES_DIR = ROOT / "analyses"
FUNCTIONAL_TAGS_PATH = ROOT / "scripts" / "functional_tags.json"
ORG_REPOS_PATH = ROOT / "scripts" / "policyengine_repos.json"
OUTPUT_PATH = ROOT / "dashboard" / "src" / "data" / "manifest.json"


# ---------------------------------------------------------------------------
# Frontmatter parsing (PyYAML).
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

PYYAML_MISSING = """\
build_manifest.py needs PyYAML, and {executable} can't import it.
Run the script through uv, which installs the repo's dependencies:
    uv run python scripts/build_manifest.py
The script wrote nothing."""


class FrontmatterError(ValueError):
    """An artifact's frontmatter isn't valid YAML, or isn't a mapping."""


def parse_frontmatter(text: str, source: str = "frontmatter") -> tuple[dict, str]:
    """Return ``(metadata, body)``; metadata is ``{}`` when there is no frontmatter.

    Raises ``FrontmatterError``, naming ``source``, when the frontmatter isn't
    valid YAML or isn't a mapping, so a broken file stops the build instead of
    reaching the dashboard half-parsed.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    if yaml is None:
        raise ModuleNotFoundError(PYYAML_MISSING.format(executable=sys.executable))
    raw_meta, body = match.group(1), match.group(2)
    try:
        parsed = yaml.safe_load(raw_meta)
    except yaml.YAMLError as error:
        raise FrontmatterError(f"{source}: frontmatter isn't valid YAML: {error}") from error
    if parsed is None:
        return {}, body
    if not isinstance(parsed, dict):
        raise FrontmatterError(
            f"{source}: frontmatter must be a YAML mapping, not {type(parsed).__name__}"
        )
    return parsed, body


# ---------------------------------------------------------------------------
# Artifact loading.
# ---------------------------------------------------------------------------


@dataclass
class Artifact:
    id: str  # unique within (kind, id) — usually slug from name field
    kind: str  # "skill" | "agent" | "command" | "bundle"
    name: str
    description: str
    body: str
    category: str  # subdirectory or bundle category
    path: str  # relative to repo root
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    triggers: list[str] = field(default_factory=list)
    bundles: list[str] = field(default_factory=list)
    # PolicyEngine GitHub repos this artifact targets (inferred from text).
    target_repos: list[str] = field(default_factory=list)
    # Curated functional metadata (from scripts/functional_tags.json).
    functional_role: str | None = None
    functional_summary: str | None = None
    functional_scope: list[str] = field(default_factory=list)
    functional_supersedes: list[str] = field(default_factory=list)
    registry_status: str = "recommended"
    registry_owner: str = ""
    recommended_for: list[str] = field(default_factory=list)
    use_instead: list[str] = field(default_factory=list)
    registry_notes: str = ""
    # For commands: agents/skills referenced in body. For agents: skills.
    references: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))


# Curated overrides for repo classification. Most repos are categorized
# heuristically by name + description, but some names are ambiguous enough
# that we name them explicitly here. Keep this list short; if you find
# yourself adding many entries, refine the classifier instead.
REPO_KIND_OVERRIDES: dict[str, str] = {
    # Country models
    "policyengine-us": "country-model",
    "policyengine-uk": "country-model",
    "policyengine-canada": "country-model",
    "policyengine-au": "country-model",
    "policyengine-ie": "country-model",
    "policyengine-il": "country-model",
    "policyengine-it": "country-model",
    "policyengine-ng": "country-model",
    "policyengine-nz": "country-model",
    "policyengine-ve": "country-model",
    "policyengine-sg": "country-model",
    "policyengine-gl": "country-model",
    "policyengine-uk-rust": "country-model",
    "policyengine-us-old": "archived-engine",
    "policyengine-uk-old": "archived-engine",

    # Platform
    "policyengine-core": "platform",
    "policyengine-app": "platform",
    "policyengine-app-v2": "platform",
    "policyengine-api": "platform",
    "policyengine-api-v2": "platform",
    "policyengine-api-v2-alpha": "platform",
    "policyengine-api-light": "platform",
    "policyengine-household-api": "platform",
    "policyengine.py": "platform",
    "policyengine-ui-kit": "platform",
    "policyengine-claude": "platform",
    "policyengine-skills": "platform",
    "policyengine-bundles": "platform",
    "policyengine.dev": "platform",
    "policyengine-developer-portal": "platform",

    # Data pipelines
    "policyengine-us-data": "data-pipeline",
    "policyengine-uk-data": "data-pipeline",
    "arch-data": "data-pipeline",
    "us-congressional-districts": "data-pipeline",
    "uk-public-services-imputation": "data-pipeline",

    # Libraries / reusable packages
    "microdf": "library",
    "microimpute": "library",
    "microcalibrate": "library",
    "microplex": "library",
    "microplex-us": "library",
    "microplex-uk": "library",
    "microplex-evals": "library",
    "microunit": "library",
    "mortality": "library",
    "rdbl": "library",
    "l0": "library",
    "L0": "library",
    "linecheck": "library",
    "openfisca-tools": "library",
    "pe-compile": "library",

    # Long-lived products / standalone tools maintained across years
    "policyengine-taxsim": "long-lived-tool",
    "policyengine-section-8": "long-lived-tool",
    "policyengine-coverage-tracker": "long-lived-tool",
    "policyengine-uk-chat": "long-lived-tool",
    "policyengine-social": "long-lived-tool",
    "policyengine-household-wizard": "long-lived-tool",
    "policyengine-snapscreener-validation": "long-lived-tool",
    "policyengine-spm-decomposition": "long-lived-tool",
    "household-api-docs": "long-lived-tool",
    "social-security-model": "long-lived-tool",
    "pe-rf-compare-uc": "long-lived-tool",
    "ukds-mcp": "research-platform",
    "policybench": "research-platform",
    "calibration-diagnostics": "research-platform",

    # Internal / strategy / process
    "strategy": "internal",
    "publishing-strategy": "internal",
    "tech-team-roadmap-2026": "internal",
    "marketing-materials": "internal",
    "pulse": "internal",
    "perf-2025": "internal",
    "newsletters": "internal",
    "code-snippets": "internal",
    "plugin-blog": "internal",
}


def classify_repo(name: str, description: str) -> str:
    """Categorize a repo into a coarse kind. Used for the coverage dashboard.

    Returns one of: country-model, platform, data-pipeline, library,
    long-lived-tool, research-platform, internal, interactive-instance,
    research-analysis, presentation, grant-proposal, other.
    """
    if name in REPO_KIND_OVERRIDES:
        return REPO_KIND_OVERRIDES[name]
    n = name.lower()
    d = (description or "").lower()
    if any(s in n for s in ["nsf-", "openai-", "nuffield-", "pritzker"]):
        return "grant-proposal"
    if any(s in n for s in ["-slides", "-presentation", "demo-day", "-talk-", "talk-", "-intern", "presentation"]) or "presentation" in d or "slide deck" in d:
        return "presentation"
    if any(
        s in n
        for s in [
            "dashboard",
            "calculator",
            "calc",
            "visualisation",
            "visualization",
            "-viz",
            "viz-",
            "interactive",
            "explorer",
            "wrapped",
            "wizard",
            "tracker",
            "-app",
            "comparison",
            "atlas",
        ]
    ) or "dashboard" in d or "interactive" in d or "calculator" in d:
        return "interactive-instance"
    if any(
        s in n
        for s in [
            "notebooks",
            "year-in",
            "review",
            "analysis",
            "roadmap",
            "publishing",
            "github-wrapped",
            "rfp",
        ]
    ):
        return "research-analysis"
    if any(
        s in n
        for s in [
            "budget",
            "statement",
            "reforms",
            "reform",
            "manifestos",
            "tax-changes",
            "tax-policy",
            "event-",
            "impacts",
            "audit",
            "scores",
        ]
    ):
        return "analysis"
    return "other"


REPO_KIND_LABELS = {
    "country-model": "Country models",
    "platform": "Platform",
    "data-pipeline": "Data pipelines",
    "library": "Libraries",
    "long-lived-tool": "Long-lived tools",
    "research-platform": "Research platforms",
    "internal": "Internal & process",
    "interactive-instance": "Interactive instances",
    "research-analysis": "Research / analysis",
    "presentation": "Presentations",
    "grant-proposal": "Grants & proposals",
    "analysis": "One-off analyses",
    "archived-engine": "Archived engines",
    "other": "Other",
}

# Kinds that the skills ecosystem is *expected* to provide ongoing tooling
# for. The remaining kinds (interactive-instance, research-analysis,
# presentation, grant-proposal, analysis, internal) are typically outputs of
# existing workflows (e.g. /create-dashboard) rather than separate engineering
# surfaces that need their own skills.
TOOLING_RELEVANT_KINDS = {
    "country-model",
    "platform",
    "data-pipeline",
    "library",
    "long-lived-tool",
    "research-platform",
}


def read_utf8(path: Path) -> str:
    """Read one of the builder's inputs as UTF-8, the encoding they're written in.

    ``read_text()`` without an encoding decodes with the locale's encoding.
    Under a locale that isn't UTF-8 (Windows, or a Latin-9 locale on Linux or
    macOS), Python before 3.15 decodes UTF-8 text wrongly: the build can stop
    on a file that is fine, or garble non-ASCII text in the manifest.
    """
    return path.read_text(encoding="utf-8")


def load_org_repos() -> list[dict]:
    """Load the cached GitHub org inventory; empty list if missing."""
    if not ORG_REPOS_PATH.exists():
        return []
    return json.loads(read_utf8(ORG_REPOS_PATH))


def build_known_repos() -> list[tuple[str, str]]:
    """Return ``(name, kind)`` tuples for every PolicyEngine org repo.

    Falls back to the curated override list alone if the org inventory file
    is missing — but the inventory should always be present in source
    control so this is just a safety net.
    """
    inventory = load_org_repos()
    if inventory:
        out: list[tuple[str, str]] = []
        for r in inventory:
            kind = classify_repo(r["name"], r.get("description", ""))
            out.append((r["name"], kind))
        # Sort longest-name first so substring matching doesn't shadow
        # longer names (e.g. "policyengine-us" vs "policyengine-us-data").
        # Break ties by name, so the inventory file's order never reaches
        # target_repos, known_repos or repo_coverage.
        out.sort(key=lambda x: (-len(x[0]), x[0]))
        return out
    return [(r, k) for r, k in REPO_KIND_OVERRIDES.items()]


KNOWN_REPO_KINDS: list[tuple[str, str]] = build_known_repos()
KNOWN_REPOS = [r for r, _ in KNOWN_REPO_KINDS]
REPO_KIND_BY_NAME = {r: k for r, k in KNOWN_REPO_KINDS}


# Routing slugs (in skill descriptions / categories) that don't literally
# spell out the repo name but still imply it.
REPO_ALIASES: dict[str, list[str]] = {
    "policyengine-us": ["TANF", "SNAP", "EITC", "CTC", "SSI", "WIC", "Section 8", "Medicaid"],
    "policyengine-uk": ["Universal Credit", "PIP", "DLA", "JSA", "ESA"],
    "policyengine-canada": ["CCB", "GIS", "OAS", "CPP", "CWB", "Canada Child Benefit"],
    "policyengine-app": ["policyengine.org", "app-v2", "frontend"],
    "policyengine-api": ["REST API", "Flask"],
}


def infer_target_repos(name: str, description: str, body: str, category: str) -> list[str]:
    """Return the PolicyEngine GitHub repos this artifact targets."""
    haystack = f"{name}\n{description}\n{body[:6000]}\n{category}"
    found: list[str] = []
    seen: set[str] = set()
    for repo in KNOWN_REPOS:
        if repo in seen:
            continue
        if re.search(rf"\b{re.escape(repo)}\b", haystack):
            found.append(repo)
            seen.add(repo)
    for repo, aliases in REPO_ALIASES.items():
        if repo in seen:
            continue
        for alias in aliases:
            if alias.lower() in haystack.lower():
                found.append(repo)
                seen.add(repo)
                break
    return found


def relpath(path: Path) -> str:
    return str(path.relative_to(ROOT))


def extract_triggers(description: str) -> list[str]:
    """Pull out the ``Triggers:`` quoted phrases from a description block."""
    triggers: list[str] = []
    match = re.search(r"Triggers?:\s*(.+?)(?:\n\n|$)", description, re.DOTALL | re.IGNORECASE)
    if not match:
        return triggers
    chunk = match.group(1)
    triggers.extend(re.findall(r'"([^"]+)"', chunk))
    return triggers


def load_skills() -> list[Artifact]:
    artifacts: list[Artifact] = []
    for skill_md in sorted(SKILLS_DIR.glob("**/SKILL.md")):
        meta, body = parse_frontmatter(read_utf8(skill_md), relpath(skill_md))
        # Flat layout: skills/<slug>/SKILL.md with the category declared in
        # frontmatter metadata. Fall back to the parent dir for any legacy
        # nested layout (skills/<category>/<slug>/SKILL.md).
        metadata = meta.get("metadata")
        category = metadata.get("category") if isinstance(metadata, dict) else None
        if not category:
            category = skill_md.parent.parent.name
        if category == "skills":
            category = "uncategorized"
        slug = skill_md.parent.name
        name = meta.get("name") or slug
        description = meta.get("description") or ""
        if isinstance(description, list):
            description = "\n".join(description)
        artifacts.append(
            Artifact(
                id=name,
                kind="skill",
                name=name,
                description=description.strip(),
                body=body,
                category=category,
                path=relpath(skill_md),
                triggers=extract_triggers(description),
                target_repos=infer_target_repos(name, description, body, category),
            )
        )
    return artifacts


def load_agents() -> list[Artifact]:
    artifacts: list[Artifact] = []
    for agent_md in sorted(AGENTS_DIR.glob("**/*.md")):
        if agent_md.name == "README.md":
            continue
        meta, body = parse_frontmatter(read_utf8(agent_md), relpath(agent_md))
        rel_to_agents = agent_md.relative_to(AGENTS_DIR)
        category = rel_to_agents.parts[0] if len(rel_to_agents.parts) > 1 else "general"
        name = meta.get("name") or agent_md.stem
        description = meta.get("description") or ""
        if isinstance(description, list):
            description = "\n".join(description)
        tools_raw = meta.get("tools") or []
        if isinstance(tools_raw, str):
            tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
        else:
            tools = list(tools_raw)
        artifacts.append(
            Artifact(
                id=name,
                kind="agent",
                name=name,
                description=description.strip(),
                body=body,
                category=category,
                path=relpath(agent_md),
                tools=tools,
                model=meta.get("model") or None,
                target_repos=infer_target_repos(name, description, body, category),
            )
        )
    return artifacts


def load_commands() -> list[Artifact]:
    artifacts: list[Artifact] = []
    for cmd_md in sorted(COMMANDS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(read_utf8(cmd_md), relpath(cmd_md))
        name = cmd_md.stem
        description = meta.get("description") or ""
        if isinstance(description, list):
            description = "\n".join(description)
        artifacts.append(
            Artifact(
                id=name,
                kind="command",
                name=name,
                description=description.strip(),
                body=body,
                category="command",
                path=relpath(cmd_md),
                target_repos=infer_target_repos(name, description, body, "command"),
            )
        )
    return artifacts


def load_bundles() -> list[Artifact]:
    artifacts: list[Artifact] = []
    for bundle_path in sorted(BUNDLES_DIR.glob("*.json")):
        data = json.loads(read_utf8(bundle_path))
        name = data.get("name") or bundle_path.stem
        artifacts.append(
            Artifact(
                id=name,
                kind="bundle",
                name=name,
                description=data.get("description") or "",
                body=json.dumps(data, indent=2),
                category=data.get("category") or "bundle",
                path=relpath(bundle_path),
            )
        )
    return artifacts


# ---------------------------------------------------------------------------
# Bundle membership + reference extraction.
# ---------------------------------------------------------------------------


def attach_bundle_membership(
    artifacts_by_kind: dict[str, list[Artifact]],
    raw_bundles: list[dict],
) -> None:
    """Populate ``Artifact.bundles`` based on bundle JSON membership lists."""
    by_path: dict[str, Artifact] = {}
    for kind in ("skill", "agent", "command"):
        for art in artifacts_by_kind[kind]:
            # Bundle entries reference either ./skills/... directly, or
            # ./commands/<file> / ./agents/<file>. Map both forms.
            full_rel = "./" + art.path
            by_path[full_rel] = art
            if art.kind == "command":
                by_path["./commands/" + Path(art.path).name] = art
            if art.kind == "agent":
                # bundles can reference e.g. "./agents/country-models/rules-engineer.md"
                sub = Path(art.path).relative_to(Path("targets/claude/agents")).as_posix()
                by_path["./agents/" + sub] = art
            if art.kind == "skill":
                # skill entries usually omit the trailing /SKILL.md
                skill_dir = "./" + str(Path(art.path).parent)
                by_path[skill_dir] = art

    for bundle in raw_bundles:
        bname = bundle["name"]
        for key in ("skills", "agents", "commands"):
            for ref in bundle.get(key, []) or []:
                art = by_path.get(ref)
                if art and bname not in art.bundles:
                    art.bundles.append(bname)


REFERENCE_PATTERNS = {
    # Match agent invocations: subagent_type="rules-engineer" or @rules-engineer
    "agent": [
        re.compile(r'subagent_type\s*[=:]\s*"([a-z][a-z0-9\-]+)"'),
        re.compile(r"@([a-z][a-z0-9\-]+)\b"),
    ],
    # Match skill invocations: Skill tool name, or slash-mentions of slugs.
    "skill": [
        re.compile(r'Skill\([\s\S]{0,80}?skill\s*[=:]\s*"([a-z][a-z0-9\-]+)"'),
        re.compile(r"`/([a-z][a-z0-9\-]+)`"),
    ],
}


def extract_references(text: str, known_ids: dict[str, set[str]]) -> dict[str, list[str]]:
    """Scan ``text`` for references to known agents/skills/commands."""
    refs: dict[str, list[str]] = defaultdict(list)
    for kind, patterns in REFERENCE_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.findall(text):
                if match in known_ids[kind] and match not in refs[kind]:
                    refs[kind].append(match)
    # Also catch raw mentions of known slugs anywhere in the body — useful for
    # picking up "use the rules-engineer agent" prose. Restrict to slugs >= 6
    # chars to avoid matching common words.
    for kind in ("agent", "skill", "command"):
        # Sorted, because set order follows the per-process string-hash seed
        # (PYTHONHASHSEED), and this loop sets the order of each artifact's
        # references and of the edges built from them.
        for slug in sorted(known_ids[kind]):
            if len(slug) < 6 or "-" not in slug:
                continue
            if re.search(rf"\b{re.escape(slug)}\b", text) and slug not in refs[kind]:
                refs[kind].append(slug)
    return dict(refs)


# ---------------------------------------------------------------------------
# Overlap scoring (TF-IDF cosine similarity, no deps).
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")
STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with",
    "this", "that", "is", "are", "be", "use", "uses", "using", "when",
    "if", "what", "would", "how", "much", "policyengine", "skill", "agent",
    "command", "tool", "tools", "before", "after", "all", "should", "do",
    "user", "users", "via", "from", "by", "as", "at", "it", "its", "load",
    "load_this_skill", "first", "skill_first", "uk", "us", "ca", "always",
    "calculate", "calculations", "patterns", "policy", "patterns_skill",
}


def tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in TOKEN_RE.findall(text)
        if len(t) > 2 and t.lower() not in STOPWORDS
    ]


# math.log calls the C library's log, and the C standard leaves its accuracy
# to each implementation, so the last bit can differ between platforms. On
# macOS, math.log misses the correctly rounded value of ln((n + 1) / (df + 1))
# for 44 of the 79,799 pairs with 2 <= n < 400 and 1 <= df <= n. One bit can
# reorder near-tied shared_terms, and a manifest built on macOS would then
# fail CI's check on Linux. The decimal module computes ln in software,
# correctly rounded to 34 digits, and float() rounds that to a double, so
# every platform gets the same float. For all 79,799 pairs that double is the
# correctly rounded one.
LN_CONTEXT = decimal.Context(prec=34)


def smoothed_idf(n_docs: int, doc_freq: int) -> float:
    """Return ``ln((n_docs + 1) / (doc_freq + 1)) + 1``, the same on every platform."""
    ratio = (n_docs + 1) / (doc_freq + 1)
    return float(LN_CONTEXT.ln(decimal.Decimal(ratio))) + 1


def compute_overlaps(artifacts: list[Artifact]) -> list[dict]:
    """Return every pair of artifacts whose TF-IDF cosine similarity is 0.15 or more.

    Compares within and across kinds — a command that duplicates a skill is
    just as interesting as two skills covering the same ground.

    Pairs follow the order of ``artifacts``: by ``a``, then by ``b``, with
    ``a`` before ``b``. An edit to one artifact changes the IDF of the terms
    it adds or drops, which moves many scores; in this order such an edit
    rewrites only the lines that change, where an order by score would move
    most pairs. The dashboard sorts pairs by score where it ranks them.
    """
    docs: list[list[str]] = []
    for art in artifacts:
        # Description and triggers carry most of the routing signal; weight
        # them more than raw body text.
        weighted = " ".join(
            [art.name, art.description, art.description, " ".join(art.triggers)]
        )
        # Cap body to keep IDF stable across short artifacts.
        body_excerpt = art.body[:4000]
        docs.append(tokenize(weighted + " " + body_excerpt))

    df = Counter()
    for doc in docs:
        df.update(set(doc))
    n_docs = len(docs)
    idf_by_df = {count: smoothed_idf(n_docs, count) for count in set(df.values())}
    idf = {term: idf_by_df[count] for term, count in df.items()}

    vectors: list[dict[str, float]] = []
    for doc in docs:
        tf = Counter(doc)
        if not tf:
            vectors.append({})
            continue
        vec = {term: count * idf.get(term, 0.0) for term, count in tf.items()}
        # math.fsum rounds exactly. The built-in sum() rounds floats
        # differently from Python 3.12 on, which changed shared_terms order.
        norm = math.sqrt(math.fsum(v * v for v in vec.values())) or 1.0
        vectors.append({k: v / norm for k, v in vec.items()})

    pairs: list[dict] = []
    for i in range(len(artifacts)):
        vi = vectors[i]
        if not vi:
            continue
        for j in range(i + 1, len(artifacts)):
            vj = vectors[j]
            if not vj:
                continue
            # Iterate over shorter vector for speed.
            if len(vi) > len(vj):
                a, b = vj, vi
            else:
                a, b = vi, vj
            score = math.fsum(a[t] * b[t] for t in a if t in b)
            if score >= 0.15:
                pairs.append(
                    {
                        "a": {"kind": artifacts[i].kind, "id": artifacts[i].id},
                        "b": {"kind": artifacts[j].kind, "id": artifacts[j].id},
                        "score": round(score, 4),
                        # Ties go to the term that sorts first, so the order
                        # never depends on where a term first appears in a text.
                        "shared_terms": sorted(
                            (term for term in a if term in b),
                            key=lambda t: (-a[t] * b[t], t),
                        )[:8],
                    }
                )
    # No sort by score: the loops above already put pairs in artifact order.
    return pairs


# ---------------------------------------------------------------------------
# Gap analysis.
# ---------------------------------------------------------------------------


def compute_gaps(
    artifacts_by_kind: dict[str, list[Artifact]],
    edges: list[dict],
    raw_bundles: list[dict],
) -> dict[str, list[dict]]:
    """Compute coverage-gap lists for the dashboard."""
    gaps: dict[str, list[dict]] = {
        "orphaned_skills": [],
        "uncalled_agents": [],
        "orphaned_agents": [],
        "broken_bundle_refs": [],
        "missing_descriptions": [],
        "missing_triggers": [],
    }

    invoked_agents: set[str] = set()
    referenced_skills: set[str] = set()
    for edge in edges:
        if edge["target_kind"] == "agent":
            invoked_agents.add(edge["target"])
        if edge["target_kind"] == "skill":
            referenced_skills.add(edge["target"])

    for art in artifacts_by_kind["skill"]:
        if not art.bundles:
            gaps["orphaned_skills"].append({"id": art.id, "category": art.category})
        if not art.description.strip():
            gaps["missing_descriptions"].append(
                {"id": art.id, "kind": "skill", "path": art.path}
            )
        if not art.triggers and "ALWAYS LOAD" not in art.description.upper():
            # Skills without triggers may still be load-on-demand; flag only
            # those that look like routing skills but lack triggers.
            if "trigger" in art.description.lower() or "when " in art.description.lower():
                gaps["missing_triggers"].append({"id": art.id, "path": art.path})

    for art in artifacts_by_kind["agent"]:
        if art.id not in invoked_agents:
            gaps["uncalled_agents"].append({"id": art.id, "category": art.category})
        if not art.bundles:
            gaps["orphaned_agents"].append({"id": art.id, "category": art.category})
        if not art.description.strip():
            gaps["missing_descriptions"].append(
                {"id": art.id, "kind": "agent", "path": art.path}
            )

    # Detect bundle references that don't resolve to a known file on disk.
    known_paths = set()
    for kind in ("skill", "agent", "command"):
        for art in artifacts_by_kind[kind]:
            known_paths.add("./" + art.path)
            if art.kind == "skill":
                known_paths.add("./" + str(Path(art.path).parent))
            if art.kind == "agent":
                sub = (
                    Path(art.path).relative_to(Path("targets/claude/agents")).as_posix()
                )
                known_paths.add("./agents/" + sub)
            if art.kind == "command":
                known_paths.add("./commands/" + Path(art.path).name)
    for bundle in raw_bundles:
        for key in ("skills", "agents", "commands"):
            for ref in bundle.get(key, []) or []:
                if ref not in known_paths:
                    gaps["broken_bundle_refs"].append(
                        {"bundle": bundle["name"], "ref": ref, "kind": key}
                    )

    return gaps


# ---------------------------------------------------------------------------
# Build.
# ---------------------------------------------------------------------------


# Written edge order. Edges group by source kind in the order build_edges
# emits them: commands, then agents, then bundles. The dashboard drawer lists
# only the first 20 incoming edges of an artifact ("Called by"), so this order
# decides which callers it shows, and user-facing commands should lead. Within
# a group, edges sort by source id, then target kind, then target id.
SOURCE_KIND_ORDER = ("command", "agent", "bundle")
TARGET_KIND_ORDER = ("agent", "skill", "command")


def _kind_rank(kind: str, order: tuple[str, ...]) -> tuple[int, str]:
    """Rank ``kind`` by its place in ``order``; unlisted kinds go last, by name."""
    return (order.index(kind) if kind in order else len(order), kind)


def edge_sort_key(edge: dict) -> tuple:
    """Key that puts ``edges`` in one canonical order (see SOURCE_KIND_ORDER)."""
    return (
        *_kind_rank(edge["source_kind"], SOURCE_KIND_ORDER),
        edge["source"],
        *_kind_rank(edge["target_kind"], TARGET_KIND_ORDER),
        edge["target"],
    )


def build_edges(
    artifacts_by_kind: dict[str, list[Artifact]],
    known_ids: dict[str, set[str]],
) -> list[dict]:
    """Build the workflow graph edges from artifact bodies."""
    edges: list[dict] = []
    # Commands reference agents and skills.
    for art in artifacts_by_kind["command"]:
        refs = extract_references(art.body, known_ids)
        art.references = refs
        for kind in ("agent", "skill", "command"):
            for target in refs.get(kind, []):
                edges.append(
                    {
                        "source_kind": "command",
                        "source": art.id,
                        "target_kind": kind,
                        "target": target,
                    }
                )
    # Agents reference other agents and skills.
    for art in artifacts_by_kind["agent"]:
        refs = extract_references(art.body, known_ids)
        # Don't add a self-loop if the agent body mentions its own name.
        for kind in refs:
            refs[kind] = [r for r in refs[kind] if not (kind == "agent" and r == art.id)]
        art.references = refs
        for kind in ("agent", "skill"):
            for target in refs.get(kind, []):
                edges.append(
                    {
                        "source_kind": "agent",
                        "source": art.id,
                        "target_kind": kind,
                        "target": target,
                    }
                )
    # Bundle membership becomes an edge from bundle -> artifact.
    for art in artifacts_by_kind["bundle"]:
        for kind in ("skill", "agent", "command"):
            members = [a for a in artifacts_by_kind[kind] if art.id in a.bundles]
            for member in members:
                edges.append(
                    {
                        "source_kind": "bundle",
                        "source": art.id,
                        "target_kind": kind,
                        "target": member.id,
                    }
                )
    return edges


def owner_for_artifact(art: Artifact) -> str:
    """Return the likely internal owner for registry triage."""
    scope = set(art.functional_scope or art.target_repos)
    if art.kind == "agent" and art.category == "dashboard":
        return "Dashboard tooling"
    if art.category in {"frontend", "content", "apps"} or scope & {
        "policyengine-app-v2",
        "policyengine-ui-kit",
        "interactive-tools",
        "dashboards",
    }:
        return "Frontend & product"
    if art.category in {
        "domain-knowledge",
        "domain",
        "technical-patterns",
        "model-development",
        "workflows",
    } or scope & {
        "policyengine-us",
        "policyengine-uk",
        "policyengine-canada",
    }:
        return "Country model engineering"
    if art.category in {"data-science", "data"} or scope & {
        "policyengine-us-data",
        "policyengine-uk-data",
        "microcosm",
        "microdf",
        "microimpute",
        "microcalibrate",
    }:
        return "Data science"
    if scope & {"policyengine-api", "policyengine-api-v2", "policyengine-core"}:
        return "Platform engineering"
    if scope & {"policyengine-skills", "policyengine-claude"}:
        return "AI tooling"
    return "PolicyEngine"


def registry_recommendation(art: Artifact) -> list[str]:
    summary = art.functional_summary or art.description
    if not summary:
        return []
    if art.kind == "command":
        return [f"Use this command when you need to {summary[0].lower() + summary[1:]}"]
    if art.kind == "skill":
        return [f"Load this skill for work involving: {summary}"]
    if art.kind == "agent":
        return [
            f"Use indirectly through its workflow unless you are maintaining agent orchestration: {summary}"
        ]
    if art.kind == "bundle":
        return [f"Install this bundle when you need: {summary}"]
    return []


def attach_registry_metadata(
    artifacts_by_kind: dict[str, list[Artifact]],
    edges: list[dict],
) -> None:
    """Add internal registry metadata used by the dashboard.

    The functional tag file can override these fields, but most values are
    derived so every artifact gets useful guidance without hand-maintaining a
    second catalog.
    """
    flat = [a for arts in artifacts_by_kind.values() for a in arts]
    by_kind_id = {(a.kind, a.id): a for a in flat}

    for art in flat:
        for old_id in art.functional_supersedes:
            old = by_kind_id.get((art.kind, old_id))
            if old and art.id not in old.use_instead:
                old.use_instead.append(art.id)

    invoked_agents = {
        e["target"]
        for e in edges
        if e["target_kind"] == "agent" and e["source_kind"] != "bundle"
    }

    for art in flat:
        art.registry_owner = art.registry_owner or owner_for_artifact(art)
        art.recommended_for = art.recommended_for or registry_recommendation(art)

        if art.use_instead:
            art.registry_status = "deprecated"
            art.registry_notes = (
                "A newer artifact explicitly supersedes this one. Prefer the replacement."
            )
        elif art.kind == "agent":
            art.registry_status = "internal-only"
            art.registry_notes = (
                "Agents are usually implementation details of commands; call directly only "
                "when maintaining or debugging the workflow."
            )
            if art.id not in invoked_agents:
                art.registry_status = "use-with-care"
                art.registry_notes = (
                    "This agent is not currently invoked by any command or agent. Confirm "
                    "it is still intended before relying on it."
                )
        elif art.kind in {"skill", "command"} and not art.bundles:
            art.registry_status = "use-with-care"
            art.registry_notes = (
                "This artifact is not shipped in any bundle, so most users will not load it "
                "unless they have a local checkout."
            )
        elif art.kind == "bundle":
            art.registry_status = "recommended"
            art.registry_notes = "Bundle install profile."
        else:
            art.registry_status = "recommended"
            art.registry_notes = "Recommended for the listed scope."


def artifact_to_dict(art: Artifact) -> dict:
    return {
        "id": art.id,
        "kind": art.kind,
        "name": art.name,
        "description": art.description,
        "category": art.category,
        "path": art.path,
        "tools": art.tools,
        "model": art.model,
        "triggers": art.triggers,
        "bundles": sorted(art.bundles),
        "target_repos": art.target_repos,
        "functional_role": art.functional_role,
        "functional_summary": art.functional_summary,
        "functional_scope": art.functional_scope,
        "functional_supersedes": art.functional_supersedes,
        "registry_status": art.registry_status,
        "registry_owner": art.registry_owner,
        "recommended_for": art.recommended_for,
        "use_instead": sorted(art.use_instead),
        "registry_notes": art.registry_notes,
        "references": {k: sorted(v) for k, v in (art.references or {}).items()},
        "body_length": len(art.body),
    }


# ---------------------------------------------------------------------------
# Functional tag merge + curated overlap computation.
# ---------------------------------------------------------------------------


def attach_functional_tags(artifacts_by_kind: dict[str, list[Artifact]]) -> None:
    """Merge hand-curated functional tags from functional_tags.json."""
    if not FUNCTIONAL_TAGS_PATH.exists():
        return
    data = json.loads(read_utf8(FUNCTIONAL_TAGS_PATH))
    for kind_plural, kind_singular in (
        ("skills", "skill"),
        ("agents", "agent"),
        ("commands", "command"),
    ):
        by_id = {a.id: a for a in artifacts_by_kind[kind_singular]}
        for entry in data.get(kind_plural, []):
            art = by_id.get(entry["id"])
            if not art:
                continue
            art.functional_role = entry.get("role")
            art.functional_summary = entry.get("summary")
            art.functional_scope = entry.get("scope_repos", [])
            art.functional_supersedes = entry.get("supersedes", [])
            art.registry_status = entry.get("status", art.registry_status)
            art.registry_owner = entry.get("owner", art.registry_owner)
            art.recommended_for = entry.get("recommended_for", art.recommended_for)
            art.use_instead = entry.get("use_instead", art.use_instead)
            art.registry_notes = entry.get("notes", art.registry_notes)


def compute_functional_overlaps(
    artifacts: list[Artifact],
    edges: list[dict],
) -> list[dict]:
    """Group artifacts by functional role and categorize each pair.

    Output categories:
      - ``superseded``      one artifact explicitly supersedes another (deprecation).
      - ``merge-candidate`` same kind, same role, overlapping scope — duplication risk.
      - ``complementary``   same kind, same role, disjoint scope — intentional siblings.
      - ``implementation-pair`` cross-kind, same root role — expected coupling.
      - ``wiring-gap``      cross-kind, same root role, NOT linked via workflow edge.
    """
    tagged = [a for a in artifacts if a.functional_role]
    edge_keys: set[str] = set()
    for e in edges:
        if e["source_kind"] == "bundle":
            continue
        edge_keys.add(f"{e['source_kind']}:{e['source']}|{e['target_kind']}:{e['target']}")
        edge_keys.add(f"{e['target_kind']}:{e['target']}|{e['source_kind']}:{e['source']}")

    def linked(a: Artifact, b: Artifact) -> bool:
        return f"{a.kind}:{a.id}|{b.kind}:{b.id}" in edge_keys

    def root_role(role: str) -> str:
        # Trim the final colon segment so "review:seo:meta" groups under "review:seo".
        # Keep two colon-segments by default (e.g. "pattern:testing" -> "pattern:testing").
        parts = role.split(":")
        if len(parts) <= 2:
            return role
        return ":".join(parts[:2])

    pairs: list[dict] = []

    # 1) Explicit supersedes.
    for art in tagged:
        for old_id in art.functional_supersedes:
            other = next(
                (
                    o
                    for o in tagged
                    if o.id == old_id and o.kind == art.kind
                ),
                None,
            )
            if other is not None:
                pairs.append(
                    {
                        "category": "superseded",
                        "artifacts": [
                            {"kind": art.kind, "id": art.id},
                            {"kind": other.kind, "id": other.id},
                        ],
                        "role": art.functional_role,
                        "rationale": (
                            f"`{art.id}` explicitly supersedes `{other.id}`. "
                            f"`{other.id}` should be deprecated or removed."
                        ),
                    }
                )

    # 2) Same-kind same exact role.
    by_kind_role: dict[tuple[str, str], list[Artifact]] = defaultdict(list)
    for art in tagged:
        by_kind_role[(art.kind, art.functional_role)].append(art)

    seen_pairs: set[tuple[str, str]] = set()
    for (kind, role), members in by_kind_role.items():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                pair_id = tuple(sorted([f"{a.kind}:{a.id}", f"{b.kind}:{b.id}"]))
                if pair_id in seen_pairs:
                    continue
                seen_pairs.add(pair_id)
                a_scope = set(a.functional_scope)
                b_scope = set(b.functional_scope)
                # "all" matches anything; otherwise compute overlap.
                overlap = (
                    a_scope & b_scope
                    or ("all" in a_scope and b_scope)
                    or ("all" in b_scope and a_scope)
                )
                if overlap:
                    pairs.append(
                        {
                            "category": "merge-candidate",
                            "artifacts": [
                                {"kind": a.kind, "id": a.id},
                                {"kind": b.kind, "id": b.id},
                            ],
                            "role": role,
                            "scope_overlap": sorted(overlap) if isinstance(overlap, set) else [],
                            "rationale": (
                                f"Both are `{role}` covering overlapping scope "
                                f"{sorted(overlap)[:3] if isinstance(overlap, set) else ''}. "
                                f"Consider whether one could replace the other or whether "
                                f"the scope split is intentional."
                            ),
                        }
                    )
                else:
                    pairs.append(
                        {
                            "category": "complementary",
                            "artifacts": [
                                {"kind": a.kind, "id": a.id},
                                {"kind": b.kind, "id": b.id},
                            ],
                            "role": role,
                            "rationale": (
                                f"Both are `{role}` but cover disjoint scope "
                                f"({sorted(a_scope)} vs {sorted(b_scope)}). "
                                f"Intentional siblings — keep both."
                            ),
                        }
                    )

    # 3) Cross-kind same root role = implementation pair (or wiring gap if unlinked).
    by_root: dict[str, list[Artifact]] = defaultdict(list)
    for art in tagged:
        by_root[root_role(art.functional_role)].append(art)

    for root, members in by_root.items():
        # Need at least one of each pair to be different kinds.
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if a.kind == b.kind:
                    continue
                pair_id = tuple(sorted([f"{a.kind}:{a.id}", f"{b.kind}:{b.id}"]))
                if pair_id in seen_pairs:
                    continue
                seen_pairs.add(pair_id)
                category = "implementation-pair" if linked(a, b) else "wiring-gap"
                pairs.append(
                    {
                        "category": category,
                        "artifacts": [
                            {"kind": a.kind, "id": a.id},
                            {"kind": b.kind, "id": b.id},
                        ],
                        "role": root,
                        "rationale": (
                            f"Both target the same functional role `{root}` "
                            + (
                                "and are wired together via the workflow graph — healthy coupling."
                                if category == "implementation-pair"
                                else "but the workflow graph does NOT link them. "
                                "Likely missing reference: the command/agent should invoke the skill."
                            )
                        ),
                    }
                )

    # Stable order: superseded > merge-candidate > wiring-gap > implementation-pair > complementary.
    rank = {
        "superseded": 0,
        "merge-candidate": 1,
        "wiring-gap": 2,
        "implementation-pair": 3,
        "complementary": 4,
    }
    pairs.sort(key=lambda p: (rank[p["category"]], p["role"]))
    return pairs


def load_analyses() -> list[dict]:
    """Load /analyze-policy archived analyses with parsed frontmatter.

    Returns a list of dicts with the fields the dashboard's Analyses tab
    needs: file, policy_id, date, title, jurisdiction, verdict, tags,
    horizon, headline numbers, and stage_5_5_corroboration status.
    """
    if not ANALYSES_DIR.exists():
        return []
    out: list[dict] = []
    for path in sorted(ANALYSES_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta, _body = parse_frontmatter(read_utf8(path), relpath(path))
        if not meta:
            continue
        jurisdiction = meta.get("jurisdiction") or {}
        if isinstance(jurisdiction, str):
            jurisdiction = {"country": jurisdiction, "state": None}
        corroboration = meta.get("stage_5_5_corroboration") or {}
        if isinstance(corroboration, str):
            corroboration = {}
        out.append({
            "file": path.name,
            "policy_id": meta.get("policy_id"),
            "date": str(meta.get("date")) if meta.get("date") else None,
            "title": meta.get("title") or path.stem,
            "jurisdiction": {
                "country": jurisdiction.get("country"),
                "state": jurisdiction.get("state"),
            },
            "verdict": meta.get("verdict"),
            "tags": list(meta.get("tags") or []),
            "horizon": meta.get("horizon"),
            "cost_billion_year1": meta.get("our_cost_billion_year1"),
            "cost_billion_10yr_actual": meta.get("our_cost_billion_10yr_actual_federal")
                or meta.get("our_cost_billion_10yr_actual_combined"),
            "gini_pct_change": meta.get("our_gini_pct_change_relative"),
            "top1_pp_change": meta.get("our_top1_share_pp_change"),
            "child_poverty_pct_change": meta.get("our_child_poverty_pct_change_relative"),
            "model_version": meta.get("model_version_at_run"),
            "data_version": meta.get("data_version_at_run"),
            "corroboration_verdict": corroboration.get("overall_verdict"),
            "issues_opened": list(meta.get("issues_opened") or []),
            "anchor_url": meta.get("anchor_url"),
        })
    return out


def assemble_manifest() -> dict:
    """Scan the repo and return the dashboard manifest."""
    skills = load_skills()
    agents = load_agents()
    commands = load_commands()
    bundles = load_bundles()
    analyses = load_analyses()
    raw_bundles = [json.loads(read_utf8(p)) for p in sorted(BUNDLES_DIR.glob("*.json"))]

    artifacts_by_kind = {
        "skill": skills,
        "agent": agents,
        "command": commands,
        "bundle": bundles,
    }

    attach_bundle_membership(artifacts_by_kind, raw_bundles)
    attach_functional_tags(artifacts_by_kind)

    known_ids = {
        kind: {a.id for a in arts}
        for kind, arts in artifacts_by_kind.items()
    }
    edges = build_edges(artifacts_by_kind, known_ids)
    attach_registry_metadata(artifacts_by_kind, edges)

    flat = skills + agents + commands + bundles
    overlaps = compute_overlaps([a for a in flat if a.kind != "bundle"])
    functional_overlaps = compute_functional_overlaps(
        [a for a in flat if a.kind != "bundle"], edges
    )
    gaps = compute_gaps(artifacts_by_kind, edges, raw_bundles)

    # Per-repo coverage across all known PolicyEngine repos.
    org_inventory = {r["name"]: r for r in load_org_repos()}
    repo_coverage: list[dict] = []
    for repo_name, repo_kind in KNOWN_REPO_KINDS:
        meta = org_inventory.get(repo_name, {})
        skills_for_repo = [
            a for a in skills if repo_name in a.target_repos
        ]
        agents_for_repo = [
            a for a in agents if repo_name in a.target_repos
        ]
        commands_for_repo = [
            a for a in commands if repo_name in a.target_repos
        ]
        repo_coverage.append(
            {
                "name": repo_name,
                "kind": repo_kind,
                "kind_label": REPO_KIND_LABELS.get(repo_kind, repo_kind),
                "tooling_relevant": repo_kind in TOOLING_RELEVANT_KINDS,
                "description": meta.get("description", ""),
                "visibility": meta.get("visibility", "PUBLIC"),
                "pushed_at": meta.get("pushed_at"),
                "skills": [a.id for a in skills_for_repo],
                "agents": [a.id for a in agents_for_repo],
                "commands": [a.id for a in commands_for_repo],
                "total": len(skills_for_repo) + len(agents_for_repo) + len(commands_for_repo),
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "counts": {
            **{kind: len(arts) for kind, arts in artifacts_by_kind.items()},
            "analysis": len(analyses),
        },
        "analyses": analyses,
        "artifacts": [artifact_to_dict(a) for a in flat],
        # Sort here as well, so the written order never depends on how the
        # code above happened to produce the edges.
        "edges": sorted(edges, key=edge_sort_key),
        "overlaps": overlaps,
        "functional_overlaps": functional_overlaps,
        "gaps": gaps,
        "bundles_raw": raw_bundles,
        "known_repos": [
            {
                "name": r,
                "kind": k,
                "kind_label": REPO_KIND_LABELS.get(k, k),
                "tooling_relevant": k in TOOLING_RELEVANT_KINDS,
            }
            for r, k in KNOWN_REPO_KINDS
        ],
        "repo_kind_labels": REPO_KIND_LABELS,
        "tooling_relevant_kinds": sorted(TOOLING_RELEVANT_KINDS),
        "repo_coverage": repo_coverage,
    }
    return manifest


def render_manifest(manifest: dict) -> str:
    """Return the manifest as the text the dashboard reads."""
    return json.dumps(manifest, indent=2)


# A rebuild with no content change rewrites only this line.
GENERATED_AT_LINE = re.compile(r'^  "generated_at": "[^"\n]*",\n', re.MULTILINE)
CHECK_DIFF_LINES = 200


def without_generated_at(text: str) -> str:
    """Blank the ``generated_at`` value, so two builds of the same content match."""
    return GENERATED_AT_LINE.sub('  "generated_at": "",\n', text, count=1)


def display_path(path: Path) -> str:
    return relpath(path) if path.is_relative_to(ROOT) else str(path)


def check_manifest(path: Path, fresh_text: str) -> int:
    """Compare the manifest at ``path`` with a fresh build; return an exit status.

    Writes nothing. Returns 0 when the two match apart from ``generated_at``.
    Otherwise prints the sections that differ and the start of a diff to
    stderr, and returns 1.
    """
    shown = display_path(path)
    fix = (
        "Rebuild it with `uv run python scripts/build_manifest.py` "
        "and commit the result."
    )
    if not path.exists():
        print(f"{shown} doesn't exist. {fix}", file=sys.stderr)
        return 1
    on_disk = without_generated_at(read_utf8(path))
    fresh = without_generated_at(fresh_text)
    if on_disk == fresh:
        print(f"{shown} matches a fresh build apart from generated_at.")
        return 0

    print(f"{shown} differs from a fresh build.", file=sys.stderr)
    try:
        old = json.loads(on_disk)
    except json.JSONDecodeError:
        print(f"{shown} isn't valid JSON.", file=sys.stderr)
    else:
        if isinstance(old, dict):
            new = json.loads(fresh)
            keys = list(new) + [key for key in old if key not in new]
            sections = [key for key in keys if old.get(key) != new.get(key)]
            print(
                "Sections that differ: "
                + (", ".join(sections) or "none, only formatting or key order"),
                file=sys.stderr,
            )
        else:
            print(f"{shown} isn't a JSON object.", file=sys.stderr)
    diff = list(
        difflib.unified_diff(
            on_disk.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            fromfile=f"{shown} (on disk)",
            tofile=f"{shown} (fresh build)",
            n=2,
        )
    )
    for line in diff[:CHECK_DIFF_LINES]:
        sys.stderr.write(line if line.endswith("\n") else line + "\n")
    if len(diff) > CHECK_DIFF_LINES:
        print(f"... {len(diff) - CHECK_DIFF_LINES} more diff lines", file=sys.stderr)
    print(fix, file=sys.stderr)
    return 1


def print_summary(manifest: dict) -> None:
    counts = manifest["counts"]
    print(
        f"  skills={counts['skill']} agents={counts['agent']} "
        f"commands={counts['command']} bundles={counts['bundle']} "
        f"analyses={counts['analysis']} edges={len(manifest['edges'])} "
        f"overlaps={len(manifest['overlaps'])} "
        f"functional_overlaps={len(manifest['functional_overlaps'])}"
    )
    by_category = Counter(p["category"] for p in manifest["functional_overlaps"])
    for category, n in sorted(by_category.items()):
        print(f"    {category}: {n}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the ecosystem dashboard manifest from this repo."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Where to write the manifest (default: {relpath(OUTPUT_PATH)}).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Build the manifest without writing it, and exit 1 if the file at "
            "--output differs from it anywhere but generated_at."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = args.output.resolve()
    if yaml is None:
        print(PYYAML_MISSING.format(executable=sys.executable), file=sys.stderr)
        return 1
    try:
        manifest = assemble_manifest()
    except FrontmatterError as error:
        print(f"build_manifest.py: {error}\nThe script wrote nothing.", file=sys.stderr)
        return 1
    text = render_manifest(manifest)
    if args.check:
        return check_manifest(output_path, text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {display_path(output_path)}")
    print_summary(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
