"""Regression tests for auto-routed issue destinations.

Before 2026-07-02, report-logger hardcoded `policyengine-us-data` for
INVESTIGATE-verdict issue routing and `policyengine-us` for structural, so UK
and CA reforms routed to the wrong repo. report-logger now picks the repo by
the reform's jurisdiction.country and, for UK data issues, by the dataset the
run used.

policyengine.py defaults UK runs to Microcosm's `microcosm_uk_2024_25`, and the
API runs only that default, so UK data issues go to `PolicyEngine/microcosm`.
A local run can name an Enhanced FRS or FRS file instead. policyengine-uk-data
builds those files and policyengine.py serves them only by name, as dataset
overlays, so that run's data issues go to `PolicyEngine/policyengine-uk-data`.

PolicyEngine has no Canada microdata: policyengine.py's bundle holds data for
us and uk only, and policyengine-canada's one dataset is a three-person
template. No repo builds the data a Canada issue would concern, so
report-logger files none and the archive keeps the report. Canada's structural
issues go to `PolicyEngine/policyengine-canada`.

gh looks up each `--label` name among the target repo's labels before it
creates an issue, and stops without creating it when one is missing (cli/cli
`pkg/cmd/pr/shared/params.go`, `api/queries_repo.go` LabelsToIDs). So
report-logger passes only the labels the repo has.

`resolve_issue_repo` and `issue_labels` restate report-logger.md's rules in
Python. The differential tests run the issue-filing bash block report-logger.md
gives the agent, under bash and, where installed, zsh, with a stand-in `gh` that
records each call. An edit to the block or to the rules that the other lacks
fails here.

Invariants, checked for any dataset string and any set of repo labels:
- routing returns None or a `PolicyEngine/<repo>` name;
- only INVESTIGATE and structural verdicts route to an issue, and INVESTIGATE
  routes to one only for us and uk;
- structural routing and US INVESTIGATE routing ignore the dataset;
- UK INVESTIGATE routing lands in microcosm or policyengine-uk-data and reads
  only the dataset's name: it cuts at the last "@" and keeps the last path
  segment, as policyengine.py's `dataset_logical_name` does before it drops
  the file extension, so a name and its hf:// URI agree;
- only a name that starts with the exact, lower-case `enhanced_frs_` or
  `frs_` goes to policyengine-uk-data;
- the issue carries each wanted label the repo has in some letter case and no
  other label, so gh never meets a label the repo lacks;
- report-logger's block files the issue in the reference's repo with the
  reference's labels, on any string and on the strings `edge_dataset` builds
  around those prefixes, reads the labels of that same repo, and calls gh not
  at all for ca.
"""
from __future__ import annotations

import csv
import os
import shutil
import string
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

REPORT_LOGGER = (
    Path(__file__).resolve().parents[2] / "targets" / "claude" / "agents" / "report-logger.md"
)

COUNTRY_MODEL_REPOS = {"us": "policyengine-us", "uk": "policyengine-uk", "ca": "policyengine-canada"}
UK_DATA_FILE_PREFIXES = ("enhanced_frs_", "frs_")  # files policyengine-uk-data builds
ISSUE_LABELS = ("calibration", "auto-filed")  # the labels report-logger wants on a data issue

MICROCOSM = "PolicyEngine/microcosm"
UK_DATA = "PolicyEngine/policyengine-uk-data"

VERDICTS = (
    "PASS",
    "PASS-WITH-NOTES",
    "PASS-WITH-CORROBORATION",
    "INVESTIGATE",
    "BLOCKED",
    "structural",
    "not-possible",
    "deployed-model-lag",
)

