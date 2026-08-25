"""Anti-rot lint: patterns that killed the pre-rebuild catalog may not return.

Each entry pairs a regex with the reason it is banned. A line may opt out by
placing an HTML comment marker ``<!-- stale-ok -->`` on the line immediately
before it — for deliberate "this is the superseded thing" history notes, and
for explicitly-scoped engine-development examples of patterns that are banned
only for analysis.

The Microsimulation guard is kept narrow on purpose so prose that merely
*names* the class — e.g. "a bare ``Microsimulation()``" — does not trip it.

The product-name guard is span-based: frozen dataset IDs and machine surfaces
are explicitly allowlisted without exempting stale prose elsewhere on the same
line. Dated analyses and the dataset-naming regression corpus remain verbatim.

Caught: same-line imports, paren-wrapped multiline imports, backslash
continuations occurring after ``import``, and same-line module-qualified
constructors. Word boundaries on both sides of the package name keep sibling
packages (``policyengine_us_data``) and prefixed identifiers
(``notpolicyengine_us``) clean.

Documented residual misses — pinned by ``MICROSIM_KNOWN_MISSES`` below, and
reviewer territory until then: backslash continuations *before* ``import``,
hybrid backslash-then-paren imports, aliased constructors
(``import policyengine_us as x; x.Microsimulation()``), ``import *`` forms,
and qualified constructors whose dot is split across lines. If the guard is
ever tightened, move the newly-caught spelling from ``MICROSIM_KNOWN_MISSES``
to ``MICROSIM_BANNED_SAMPLES`` to record the improvement.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

MICROSIM_REASON = (
    "direct country-package Microsimulation is deprecated for analysis "
    "(2026-08-01); use pe.{us,uk}.managed_microsimulation() from "
    "policyengine>=5.0.1 — deliberate deprecation notes and explicitly-scoped "
    "engine-development examples take <!-- stale-ok -->"
)

# (pattern, reason) — matched line by line
FORBIDDEN: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"hf://policyengine/policyengine-us-data"),
        "policyengine-us-data is archived; datasets resolve by name from the "
        "certified bundle (populace_us_2024 / populace_us_2024_acs_local)",
    ),
    (
        re.compile(r"(states|districts)/[A-Z]{2}(-\d+)?\.h5"),
        "per-state/district H5 files were removed; filter one national dataset "
        "by geography columns",
    ),
    (
        re.compile(r"@mantine/|Mantine"),
        "app-v2 has zero Mantine dependencies",
    ),
    (
        re.compile(r"USHouseholdInput|UKHouseholdInput|calculate_household_impact"),
        "deleted policyengine.py API; use pe.{us,uk}.calculate_household",
    ),
    (
        re.compile(r"changelog_entry\.yaml"),
        "deprecated changelog format; use towncrier fragments in changelog.d/",
    ),
    (
        re.compile(r"policyengine-app/src"),
        "policyengine-app (v1) is archived; use policyengine-app-v2 paths",
    ),
    (
        re.compile(r"\benhanced_cps_2024\b|\benhanced_frs_2023_24\b"),
        "superseded by Microcosm datasets (populace_us_2024 / populace_uk_2023); "
        "mark deliberate history notes with <!-- stale-ok -->",
    ),
    (
        re.compile(r"npm install @policyengine/design-system|design-system@"),
        "deprecated package; new work consumes @policyengine/ui-kit",
    ),
    (
        re.compile(r"\b[a-z0-9][a-z0-9-]*-skill\b", re.IGNORECASE),
        "pre-rebuild skill naming (e.g. policyengine-us-skill); current skills "
        "use the short directory name in skills/ (e.g. policyengine-us)",
    ),
    (
        # module-qualified constructor: policyengine_us.Microsimulation(...).
        # (?<!\w) rejects prefixed identifiers (notpolicyengine_us.…); \b keeps
        # policyengine_us_data and other sibling packages out.
        re.compile(r"(?<!\w)policyengine_(us|uk)\b\s*\.\s*Microsimulation\b"),
        MICROSIM_REASON,
    ),
]

# (pattern, reason) — matched against whole-file text, for import statements
# whose logical line a per-line scan cannot see. ``(?:[^\n\\]|\\\n)*`` walks a
# logical line: any char except newline/backslash, or a backslash-newline
# continuation — so same-line AND backslash-continued imports both match, while
# a plain newline still terminates the search. ``[^)]*`` in the paren form
# crosses newlines but cannot run past the closing paren.
FORBIDDEN_MULTILINE: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"from\s+policyengine_(us|uk)\b[\w.]*(?:[^\n\\]|\\\n)*\bMicrosimulation\b"
        ),
        MICROSIM_REASON,
    ),
    (
        re.compile(
            r"from\s+policyengine_(us|uk)\b[\w.]*\s+import\s*\([^)]*\bMicrosimulation\b"
        ),
        MICROSIM_REASON,
    ),
]

SCAN_DIRS = ["skills", "targets", "docs", "bundles", "presets"]
SCAN_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".sh", ".html", ".ipynb"}
STALE_OK = "<!-- stale-ok -->"

STALE_PRODUCT_REASON = (
    "Populace and Ledger were renamed on 2026-08-07; use Microcosm and Chronicle "
    "in prose. Frozen identifiers require an explicit allowlist entry."
)
STALE_PRODUCT_NAME = re.compile(
    r"(?<![A-Za-z])(?:populace|ledger)(?![A-Za-z])",
    re.IGNORECASE,
)

# A stale-name match is allowed only when its exact span falls inside one of
# these frozen machine surfaces. Do not add bare ``populace-data`` here: only
# the certified bundle's versioned legacy dist name is frozen; current shard
# teaching must say ``microcosm-data``.
FROZEN_PRODUCT_SPANS = (
    re.compile(r"\bpopulace_us_2024[A-Za-z0-9_]*\b"),
    re.compile(r"\bpopulace_uk_2023\b"),
    re.compile(r"\bpopulace-(?:us-2024|uk-2023)\b"),
    re.compile(
        r"policyengine/populace-(?:us(?:-staging)?|uk-private|"
        r"be-(?:\*|[A-Za-z0-9][A-Za-z0-9-]*))"
        r"(?![A-Za-z0-9_-])"
    ),
    re.compile(r"\bPOPULACE_(?:[A-Z0-9_]+|\*)(?![A-Za-z0-9_*-])"),
    re.compile(r"--ledger-[a-z0-9-]+(?![A-Za-z0-9_-])"),
    re.compile(r"\bledger_(?:[A-Za-z0-9_]+|\*)(?![A-Za-z0-9_*-])"),
    re.compile(r"#populace(?:-(?:us|uk))?(?![A-Za-z0-9_-])"),
    re.compile(r"Microcosm \(formerly Populace\)"),
    re.compile(
        r"(?:https://calibration-diagnostics\.vercel\.app)?"
        r"/calibration/dashboard/(?:api/)?populace(?![A-Za-z0-9_-])"
    ),
    re.compile(r"\bpopulace-data\b`?(?:==|\s+)0\.1\.0(?![A-Za-z0-9_.-])"),
    re.compile(
        r"data_package\.name\s*=\s*[\"']populace-data[\"']"
    ),
)

PRODUCT_SCAN_DIRS = [*SCAN_DIRS, "scripts", "dashboard/src", "tests"]
PRODUCT_SCAN_SUFFIXES = SCAN_SUFFIXES | {".ts", ".tsx", ".js", ".jsx"}
PRODUCT_SCAN_ROOT_FILES = ["README.md"]
PRODUCT_SCAN_EXCLUDED = {
    "analyses",  # dated records are frozen verbatim
    "dashboard/src/data/manifest.json",  # generated from the source files
    "tests/pipeline/test_dataset_naming.py",  # frozen dataset-name pins
    "tests/test_no_stale_references.py",  # guard patterns and corpus
}

# Exact lowercase bookkeeping phrases. Uppercase Ledger remains forbidden so
# the branded product cannot slip through these path-scoped exceptions.
PATH_GENERIC_LEDGER_SPANS: dict[str, tuple[re.Pattern[str], ...]] = {
    "skills/encode-policy-v2/references/workflow.md": (
        re.compile(r"\brun ledger[.,]"),
        re.compile(r"\bFresh/resume ledger$"),
        re.compile(r"\bphase ledger\."),
        re.compile(r"\bthe ledger proves\b"),
        re.compile(r"\bin the ledger[.;]"),
        re.compile(r"\bledger:"),
        re.compile(r"\bShort ledger\s*\|"),
    ),
    "skills/review-program/references/workflow.md": (
        re.compile(r"\bcompleted ledger with\b"),
        re.compile(r"\brun-state ledger \(for metrics\)"),
        re.compile(r"^\s*ledger\)\."),
    ),
    "targets/claude/agents/calibration-diagnostics.md": (
        re.compile(r"\bledger metadata\b"),
    ),
}

# Exact compatibility/search literals that are machine surfaces but do not
# belong to a broader frozen identifier family.
PATH_FROZEN_PRODUCT_SPANS: dict[str, tuple[re.Pattern[str], ...]] = {
    "scripts/functional_tags.json": (
        re.compile(r"data:populace(?![A-Za-z0-9_-])"),
    ),
    "skills/policyengine-data/SKILL.md": (
        re.compile(r"[\"']populace[\"']\s+in\s+DEFAULT_DATASET"),
    ),
    "skills/policyengine/SKILL.md": (
        re.compile(r"\.startswith\([\"']populace_us[\"']\)"),
    ),
    "skills/policyengine-uk/SKILL.md": (
        re.compile(r"\bpopulace_uk(?![A-Za-z0-9_-])"),
    ),
    "targets/claude/agents/microsim-runner.md": (
        re.compile(r"[\"']populace[\"']\s+in\s+data_version"),
    ),
}


def iter_scan_files():
    for dirname in SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in SCAN_SUFFIXES:
                yield path


def iter_product_scan_files():
    """Yield source files whose prose and machine surfaces teach product names."""
    yielded: set[Path] = set()
    for relpath in PRODUCT_SCAN_ROOT_FILES:
        path = REPO_ROOT / relpath
        if path.is_file():
            yielded.add(path)
            yield path
    for dirname in PRODUCT_SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in PRODUCT_SCAN_SUFFIXES:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in PRODUCT_SCAN_EXCLUDED or any(
                rel == excluded or rel.startswith(f"{excluded}/")
                for excluded in PRODUCT_SCAN_EXCLUDED
            ):
                continue
            if path not in yielded:
                yielded.add(path)
                yield path


def frozen_product_spans(line: str, relpath: str) -> list[tuple[int, int]]:
    patterns = [
        *FROZEN_PRODUCT_SPANS,
        *PATH_FROZEN_PRODUCT_SPANS.get(relpath, ()),
        *PATH_GENERIC_LEDGER_SPANS.get(relpath, ()),
    ]
    return [match.span() for pattern in patterns for match in pattern.finditer(line)]


def scan_stale_product_names(
    text: str,
    relpath: str = "README.md",
) -> list[tuple[int, str]]:
    """Return stale product-name tokens not contained by a frozen span."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        allowed = frozen_product_spans(line, relpath)
        for match in STALE_PRODUCT_NAME.finditer(line):
            if any(start <= match.start() and match.end() <= end for start, end in allowed):
                continue
            found.append((lineno, match.group()))
    return found


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """Return (lineno, pattern, reason) violations in ``text``, honoring stale-ok."""
    lines = text.splitlines()

    def exempt(lineno: int) -> bool:
        prev = lines[lineno - 2] if lineno >= 2 else ""
        line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
        return STALE_OK in prev or STALE_OK in line

    found: dict[tuple[int, str], str] = {}
    for lineno, line in enumerate(lines, start=1):
        if exempt(lineno):
            continue
        for pattern, reason in FORBIDDEN:
            if pattern.search(line):
                found.setdefault((lineno, pattern.pattern), reason)
    for pattern, reason in FORBIDDEN_MULTILINE:
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            if exempt(lineno):
                continue
            found.setdefault((lineno, pattern.pattern), reason)
    return [(lineno, pat, reason) for (lineno, pat), reason in sorted(found.items())]


