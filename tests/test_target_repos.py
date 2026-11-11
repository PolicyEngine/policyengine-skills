"""Which PolicyEngine repos each skill, agent and command targets.

``scripts/build_manifest.py`` infers ``target_repos`` from the repo names and
aliases in an artifact's name, description, body and category; the
dashboard's repo coverage (``repo_coverage``), its Catalog repo filter and
some registry owners follow from it. The builder used to match aliases as
case-insensitive substrings, so "SSI" in "missing" tagged policyengine-us
and "PIP" in "pipeline" tagged policyengine-uk. It matched a repo name inside
a longer one, so every mention of policyengine-app-v2 tagged policyengine-app,
and the skill name "policyengine-model-development" tagged the
policyengine-model repo. And it read only the first 6,000 characters of a
body, so text added near the top of a long skill could drop a repo.

These tests hold the rule that replaced it. A repo name or alias counts only
where it stands as a whole token, and at each position the longest one
standing there wins. A hyphen or a dot extends a repo name or a slug-like
alias ("policyengine-us-data", "api.policyengine.org") but ends a word alias
("SNAP-eligible" mentions SNAP). A repo name or alias in capitals counts
only in capitals, and any other in any case. The whole body counts.
"""

from __future__ import annotations

import string
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_manifest import (  # noqa: E402
    KNOWN_REPOS,
    REPO_ALIASES,
    REPO_MATCHER,
    RepoMatcher,
    infer_target_repos,
)


def targets(body: str) -> list[str]:
    return infer_target_repos("an-artifact", "", body, "general")


# ---------------------------------------------------------------------------
# Examples. Most come from this repo's own skills, agents and commands.
# ---------------------------------------------------------------------------

NOT_A_MENTION = [
    # An alias inside a longer word.
    "If either value is missing, derive the same namespace.",
    "No worker edits outside its assigned files.",
    "Run the classification step when possible.",
    "The pipeline's PASS verdict requires external sources.",
    "Load the sensitivity registry.",
    "Ask the state legislative fiscal office.",
    "Use the assigned snapshot read-only.",
    # An acronym in lowercase is another word, or code.
    "uv pip install -e .",
    "The 2030 snap-back ends the credit.",
    "Compile foo.cpp first.",
    "Filter by tag (`salt`, `ctc`, `eitc`).",
    "Edit crm.py first.",
    # A repo name inside a longer token: a skill name, a file name, another
    # repo's name, a deployment's hostname.
    "Load policyengine-model-development before you edit a variable.",
    '"filename": "policyengine-atlas-pbif-grant.md"',
    "/create-dashboard --repo child-poverty-dashboard",
    "Read the URL (e.g. `marriage-zeta-beryl.vercel.app`).",
    # A hostname whose left side isn't one the aliases name.
    "The v2 alpha lives at v2.api.policyengine.org.",
    "Fetch blog.policyengine.org for narrative posts.",
    # A generic word is no longer an alias.
    "How to type the API contract for the frontend.",
]


@pytest.mark.parametrize("text", NOT_A_MENTION)
def test_text_that_mentions_no_repo_targets_none(text):
    assert targets(text) == []


