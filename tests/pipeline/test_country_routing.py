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

`resolve_issue_repo` restates report-logger.md's rule in Python. The
differential tests run the bash snippet report-logger.md gives the agent on
the same inputs, so an edit to one that the other lacks fails here.

Invariants, checked for any dataset string:
- routing returns None or a `PolicyEngine/<repo>` name;
- only INVESTIGATE and structural verdicts route to an issue;
- structural routing and US INVESTIGATE routing ignore the dataset;
- UK INVESTIGATE routing lands in microcosm or policyengine-uk-data and reads
  only the dataset's name, which it takes the way policyengine.py's
  `dataset_logical_name` does (drop any @revision, keep the last path
  segment), so a name and its hf:// URI agree;
- report-logger's bash and `resolve_issue_repo` agree for `us` and `uk`.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

REPORT_LOGGER = (
    Path(__file__).resolve().parents[2] / "targets" / "claude" / "agents" / "report-logger.md"
)

COUNTRY_MODEL_REPOS = {"us": "policyengine-us", "uk": "policyengine-uk", "ca": "policyengine-canada"}
OTHER_DATA_REPOS = {"ca": "policyengine-canada-data"}
UK_DATA_FILE_PREFIXES = ("enhanced_frs_", "frs_")  # files policyengine-uk-data builds

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

# UK datasets in the policyengine.py 6.16.0 bundle manifest, grouped by the
# repo that builds them: Microcosm's certified datasets and one older overlay,
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


def dataset_name(dataset: str | None) -> str:
    """Return the name report-logger routes by: drop any @revision, keep the last path segment.

    policyengine.py's `dataset_logical_name` also cuts at the last "@" before it
    takes the file name, so a dataset name and its hf:// URI share a prefix.
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
    return f"PolicyEngine/{OTHER_DATA_REPOS[country]}"


@lru_cache(maxsize=1)
def routing_snippet() -> str:
    """Return the lines of report-logger's issue-filing bash block that set DATA_REPO."""
    text = REPORT_LOGGER.read_text(encoding="utf-8")
    section = text.split("### Open issue mechanics", 1)[1]
    block = section.split("```bash\n", 1)[1].split("```", 1)[0]
    snippet = block.split("gh issue create", 1)[0]
    assert "DATA_REPO=" in snippet, "report-logger's issue-filing block no longer sets DATA_REPO"
    return snippet


def run_routing_snippet(country: str, dataset: str) -> str:
    """Run report-logger's bash routing for one country and dataset; return DATA_REPO."""
    result = subprocess.run(
        ["bash", "-c", routing_snippet() + '\nprintf %s "$DATA_REPO"'],
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LC_ALL": "C",
            "country": country,
            "dataset": dataset,
        },
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


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


# --- Examples --------------------------------------------------------------


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


def test_uk_structural_does_not_route_to_us():
    result = resolve_issue_repo("structural", "uk")
    assert result == "PolicyEngine/policyengine-uk"
    assert result != "PolicyEngine/policyengine-us"


def test_canada_investigate_routes_correctly():
    assert resolve_issue_repo("INVESTIGATE", "ca") == "PolicyEngine/policyengine-canada-data"


def test_pass_verdicts_dont_route_to_issues():
    for verdict in ("PASS", "PASS-WITH-NOTES", "PASS-WITH-CORROBORATION"):
        for country in ("us", "uk", "ca"):
            assert resolve_issue_repo(verdict, country) is None


# --- Properties --------------------------------------------------------------


@given(
    verdict=st.sampled_from(VERDICTS),
    country=st.sampled_from(sorted(COUNTRY_MODEL_REPOS)),
    dataset=st.none() | any_dataset,
)
def test_routing_returns_none_or_one_policyengine_repo(verdict, country, dataset):
    result = resolve_issue_repo(verdict, country, dataset)
    if verdict in ("INVESTIGATE", "structural"):
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


@given(dataset=st.none() | any_dataset)
def test_uk_investigate_lands_in_microcosm_or_uk_data(dataset):
    assert resolve_issue_repo("INVESTIGATE", "uk", dataset) in {MICROCOSM, UK_DATA}


@given(name=known_dataset, path=repo_path, rev=revision)
def test_uk_investigate_routes_a_uri_like_its_dataset_name(name, path, rev):
    uri = f"hf://{path}/{name}.h5@{rev}"
    assert resolve_issue_repo("INVESTIGATE", "uk", uri) == resolve_issue_repo(
        "INVESTIGATE", "uk", name
    )


# --- Differential: report-logger's bash against the reference ---------------


@pytest.mark.parametrize("country", ["us", "uk"])
@pytest.mark.parametrize(
    "dataset",
    [
        "",
        UK_DEFAULT_URI,
        ENHANCED_FRS_URI,
        ENHANCED_FRS_BRANCH_URI,
        *UK_MICROCOSM_DATASETS,
        *UK_DATA_FILES,
    ],
)
def test_report_logger_bash_matches_reference(country, dataset):
    assert run_routing_snippet(country, dataset) == resolve_issue_repo(
        "INVESTIGATE", country, dataset
    )


@settings(max_examples=150, deadline=None)
@given(country=st.sampled_from(["us", "uk"]), dataset=any_dataset)
def test_report_logger_bash_matches_reference_for_any_dataset(country, dataset):
    assert run_routing_snippet(country, dataset) == resolve_issue_repo(
        "INVESTIGATE", country, dataset
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "report-logger's bash sends ca to policyengine-ca-data while its prose and "
        "this reference say policyengine-canada-data; neither repo exists, and "
        "policyengine.py's bundle has no Canada data"
    ),
)
def test_report_logger_bash_routes_ca_like_the_reference():
    assert run_routing_snippet("ca", "") == resolve_issue_repo("INVESTIGATE", "ca")