# UK datasets in the policyengine.py 6.16.0 bundle manifest, in two groups by
# the repo that builds them: Microcosm's certified datasets and one older overlay,
# then policyengine-uk-data's `dataset_overlays`, which policyengine.py serves
# only by name.
UK_MICROCOSM_DATASETS = (
    "microcosm_uk_2024_25",
    "microcosm_uk_2024_25_dense",
    "microcosm_uk_2024_25_calibration",
    "populace_uk_2023",
)
UK_DATA_FILES = (
    "enhanced_frs_2023_24",
    "enhanced_frs_2024_25",
    "enhanced_frs_2024_25_tiny",
    "frs_2023_24",
    "frs_2024_25",
    "frs_2024_25_tiny",
)
UK_DEFAULT_URI = (
    "hf://policyengine/populace-uk-private/microcosm_uk_2024_25.h5"
    "@microcosm-uk-2024-25-national-20261025T091414Z-a6299504"
)
ENHANCED_FRS_URI = "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2024_25.h5@1.58.1"
ENHANCED_FRS_BRANCH_URI = (
    "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2024_25.h5@refs/pr/3"
)

# Labels that differ from a wanted label by one character, one letter's
# script, or white space: gh resolves none of them to a wanted label.
NEAR_MISS_LABELS = (
    "calibrations",
    "recalibration",
    "calibratio",
    "c.libration",
    "calibration ",
    " calibration",
    "calibration\r",
    "calıbration",  # dotless i
    "calİbration",  # dotted capital I
    "auto-file",
    "auto-filed2",
    "auto_filed",
    "autofiled",
    "auto.filed",
    "auto-filed\t",
    "ａuto-filed",  # fullwidth a
)


def dataset_name(dataset: str | None) -> str:
    """Return the name report-logger routes by: cut at the last "@", keep the last path segment.

    policyengine.py's `dataset_logical_name` also cuts at the last "@" before it
    takes the file name, so a dataset name and its hf:// URI share a prefix. It
    then drops the file extension, which a prefix rule never reads.
    """
    return (dataset or "").rsplit("@", 1)[0].rsplit("/", 1)[-1]


def resolve_issue_repo(verdict: str, country: str, dataset: str | None = None) -> str | None:
    """Return the repo report-logger auto-routes an issue to, or None for no issue.

    `dataset` is the run's `dataset_at_run`; None or "" means the bundle default.
    """
    if verdict == "structural":
        return f"PolicyEngine/{COUNTRY_MODEL_REPOS[country]}"
    if verdict != "INVESTIGATE":
        return None
    if country == "us":
        return MICROCOSM
    if country == "uk":
        if dataset_name(dataset).startswith(UK_DATA_FILE_PREFIXES):
            return UK_DATA
        return MICROCOSM
    return None  # no Canada microdata, so no repo for a ca data issue


def gh_resolves_label(name: str, repo_labels) -> bool:
    """Return whether gh can add label `name` to an issue in a repo with `repo_labels`.

    gh compares names with Go's strings.EqualFold. For the names in ISSUE_LABELS,
    EqualFold accepts only ASCII case variants: run over every Unicode code point
    (Go 1.27), it pairs no letter of "calibration" or "auto-filed" with anything
    beyond its ASCII upper and lower case. Only k and s have such partners
    (U+212A and U+017F), and neither name holds one.
    """
    return any(label.isascii() and label.lower() == name for label in repo_labels)


def issue_labels(repo_labels) -> list[str]:
    """Return the labels report-logger passes to `gh issue create`, in order."""
    return [name for name in ISSUE_LABELS if gh_resolves_label(name, repo_labels)]


def swap_ascii_case(text: str) -> str:
    """Swap the case of A-Z and a-z, leaving every other character alone."""
    return text.translate(str.maketrans(string.ascii_letters, string.ascii_letters.swapcase()))


# --- Running report-logger's block -------------------------------------------

