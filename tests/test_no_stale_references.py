"""Anti-rot lint: patterns that killed the pre-rebuild catalog may not return.

Each entry pairs a regex with the reason it is banned. A line may opt out by
placing an HTML comment marker ``<!-- stale-ok -->`` on the line immediately
before it — for deliberate "this is the superseded thing" history notes, and
for explicitly-scoped engine-development examples of patterns that are banned
only for analysis.

The Microsimulation guard is kept narrow on purpose so prose that merely
*names* the class — e.g. "a bare ``Microsimulation()``" — does not trip it.

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
        "superseded by Populace datasets (populace_us_2024 / populace_uk_2023); "
        "mark deliberate history notes with <!-- stale-ok -->",
    ),
    (
        re.compile(r"npm install @policyengine/design-system|design-system@"),
        "deprecated package; new work consumes @policyengine/ui-kit",
    ),
    (
        re.compile(r"\b[a-z0-9][a-z0-9-]*-skill\b"),
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


def iter_scan_files():
    for dirname in SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in SCAN_SUFFIXES:
                yield path


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
SKILL_INVOCATION = re.compile(r"\bSkill: ([a-z0-9][a-z0-9:-]*)")

# skills/<path> references (prose, code, bundle manifests). The lookbehind
# keeps this from matching inside longer tokens such as
# `policyengine-skills/main/...` URLs.
SKILLS_PATH = re.compile(r"(?<![A-Za-z0-9-])skills/([A-Za-z0-9_{}./-]+)")

# The one placeholder used by templated paths like skills/policyengine-{country}/.
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
                continue  # unknown template — nothing to resolve
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