MENTIONS = [
    ("Triggers: EITC, CTC, SNAP, TANF, SSI.", ["policyengine-us"]),
    ("Section 8 vouchers", ["policyengine-us"]),
    ("Optional aged/blind/disabled (non-SSI) coverage", ["policyengine-us"]),
    ("SNAP-eligible households", ["policyengine-us"]),
    ("UK: Income Tax, NI, Universal Credit.", ["policyengine-uk"]),
    ("Triggers: income tax, universal credit.", ["policyengine-uk"]),
    ("PIP rates rise in April.", ["policyengine-uk"]),
    ("Canadian benefits (CCB, CWB, OAS).", ["policyengine-canada"]),
    # Repos named outright come before repos only an alias implies.
    ("Covers SSI; see policyengine-uk.", ["policyengine-uk", "policyengine-us"]),
    ("git clone https://github.com/PolicyEngine/policyengine-us.git", ["policyengine-us"]),
    ("Open the PR against policyengine-uk.", ["policyengine-uk"]),
    ("(see `policyengine-canada`)", ["policyengine-canada"]),
    ("from policyengine_us import Simulation", ["policyengine-us"]),
    # GitHub resolves repo names in any case, and prose capitalizes them.
    ("Implement a new PolicyEngine-US state benefit.", ["policyengine-us"]),
    ("Examples: `aca-calc`.", ["ACA-Calc"]),
    ("Clone policyengine/POLICYENGINE-UK.", ["policyengine-uk"]),
    ("policyengine_us/tests/policy/contrib", ["policyengine-us"]),
    # The longest name standing at a position wins.
    ("See policyengine-us-data.", ["policyengine-us-data"]),
    ("See policyengine-us-data, then policyengine-us.", ["policyengine-us-data", "policyengine-us"]),
    ("policyengine_us_data", ["policyengine-us-data"]),
    ("Edit policyengine-app-v2/website/next.config.ts.", ["policyengine-app-v2"]),
    ("mirrors policyengine-api-v2's simulation service", ["policyengine-api-v2"]),
    ("Calculators such as `ri-ctc-calculator`.", ["ri-ctc-calculator"]),
    # The web-app and API aliases name the repos behind those hosts.
    ("Tools embed in policyengine.org.", ["policyengine-app-v2"]),
    ("Legacy UI libraries app-v2 no longer uses.", ["policyengine-app-v2"]),
    ("Call api.policyengine.org/calculate.", ["policyengine-api"]),
]


@pytest.mark.parametrize(("text", "expected"), MENTIONS)
def test_a_whole_token_mention_targets_its_repo(text, expected):
    assert targets(text) == expected


def test_a_mention_late_in_a_long_body_counts():
    # The builder read only body[:6000]; 47 of the 80 artifacts had longer
    # bodies.
    body = "Filler that names no repo.\n" * 1_000 + "Then open policyengine-uk."
    assert len(body) > 20_000
    assert targets(body) == ["policyengine-uk"]


def test_name_description_and_category_count_too():
    assert infer_target_repos("policyengine-uk", "", "", "general") == ["policyengine-uk"]
    assert infer_target_repos("x", "Covers SSI.", "", "general") == ["policyengine-us"]
    assert infer_target_repos("x", "", "", "policyengine-canada") == ["policyengine-canada"]


def test_named_repos_come_first_then_alias_only_repos():
    text = "SSI, policyengine-uk, policyengine-us-data and Canada Child Benefit"
    named = sorted(["policyengine-uk", "policyengine-us-data"], key=KNOWN_REPOS.index)
    implied = sorted(["policyengine-us", "policyengine-canada"], key=list(REPO_ALIASES).index)
    assert targets(text) == named + implied


def test_the_longest_term_starting_at_a_position_wins():
    # No two terms in today's table start a token together, so these use
    # small tables of their own.
    assert RepoMatcher(["foo", "foo.bar"], {})("see foo.bar") == ["foo.bar"]
    assert RepoMatcher(["foo", "foo.bar"], {})("see foo.") == ["foo"]
    phrases = RepoMatcher([], {"repo-a": ["Canada"], "repo-b": ["Canada Child Benefit"]})
    assert phrases("the Canada Child Benefit") == ["repo-b"]
    assert phrases("Canada's") == ["repo-a"]


# ---------------------------------------------------------------------------
# The real inventory and alias table.
# ---------------------------------------------------------------------------


def test_every_known_repo_name_targets_exactly_itself():
    # A repo name inside another (policyengine-us in policyengine-us-data,
    # policyengine-app in policyengine-app-v2, ctc-calculator in
    # ri-ctc-calculator) never counts, and neither does an alias inside a
    # repo name (Medicaid in state-medicaid-dashboard).
    for repo in KNOWN_REPOS:
        assert REPO_MATCHER(repo) == [repo], repo
        assert REPO_MATCHER(repo.replace("-", "_")) == [repo], repo