# Stand-in for gh, defined as a shell function ahead of the block: it records
# the call (its argument count, then each argument, NUL-terminated), answers
# `gh label list`, and accepts `gh issue create`. A function saves a process
# per call, which keeps the property tests fast.
FAKE_GH_FUNCTION = r"""gh() {
  printf '%s\0' "$#" "$@" >> "$FAKE_GH_LOG"
  case "$1 $2" in
    "label list") printf '%s' "$FAKE_GH_LABEL_LIST" ;;
    "issue create") printf '%s\n' "https://github.com/PolicyEngine/stand-in/issues/1" ;;
    *) printf 'stand-in gh: unexpected call: %s\n' "$*" >&2; return 2 ;;
  esac
}
"""
# First on PATH, so a block that reaches past the function (`command gh`)
# fails here instead of running the real gh.
GUARD_GH = """#!/bin/sh
echo "report-logger's block ran gh past the stand-in function: gh $*" >&2
exit 97
"""

SHELLS = {
    "bash": ("bash", "-c"),
    "zsh": ("zsh", "-f", "-c"),  # -f skips the user's startup files
}
SHELL_PARAMS = [
    pytest.param("bash", id="bash"),
    pytest.param(
        "zsh",
        id="zsh",
        marks=pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is not installed"),
    ),
]


@pytest.fixture(scope="session")
def fake_gh_dir(tmp_path_factory) -> Path:
    """Return a directory holding the guard gh, to put first on PATH."""
    directory = tmp_path_factory.mktemp("guard-gh")
    gh = directory / "gh"
    gh.write_text(GUARD_GH, encoding="utf-8")
    gh.chmod(0o755)
    return directory


@lru_cache(maxsize=1)
def issue_block() -> str:
    """Return report-logger's issue-filing bash block."""
    text = REPORT_LOGGER.read_text(encoding="utf-8")
    section = text.split("### Open issue mechanics", 1)[1]
    block = section.split("```bash\n", 1)[1].split("```", 1)[0]
    assert "gh issue create" in block, "report-logger's issue-filing block no longer runs gh issue create"
    return block


def label_list_call(repo: str) -> list[str]:
    """Return the `gh label list` call whose output the stand-in imitates.

    For this call gh prints each label name on its own line, with A-Z lowered by
    jq's ascii_downcase.
    """
    return ["label", "list", "--repo", repo, "--limit", "1000", "--json", "name", "--jq", ".[].name | ascii_downcase"]