def test_no_stale_references() -> None:
    violations: list[str] = []
    for path in iter_scan_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, pattern, reason in scan_text(text):
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}:{lineno}: {pattern!r} — {reason}")
    assert not violations, "Stale references found:\n" + "\n".join(violations)


def test_no_stale_product_names() -> None:
    violations: list[str] = []
    for path in iter_product_scan_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, token in scan_stale_product_names(text, rel):
            violations.append(f"{rel}:{lineno}: {token!r} — {STALE_PRODUCT_REASON}")
    assert not violations, "Stale product names found:\n" + "\n".join(violations)


# --- Corpus for the product-name guard --------------------------------------

STALE_PRODUCT_BANNED_SAMPLES = [
    ("The Populace stack builds the data.", 1),
    ("Check the populace release before scoring.", 1),
    ("Facts are Ledger's lane.", 1),
    ("Route work to PolicyEngine/populace.", 1),
    ("Use the ~/PolicyEngine/populace mirror.", 1),
    ("Install populace-frame and import populace.fit.", 2),
    ("See https://populace.dev.", 1),
    ("Populace uses populace_us_2024.", 1),
    ("Populace_US_2024 is not a frozen identifier.", 1),
    ("Populace-us-2024-deadbeef is not a frozen identifier.", 1),
    ("--Ledger-facts is not the frozen lowercase flag.", 1),
    ("#populace-new is not a frozen Slack channel.", 1),
    ("#populace-us-extra is not a frozen Slack channel.", 1),
    ("#populace_new is not a frozen Slack channel.", 1),
    ("policyengine/populace-us_extra is not a frozen dataset ID.", 1),
    ("--ledger-facts_extra is not a frozen CLI flag.", 1),
    ("/calibration/dashboard/api/populace2 is not a live route.", 1),
    ("/calibration/dashboard/populace-old is not a live route.", 1),
    ("POPULACE_TOKEN-extra is not a frozen environment token.", 1),
    ("ledger_facts-extra is not a frozen field name.", 1),
]

