"""Every US household example must name its SPM geography.

Since policyengine 6.0.0 (policyengine-us 2.x, spm-calculator 1.0.0), the
default outputs of ``pe.us.calculate_household`` include SPM poverty, and a
household with only ``state_code`` raises ``SPMInputError``: the SPM threshold
is set by county, and a state alone does not identify one. Eight fast skill
examples broke that way before anyone noticed, because only the
``skill-examples`` job (which installs the full model) could see it.

This lint catches the same mistake in the plain ``test`` job, and in examples
that are not marked ``<!-- verify -->``: each ``pe.us.calculate_household(``
call must pass ``county_fips`` (a five-digit string) or an ``spm=`` selection.
A call written to demonstrate the error opts out with an
``# expect: SPMInputError`` comment inside the call or on the line that closes
it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = ["skills", "targets", "docs", "bundles", "presets"]
SCAN_SUFFIXES = {".md", ".py", ".ipynb"}

CALL = re.compile(r"\bpe\.us\.calculate_household\(")
GEOGRAPHY = re.compile(r"\bcounty_fips\b|\bspm\s*=")
EXPECTED_ERROR = "# expect: SPMInputError"


def call_text(text: str, open_paren: int) -> str:
    """Return the call whose "(" is at ``open_paren``, through the end of the
    line that closes it (so a trailing comment on that line belongs to it)."""
    depth = 0
    for index in range(open_paren, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                line_end = text.find("\n", index)
                return text[open_paren : len(text) if line_end == -1 else line_end]
    return text[open_paren:]


def scan_text(text: str) -> list[int]:
    """Return the line numbers of US household calls with no SPM geography."""
    missing = []
    for match in CALL.finditer(text):
        arguments = call_text(text, match.end() - 1)
        if GEOGRAPHY.search(arguments) or EXPECTED_ERROR in arguments:
            continue
        missing.append(text.count("\n", 0, match.start()) + 1)
    return missing


def iter_scan_files():
    for dirname in SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in SCAN_SUFFIXES:
                yield path


def test_us_household_calls_name_spm_geography() -> None:
    violations = []
    for path in iter_scan_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno in scan_text(text):
            violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    assert not violations, (
        "pe.us.calculate_household calls without county_fips or spm= "
        "(state_code alone raises SPMInputError since policyengine 6.0.0):\n"
        + "\n".join(violations)
    )


def test_scanner_flags_state_only_households() -> None:
    state_only = (
        "r = pe.us.calculate_household(\n"
        "    people=[{'age': 40}],\n"
        "    household={'state_code': 'CA'},\n"
        "    year=2026,\n"
        ")\n"
    )
    assert scan_text(state_only) == [1]
    # A nested call's parentheses do not end the scan early.
    nested = "pe.us.calculate_household(people=list(range(1)), household=dict(state_code='CA'))"
    assert scan_text(nested) == [1]


def test_scanner_accepts_county_spm_or_marked_error() -> None:
    county = "pe.us.calculate_household(household={'state_code': 'CA', 'county_fips': '06037'})"
    national = "pe.us.calculate_household(household={'state_code': 'CA'}, spm={'geography_kind': 'national'})"
    national_spaced = "pe.us.calculate_household(household=h, spm = selection)"
    marked = (
        "pe.us.calculate_household(**family, household={'state_code': 'CA'})"
        "  # expect: SPMInputError"
    )
    marked_inside = (
        "pe.us.calculate_household(\n"
        "    household={'state_code': 'CA'},  # expect: SPMInputError\n"
        ")"
    )
    prose = "Use `pe.us.calculate_household` for one household."
    for sample in (county, national, national_spaced, marked, marked_inside, prose):
        assert scan_text(sample) == [], sample
    # A marker on a later line belongs to whatever follows, not to this call.
    marked_later = (
        "pe.us.calculate_household(household={'state_code': 'CA'})\n"
        "# expect: SPMInputError\n"
    )
    assert scan_text(marked_later) == [1]