def test_every_alias_targets_a_known_repo():
    # repo_coverage lists only known repos, so an alias for any other repo
    # would tag artifacts that the coverage view never counts.
    assert set(REPO_ALIASES) <= set(KNOWN_REPOS)
    for repo, aliases in REPO_ALIASES.items():
        for alias in aliases:
            assert REPO_MATCHER(alias) == [repo], alias


@pytest.mark.parametrize(
    ("repos", "aliases"),
    [
        (["policyengine-us"], {"policyengine-uk": ["policyengine-us"]}),
        (["policyengine-us"], {"policyengine-uk": ["Policyengine_US"]}),
        ([], {"policyengine-us": ["CTC"], "policyengine-uk": ["CTC"]}),
        ([], {"policyengine-us": ["Section 8", "section 8"]}),
        ([], {"policyengine-us": [""]}),
    ],
)
def test_an_ambiguous_or_empty_alias_is_rejected(repos, aliases):
    with pytest.raises(ValueError):
        RepoMatcher(repos, aliases)


# ---------------------------------------------------------------------------
# Properties of one-term matchers.
# ---------------------------------------------------------------------------

# Repo names are slugs; so are aliases with a hyphen or a dot in them.
SLUG = st.one_of(
    st.from_regex(r"[a-z][a-z0-9]{1,8}(-[a-z0-9]{1,8}){0,3}", fullmatch=True),
    st.from_regex(r"[A-Z][A-Za-z0-9]{1,5}(-[A-Za-z0-9]{1,5})?", fullmatch=True),
    st.from_regex(r"([a-z]{2,6}\.)?[a-z]{3,10}\.(org|com|dev)", fullmatch=True),
)
# Word aliases: acronyms, names and phrases, as in REPO_ALIASES.
WORD = st.one_of(
    st.from_regex(r"[A-Z]{2,5}", fullmatch=True),
    st.from_regex(r"[A-Z][a-z]{3,9}", fullmatch=True),
    st.from_regex(r"[A-Z][a-z]{2,8}( [A-Za-z][a-z]{1,8}){1,2}", fullmatch=True),
    st.from_regex(r"[A-Z][a-z]{3,8} [0-9]{1,3}", fullmatch=True),
)
# (term, is an alias): every kind of term a matcher holds.
TERM = st.one_of(
    st.tuples(SLUG, st.just(False)),
    st.tuples(SLUG, st.just(True)),
    st.tuples(WORD, st.just(True)),
)
WORD_CHARS = string.ascii_letters + string.digits + "_"
OPENERS = ["", " ", "\n", "(", "[", "`", "'", '"', "/", "*", "**", ": "]
CLOSERS = ["", " ", "\n", ")", "]", "`", "'", '"', "/", "*", ".", ",", ";", ":", "?", "!", ".git", "'s"]


def one_term_matcher(term: str, alias: bool) -> tuple[RepoMatcher, list[str]]:
    if alias:
        return RepoMatcher([], {"some-repo": [term]}), ["some-repo"]
    return RepoMatcher([term], {}), [term]


def is_word_alias(term: str, alias: bool) -> bool:
    return alias and "-" not in term and "." not in term


@settings(deadline=None)
@given(TERM, st.data())
def test_a_term_run_into_a_longer_token_never_counts(term_alias, data):
    # "SSI" in "missing", "PIP" in "pipeline", policyengine-app in
    # policyengine-app-v2: letters, digits or underscores on either side make
    # a different token, and so does a hyphen next to a slug.
    term, alias = term_alias
    glue = WORD_CHARS if is_word_alias(term, alias) else WORD_CHARS + "-"
    before = data.draw(st.text(alphabet=glue, max_size=4), label="before")
    after = data.draw(st.text(alphabet=glue, max_size=4), label="after")
    assume(before or after)
    matcher, _ = one_term_matcher(term, alias)
    assert matcher(f"see {before}{term}{after} here") == []