def run_issue_block(shell: str, fake_gh_dir: Path, country: str, dataset: str, repo_labels) -> list[list[str]]:
    """Run report-logger's issue-filing block; return the gh calls it made, in order."""
    lowered = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "gh-calls"
        result = subprocess.run(
            [*SHELLS[shell], FAKE_GH_FUNCTION + issue_block()],
            env={
                "PATH": f"{fake_gh_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
                "LC_ALL": "C",
                "country": country,
                "dataset": dataset,
                "FAKE_GH_LOG": str(log),
                "FAKE_GH_LABEL_LIST": "\n".join(name.translate(lowered) for name in repo_labels),
            },
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        fields = log.read_bytes().split(b"\0")[:-1] if log.exists() else []
    calls = []
    while fields:
        argc = int(fields[0])
        calls.append([field.decode("utf-8", "surrogateescape") for field in fields[1 : 1 + argc]])
        fields = fields[1 + argc :]
    return calls


def gh_label_names(value: str) -> list[str]:
    """Return the label names gh reads from one --label value.

    gh's --label is a pflag StringSlice, which splits each value as one CSV
    record and reads an empty value as no names (pflag 1.0.10 readAsCSV).
    """
    return next(csv.reader([value])) if value else []


def filed_issue(calls: list[list[str]]) -> tuple[str, list[str]] | None:
    """Return (repo, label names gh looks up) for the issue filed, or None for none.

    Fails if the block made any other gh call, or read the labels of a repo
    other than the issue's.
    """
    if not calls:
        return None
    *before, create = calls
    assert create[:2] == ["issue", "create"], f"the block's last gh call is not issue create: {calls}"
    args = create[2:]
    assert len(args) % 2 == 0, f"gh issue create got a flag without a value: {args}"
    values = {"--repo": [], "--title": [], "--body": [], "--label": []}
    for flag, value in zip(args[::2], args[1::2]):
        assert flag in values, f"gh issue create got an unexpected argument {flag!r}"
        values[flag].append(value)
    assert all(len(values[flag]) == 1 for flag in ("--repo", "--title", "--body")), values
    repo = values["--repo"][0]
    assert before == [label_list_call(repo)], f"the block should read {repo}'s labels once first: {before}"
    return repo, [name for value in values["--label"] for name in gh_label_names(value)]


def expected_issue(country: str, dataset: str, repo_labels) -> tuple[str, list[str]] | None:
    """Return the issue the reference files for an INVESTIGATE run, or None."""
    repo = resolve_issue_repo("INVESTIGATE", country, dataset)
    return None if repo is None else (repo, issue_labels(repo_labels))


# --- Strategies ---------------------------------------------------------------

# Any string an environment variable can hold: no NUL, no lone surrogates.
any_dataset = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    max_size=80,
)
known_dataset = st.sampled_from(UK_MICROCOSM_DATASETS + UK_DATA_FILES)
# Hugging Face revisions: commit hashes, tags or branch names such as refs/pr/1.
revision = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126, blacklist_characters="@"),
    min_size=1,
    max_size=40,
)
repo_path = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    max_size=60,
)
# `edge_dataset` builds strings around the rule's boundary from the two
# prefixes, their near misses in case and spelling, URI heads, revisions and
# stray "@" and "/".
edge_name = st.builds(
    lambda prefix, rest: prefix + rest,
    st.sampled_from(
        ["", "frs", "frs_", "FRS_", "enhanced_frs", "enhanced_frs_", "ENHANCED_FRS_",
         "efrs_", "xfrs_", "microcosm_uk_frs_"]
    ),
    any_dataset,
)
edge_dataset = st.builds(
    lambda head, name, tail: head + name + tail,
    st.sampled_from(["", "hf://", "hf://policyengine/policyengine-uk-data-private/", "a@b/"]),
    edge_name,
    st.sampled_from(["", ".h5", "@1.58.1", ".h5@refs/pr/3", "@a@b", "/"]),
)
# Names that resemble an Enhanced FRS or FRS file name in case or spelling, or
# hold "frs_" past the start, so they miss the exact, lower-case prefix; then a
# path whose "@" sits before the revision's.
NEAR_MISSES = (
    "frs",
    "frs2024_25",
    "FRS_2024_25",
    "ENHANCED_FRS_2024_25",
    "enhanced_frs2024_25",
    "efrs_2024_25",
    "microcosm_uk_frs_x",
)
AT_IN_PATH_URI = "a@b/enhanced_frs_2024_25.h5@1.58.1"


def ascii_case_variants(name: str):
    """Strategy for `name` with each of its letters in either case."""
    return st.lists(st.booleans(), min_size=len(name), max_size=len(name)).map(
        lambda upper: "".join(c.upper() if u else c for c, u in zip(name, upper))
    )


# A label name of any characters but a newline (the block reads gh's output one
# name per line), NUL or a lone surrogate.
any_label = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00\n"),
    min_size=1,
    max_size=30,
)
repo_labels = st.lists(
    st.one_of(
        st.sampled_from(ISSUE_LABELS).flatmap(ascii_case_variants),
        st.sampled_from(NEAR_MISS_LABELS),
        any_label,
    ),
    max_size=8,
)


# --- Examples -----------------------------------------------------------------


def test_us_investigate_routes_correctly():
    assert resolve_issue_repo("INVESTIGATE", "us") == MICROCOSM


def test_us_structural_routes_correctly():
    assert resolve_issue_repo("structural", "us") == "PolicyEngine/policyengine-us"


@pytest.mark.parametrize("dataset", [None, "", UK_DEFAULT_URI, *UK_MICROCOSM_DATASETS])
def test_uk_investigate_on_microcosm_data_routes_to_microcosm(dataset):
    """The default, every API run and the other Microcosm builds go to Microcosm."""
    result = resolve_issue_repo("INVESTIGATE", "uk", dataset)
    assert result == MICROCOSM
    assert "us-data" not in result