STALE_PRODUCT_PATH_BANNED_SAMPLES = [
    (
        "scripts/functional_tags.json",
        '"role": "data:populace-old"',
    ),
    (
        "skills/encode-policy-v2/references/workflow.md",
        "the ledger product uploads facts",
    ),
    (
        "skills/policyengine-uk/SKILL.md",
        "populace_uk-old",
    ),
]

STALE_PRODUCT_ALLOWED_SAMPLES = [
    ("README.md", "Microcosm (formerly Populace)"),
    ("README.md", "populace_us_2024_acs_local"),
    ("README.md", "populace_uk_2023"),
    ("README.md", "populace-us-2024-<sha>-<ts>"),
    ("README.md", "populace-uk-2023-dd68c73-..."),
    ("README.md", "policyengine/populace-us"),
    ("README.md", "policyengine/populace-us-staging"),
    ("README.md", "policyengine/populace-uk-private"),
    ("README.md", "policyengine/populace-be-*"),
    ("README.md", "POPULACE_TOKEN"),
    ("README.md", "POPULACE_*"),
    ("README.md", "--ledger-facts"),
    ("README.md", "ledger_facts"),
    ("README.md", "ledger_*"),
    ("README.md", "#populace #populace-us #populace-uk"),
    (
        "README.md",
        "https://calibration-diagnostics.vercel.app/calibration/dashboard/api/populace",
    ),
    ("README.md", "/calibration/dashboard/populace"),
    ("README.md", "populace-data==0.1.0"),
    ("README.md", "`populace-data` 0.1.0"),
    ("README.md", 'data_package.name="populace-data"'),
    ("README.md", "knowledgeRoles"),
    (
        "skills/encode-policy-v2/references/workflow.md",
        "record the reason in the run ledger. Use a short phase ledger.",
    ),
    (
        "skills/review-program/references/workflow.md",
        "read the run-state ledger (for metrics)",
    ),
    (
        "targets/claude/agents/calibration-diagnostics.md",
        "the packet includes ledger metadata",
    ),
    ("scripts/functional_tags.json", '"role": "data:populace"'),
    (
        "skills/policyengine-data/SKILL.md",
        '`test_microsim.py` asserts `"populace" in DEFAULT_DATASET`',
    ),
    (
        "skills/policyengine/SKILL.md",
        'assert value.startswith("populace_us")',
    ),
    ("skills/policyengine-uk/SKILL.md", "Triggers: populace_uk"),
    (
        "targets/claude/agents/microsim-runner.md",
        '"populace" in data_version',
    ),
]