@settings(deadline=None)
@given(TERM, st.sampled_from(OPENERS), st.sampled_from(CLOSERS))
def test_a_term_standing_alone_counts(term_alias, opener, closer):
    term, alias = term_alias
    matcher, expected = one_term_matcher(term, alias)
    assert matcher(f"see {opener}{term}{closer} here") == expected


@settings(deadline=None)
@given(WORD)
def test_a_hyphen_joins_a_word_alias_without_hiding_it(term):
    matcher, expected = one_term_matcher(term, alias=True)
    assert matcher(f"non-{term} cases") == expected
    assert matcher(f"{term}-eligible units") == expected


@settings(deadline=None)
@given(TERM, st.sampled_from([str.lower, str.upper, str.swapcase, str.title]))
def test_only_terms_outside_capitals_ignore_case(term_alias, recase):
    # "PIP" in capitals is Personal Independence Payment; "pip" installs
    # Python packages. "universal credit" is still Universal Credit, and
    # "PolicyEngine-US" is still policyengine-us.
    term, alias = term_alias
    variant = recase(term)
    matcher, expected = one_term_matcher(term, alias)
    counts = variant == term or not term.isupper()
    assert matcher(f"see {variant} here") == (expected if counts else [])


# ---------------------------------------------------------------------------
# Properties of the real matcher.
# ---------------------------------------------------------------------------

# Lines with real names, aliases, import names and near misses, plus noise.
REAL_LINES = [
    "Covers SSI and TANF.",
    "If a value is missing, stop.",
    "Run the pipeline in process-test mode.",
    "uv pip install -e .",
    "PIP and Universal Credit",
    "Read the population registry.",
    "Take a memory snapshot; SNAP-eligible units.",
    "See policyengine-us-data and policyengine-us.",
    "Edit policyengine-app-v2/website/next.config.ts.",
    "Load policyengine-model-development.",
    "Call api.policyengine.org/calculate.",
    "Embeds in policyengine.org.",
    "from policyengine_uk import Microsimulation",
    "git clone https://github.com/PolicyEngine/policyengine-canada.git",
    "GIS, OAS and CPP",
    "Compile foo.cpp.",
    "Section 8",
]
NOISE = st.text(alphabet=string.ascii_letters + string.digits + " .,;:-_/()`'\"", max_size=40)
# Longer than the old 6,000-character cut-off on its own, and names no repo.
FILLER = "Filler that names nothing at all. " * 200
LINE = st.one_of(st.sampled_from(REAL_LINES), NOISE, st.just(FILLER))
# Half the inserted blocks open with FILLER, so they push what follows them
# past where the old cut-off fell.
INSERTED = st.lists(LINE, min_size=1, max_size=5).flatmap(
    lambda lines: st.sampled_from([lines, [FILLER, *lines]])
)


@settings(deadline=None)
@given(st.lists(LINE, max_size=10), INSERTED, st.data())
def test_inserting_lines_never_removes_a_repo(lines, inserted, data):
    # The old body[:6000] cut-off broke this: lines added near the top of a
    # long body pushed a later mention past it.
    at = data.draw(st.integers(0, len(lines)), label="at")
    before = targets("\n".join(lines))
    after = targets("\n".join(lines[:at] + inserted + lines[at:]))
    assert set(before) <= set(after)
    if not targets("\n".join(inserted)):
        assert after == before


@settings(deadline=None)
@given(st.lists(LINE, max_size=10), st.data())
def test_line_order_never_changes_target_repos(lines, data):
    shuffled = data.draw(st.permutations(lines), label="shuffled")
    assert REPO_MATCHER("\n".join(shuffled)) == REPO_MATCHER("\n".join(lines))