@pytest.mark.parametrize("dataset", [ENHANCED_FRS_URI, ENHANCED_FRS_BRANCH_URI, *UK_DATA_FILES])
def test_uk_investigate_on_an_frs_file_routes_to_uk_data(dataset):
    assert resolve_issue_repo("INVESTIGATE", "uk", dataset) == UK_DATA


@pytest.mark.parametrize("dataset", NEAR_MISSES)
def test_uk_investigate_needs_an_exact_lowercase_prefix(dataset):
    assert resolve_issue_repo("INVESTIGATE", "uk", dataset) == MICROCOSM


def test_uk_investigate_cuts_the_revision_at_the_last_at():
    assert resolve_issue_repo("INVESTIGATE", "uk", AT_IN_PATH_URI) == UK_DATA


def test_uk_structural_does_not_route_to_us():
    result = resolve_issue_repo("structural", "uk")
    assert result == "PolicyEngine/policyengine-uk"
    assert result != "PolicyEngine/policyengine-us"


@pytest.mark.parametrize("dataset", [None, "", "microcosm_uk_2024_25", "enhanced_frs_2024_25"])
def test_canada_investigate_files_no_issue(dataset):
    """No repo builds Canada data, whatever dataset the run names."""
    assert resolve_issue_repo("INVESTIGATE", "ca", dataset) is None


def test_canada_structural_routes_to_policyengine_canada():
    assert resolve_issue_repo("structural", "ca") == "PolicyEngine/policyengine-canada"


def test_pass_verdicts_dont_route_to_issues():
    for verdict in ("PASS", "PASS-WITH-NOTES", "PASS-WITH-CORROBORATION"):
        for country in ("us", "uk", "ca"):
            assert resolve_issue_repo(verdict, country) is None


def test_issue_label_names_fold_only_to_ascii_case_variants():
    """gh_resolves_label holds only for lower-case ASCII names without k or s."""
    for name in ISSUE_LABELS:
        assert name.isascii() and name == name.lower()
        assert not set(name) & {"k", "s"}


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        pytest.param([], [], id="neither label, like microcosm and uk-data on 2026-11-08"),
        pytest.param(
            ["bug", "calibration"], ["calibration"], id="calibration only, like policyengine-us"
        ),
        pytest.param(["auto-filed", "calibration"], ["calibration", "auto-filed"], id="both"),
        pytest.param(["AUTO-FILED", "Calibration"], ["calibration", "auto-filed"], id="any case"),
        pytest.param(list(NEAR_MISS_LABELS), [], id="near misses"),
    ],
)
def test_issue_labels(labels, expected):
    assert issue_labels(labels) == expected


# --- Properties ---------------------------------------------------------------


@given(
    verdict=st.sampled_from(VERDICTS),
    country=st.sampled_from(sorted(COUNTRY_MODEL_REPOS)),
    dataset=st.none() | any_dataset,
)
def test_routing_returns_none_or_one_policyengine_repo(verdict, country, dataset):
    result = resolve_issue_repo(verdict, country, dataset)
    if verdict == "structural" or (verdict == "INVESTIGATE" and country in ("us", "uk")):
        assert result is not None
        owner, _, repo = result.partition("/")
        assert owner == "PolicyEngine"
        assert repo and "/" not in repo
    else:
        assert result is None


@given(
    country=st.sampled_from(sorted(COUNTRY_MODEL_REPOS)),
    dataset=any_dataset,
)
def test_structural_routing_ignores_the_dataset(country, dataset):
    assert resolve_issue_repo("structural", country, dataset) == resolve_issue_repo(
        "structural", country
    )


@given(dataset=st.none() | any_dataset)
def test_us_investigate_routes_to_microcosm_for_any_dataset(dataset):
    assert resolve_issue_repo("INVESTIGATE", "us", dataset) == MICROCOSM


@given(dataset=st.none() | any_dataset | edge_dataset)
def test_uk_investigate_lands_in_microcosm_or_uk_data(dataset):
    assert resolve_issue_repo("INVESTIGATE", "uk", dataset) in {MICROCOSM, UK_DATA}