@pytest.mark.parametrize(("sample", "expected_hits"), STALE_PRODUCT_BANNED_SAMPLES)
def test_product_name_guard_catches(sample: str, expected_hits: int) -> None:
    hits = scan_stale_product_names(sample)
    assert len(hits) == expected_hits, (
        f"guard found {len(hits)} stale names, expected {expected_hits}: {sample!r}"
    )


@pytest.mark.parametrize(("relpath", "sample"), STALE_PRODUCT_PATH_BANNED_SAMPLES)
def test_product_name_guard_keeps_path_exceptions_tight(
    relpath: str,
    sample: str,
) -> None:
    hits = scan_stale_product_names(sample, relpath)
    assert len(hits) == 1, f"path exception hid stale product prose: {sample!r}"


@pytest.mark.parametrize(("relpath", "sample"), STALE_PRODUCT_ALLOWED_SAMPLES)
def test_product_name_guard_allows(relpath: str, sample: str) -> None:
    hits = scan_stale_product_names(sample, relpath)
    assert not hits, f"guard false-positived on frozen spelling: {sample!r}"


# --- Corpus for the Microsimulation guard -----------------------------------
# Pins the guard's behavior: every banned spelling below must trip it, every
# allowed spelling must pass. Extend both lists when the patterns change.