def reference_targets(text: str, repos: list[str], aliases: dict[str, list[str]]) -> list[str]:
    """The documented rule again, by plain string comparison instead of a regex."""

    def word_char(char: str) -> bool:  # what \w matches in a str pattern
        return char.isalnum() or char == "_"

    terms = [(repo, repo, False) for repo in repos]
    terms += [(repo.replace("-", "_"), repo, False) for repo in repos if "-" in repo]
    terms += [(alias, repo, True) for repo, texts in aliases.items() for alias in texts]
    terms.sort(key=lambda term: (-len(term[0]), term[0]))
    by_first = defaultdict(list)  # candidates for a position, longest first
    for term in terms:
        by_first[term[0][0].lower()].append(term)

    named, implied = set(), set()
    i = 0
    while i < len(text):
        before = text[i - 1] if i else ""
        for term, repo, alias in by_first.get(text[i].lower(), []):
            word = alias and "-" not in term and "." not in term
            end = i + len(term)
            after = text[end] if end < len(text) else ""
            if not term.isupper():
                same = text[i:end].lower() == term.lower()
            else:
                same = text[i:end] == term
            if not same or word_char(before) or word_char(after):
                continue
            if not word and (before in ("-", ".") or after == "-"):
                continue
            (implied if alias else named).add(repo)
            i = end
            break
        else:
            i += 1
    return [r for r in repos if r in named] + [
        r for r in aliases if r in implied and r not in named
    ]


TERM_IN_ANY_CASE = st.sampled_from([term.text for term in REPO_MATCHER.terms]).flatmap(
    lambda text: st.sampled_from([text, text.lower(), text.upper(), text.title()])
)
PIECE = st.one_of(
    TERM_IN_ANY_CASE,
    st.sampled_from(list(" \n.,;:-_/()`'\"") + ["s", "x", "1", "non-", "-data", ".git", "api."]),
    st.text(alphabet=string.ascii_letters + string.digits, max_size=6),
)


@settings(deadline=None, max_examples=300)
@given(st.lists(PIECE, max_size=30))
def test_matcher_agrees_with_a_plain_string_scan(pieces):
    text = "".join(pieces)
    assert REPO_MATCHER(text) == reference_targets(text, KNOWN_REPOS, REPO_ALIASES)


# Small tables over a tiny alphabet, so terms overlap, nest and share starts.
# The pools hold terms that start other terms ("a", "a." and "a.b"), which
# random strings rarely produce.
TINY_NAME = st.one_of(
    st.sampled_from(["a", "a.", "a.b", "a-b", "ab", "AB", "b", "b.a", "a.b-a"]),
    st.from_regex(r"[abAB][abAB.\-]{0,3}", fullmatch=True),
)
TINY_ALIAS = st.one_of(
    st.sampled_from(["A", "A b", "A-b", "A.b", "B", "b a", "Ab", "A b-a"]),
    st.from_regex(r"[aAbB][aAbB .\-]{0,3}", fullmatch=True),
)
TINY_CHAR = st.sampled_from(list("aAbB .-_x\n"))


@settings(deadline=None, max_examples=300)
@given(
    st.lists(TINY_NAME, unique=True, max_size=4),
    st.dictionaries(
        st.sampled_from(["r1", "r2", "r3"]), st.lists(TINY_ALIAS, max_size=3), max_size=3
    ),
    st.data(),
)
def test_any_table_agrees_with_a_plain_string_scan(repos, aliases, data):
    try:
        matcher = RepoMatcher(repos, aliases)
    except ValueError:
        assume(False)
    # Build the text from the table's own terms, recased, and single
    # characters, so terms run into each other, nest and repeat.
    texts = [term.text for term in matcher.terms]
    piece = TINY_CHAR
    if texts:
        recased = st.sampled_from(texts).flatmap(
            lambda text: st.sampled_from([text, text.lower(), text.upper()])
        )
        piece = st.one_of(recased, TINY_CHAR)
    text = "".join(data.draw(st.lists(piece, max_size=16), label="pieces"))
    assert matcher(text) == reference_targets(text, repos, aliases)