@given(dataset=st.none() | any_dataset)
def test_ca_investigate_files_no_issue_for_any_dataset(dataset):
    assert resolve_issue_repo("INVESTIGATE", "ca", dataset) is None


@given(name=known_dataset, path=repo_path, rev=revision)
def test_uk_investigate_routes_a_uri_like_its_dataset_name(name, path, rev):
    uri = f"hf://{path}/{name}.h5@{rev}"
    assert resolve_issue_repo("INVESTIGATE", "uk", uri) == resolve_issue_repo(
        "INVESTIGATE", "uk", name
    )


@given(labels=repo_labels)
def test_issue_labels_are_wanted_labels_gh_resolves_in_order(labels):
    result = issue_labels(labels)
    assert result == [name for name in ISSUE_LABELS if name in result]
    assert all(gh_resolves_label(name, labels) for name in result)


@given(labels=repo_labels, more=repo_labels)
def test_issue_labels_never_drop_a_label_when_the_repo_gains_labels(labels, more):
    assert set(issue_labels(labels)) <= set(issue_labels(labels + more))


@given(labels=repo_labels)
def test_issue_labels_ignore_letter_case(labels):
    assert issue_labels([swap_ascii_case(label) for label in labels]) == issue_labels(labels)


# --- Differential: report-logger's block against the reference ---------------


@pytest.mark.parametrize("shell", SHELL_PARAMS)
@pytest.mark.parametrize("country", ["us", "uk"])
@pytest.mark.parametrize(
    "dataset",
    [
        "",
        UK_DEFAULT_URI,
        ENHANCED_FRS_URI,
        ENHANCED_FRS_BRANCH_URI,
        AT_IN_PATH_URI,
        *UK_MICROCOSM_DATASETS,
        *UK_DATA_FILES,
        *NEAR_MISSES,
    ],
)
def test_report_logger_bash_matches_reference(shell, fake_gh_dir, country, dataset):
    calls = run_issue_block(shell, fake_gh_dir, country, dataset, [])
    assert filed_issue(calls) == expected_issue(country, dataset, [])


@pytest.mark.parametrize("shell", SHELL_PARAMS)
@pytest.mark.parametrize("dataset", ["", "microcosm_uk_2024_25", ENHANCED_FRS_URI])
def test_report_logger_bash_files_no_issue_for_ca(shell, fake_gh_dir, dataset):
    """For ca the block calls gh not at all, not even to list labels."""
    assert run_issue_block(shell, fake_gh_dir, "ca", dataset, list(ISSUE_LABELS)) == []


@pytest.mark.parametrize("shell", SHELL_PARAMS)
@pytest.mark.parametrize(
    "labels",
    [
        pytest.param([], id="neither label"),
        pytest.param(["bug", "calibration"], id="calibration only"),
        pytest.param(["auto-filed"], id="auto-filed only"),
        pytest.param(["auto-filed", "calibration"], id="both"),
        pytest.param(["AUTO-FILED", "Calibration"], id="any case"),
        pytest.param(list(NEAR_MISS_LABELS), id="near misses"),
    ],
)
def test_report_logger_bash_passes_only_labels_the_repo_has(shell, fake_gh_dir, labels):
    calls = run_issue_block(shell, fake_gh_dir, "us", "", labels)
    assert filed_issue(calls) == (MICROCOSM, issue_labels(labels))


@pytest.mark.parametrize("shell", SHELL_PARAMS)
@settings(max_examples=150, deadline=None)
@given(
    country=st.sampled_from(["us", "uk", "ca"]),
    dataset=any_dataset | edge_dataset,
    labels=repo_labels,
)
def test_report_logger_bash_matches_reference_for_any_input(
    shell, fake_gh_dir, country, dataset, labels
):
    calls = run_issue_block(shell, fake_gh_dir, country, dataset, labels)
    assert filed_issue(calls) == expected_issue(country, dataset, labels)