MICROSIM_BANNED_SAMPLES = [
    "from policyengine_us import Microsimulation",
    "from policyengine_uk import Microsimulation",
    "from policyengine_us import Simulation, Microsimulation",
    "from  policyengine_us  import  Microsimulation",
    "from policyengine_us.microsimulation import Microsimulation",
    "sim = policyengine_us.Microsimulation()",
    "sim = policyengine_uk . Microsimulation(reform=reform)",
    "from policyengine_us import (\n    Microsimulation,\n)",
    "from policyengine_uk import (\n    Simulation,\n    Microsimulation,\n)",
    "from policyengine_us import \\\n    Microsimulation",
    "from policyengine_uk \\\n    import Microsimulation",
    "from policyengine_us import Simulation, \\\n    Microsimulation",
]

MICROSIM_ALLOWED_SAMPLES = [
    "sim = pe.us.managed_microsimulation()",
    "sim = pe.uk.managed_microsimulation(reform=reform)",
    "from policyengine_us import Simulation",
    "from policyengine_uk import CountryTaxBenefitSystem",
    "from policyengine_us import (\n    Simulation,\n    CountryTaxBenefitSystem,\n)",
    "from policyengine_us import \\\n    Simulation",
    "from policyengine_us_data import Microsimulation",
    "the notpolicyengine_us.Microsimulation identifier is unrelated",
    "a bare `Microsimulation()` is already post-July-2025 UC law",
    "The country-package `Microsimulation(reform=...)` accepts either form",
    "<!-- stale-ok -->\nfrom policyengine_us import Microsimulation  # deprecation note",
]

# Spellings that SHOULD be banned but deliberately evade the current patterns
# (regex reach vs false-positive trade-off — see module docstring). Pinned so
# the guard's blind spots are explicit; a tightening that catches one should
# move it to MICROSIM_BANNED_SAMPLES.
MICROSIM_KNOWN_MISSES = [
    "from policyengine_us \\\n    import (\n    Microsimulation,\n)",
    "from \\\n    policyengine_us import Microsimulation",
    "import policyengine_us as pe_us\nsim = pe_us.Microsimulation()",
    "from policyengine_us import *\nsim = Microsimulation()",
    "sim = policyengine_us.\\\n    Microsimulation()",
]


@pytest.mark.parametrize("sample", MICROSIM_BANNED_SAMPLES)
def test_microsim_guard_catches(sample: str) -> None:
    hits = [reason for _, _, reason in scan_text(sample) if reason == MICROSIM_REASON]
    assert hits, f"guard missed banned spelling: {sample!r}"


@pytest.mark.parametrize("sample", MICROSIM_ALLOWED_SAMPLES)
def test_microsim_guard_allows(sample: str) -> None:
    hits = [reason for _, _, reason in scan_text(sample) if reason == MICROSIM_REASON]
    assert not hits, f"guard false-positived on allowed spelling: {sample!r}"


@pytest.mark.parametrize("sample", MICROSIM_KNOWN_MISSES)
def test_microsim_guard_known_misses(sample: str) -> None:
    """Pins the guard's documented blind spots (they are misses, not features)."""
    hits = [reason for _, _, reason in scan_text(sample) if reason == MICROSIM_REASON]
    assert not hits, (
        f"guard now catches {sample!r} — move it from MICROSIM_KNOWN_MISSES "
        "to MICROSIM_BANNED_SAMPLES to record the improvement"
    )


SKILLS_DIR = REPO_ROOT / "skills"

# `Skill: <name>` load instructions in agent/command files. Plugin-qualified
# names (`Skill: plugin:name`) resolve outside this repo and are skipped.
SKILL_INVOCATION = re.compile(r"\bSkill: ([a-z0-9][a-z0-9_:-]*)")

# skills/<path> references (prose, code, bundle manifests). The lookbehind
# keeps this from matching inside longer tokens such as
# `policyengine-skills/main/...` URLs.
SKILLS_PATH = re.compile(r"(?<![A-Za-z0-9-])skills/([A-Za-z0-9_{}./-]+)")

# Directory-name expansions for templated paths like
# skills/policyengine-{country}/. NOTE: the /analyze-policy --country flag value
# `ca` maps to the DIRECTORY `policyengine-canada`; command files must spell
# that mapping out explicitly instead of relying on the template (see
# analyze-policy.md), because flag vocabulary and directory names differ.
COUNTRY_EXPANSIONS = ("us", "uk", "canada")


def existing_skill_names() -> set[str]:
    return {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}


def iter_lines_with_stale_ok():
    for path in iter_scan_files():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, start=1):
            prev = lines[lineno - 2] if lineno >= 2 else ""
            if STALE_OK in prev or STALE_OK in line:
                continue
            yield path, lineno, line


def test_skill_invocations_resolve() -> None:
    """Every `Skill: <name>` load instruction names a directory in skills/."""
    known = existing_skill_names()
    violations: list[str] = []
    for path, lineno, line in iter_lines_with_stale_ok():
        for name in SKILL_INVOCATION.findall(line):
            name = name.rstrip(":-")
            if ":" in name:
                continue
            if name not in known:
                rel = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}:{lineno}: `Skill: {name}` — no skills/{name}/ directory"
                )
    assert not violations, (
        "Skill load instructions referencing nonexistent skills:\n"
        + "\n".join(violations)
    )


def test_referenced_skills_paths_exist() -> None:
    """Every skills/... path referenced anywhere resolves inside this repo."""
    violations: list[str] = []
    for path, lineno, line in iter_lines_with_stale_ok():
        for match in SKILLS_PATH.finditer(line):
            ref = match.group(1).rstrip("./")
            if "{country}" in ref:
                candidates = [ref.replace("{country}", c) for c in COUNTRY_EXPANSIONS]
            elif "{" in ref:
                rel = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}:{lineno}: skills/{ref} — unknown template "
                    "placeholder (only {country} is expandable)"
                )
                continue
            else:
                candidates = [ref]
            for candidate in candidates:
                if not (SKILLS_DIR / candidate).exists():
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(
                        f"{rel}:{lineno}: skills/{ref} — skills/{candidate} does not exist"
                    )
                    break
    assert not violations, (
        "References to nonexistent skills/ paths:\n" + "\n".join(violations)
    )
