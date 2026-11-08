"""Regression tests for the dataset behind an API economy run.

policyengine-api's economy routes take `region`, `time_period` (or
`start_year` and `window_size` on the budget-window route), `version`,
`target`, `spm` and, for the UK, `breakdown`. `EconomyQuery` forbids every
other field (`policyengine_api/query_parameters.py` at fe2d09da0), so a
request that sends `dataset` gets HTTP 400 "dataset: Extra inputs are not
permitted". The routes build every request with `dataset="default"`, and the
API runs each reform on the one dataset `/{country}/metadata` lists under
`economy_options.datasets`.

An annual result's `policyengine_bundle` names what the simulation loaded:
its `dataset` holds the file's hf:// URI or `default`, and its `data_version`
can come back empty. A budget-window result carries no bundle.
microsim-runner's dataset check, `run_dataset`, turns the URI into the
dataset's name and takes whatever the bundle leaves out from the metadata's
default entry. These tests exec `run_dataset` straight from microsim-runner.md,
so the agent's code and the tests can't drift apart.

Invariants, for any bundle whose dataset is an hf:// URI, a bare dataset
name, `default` or empty:
- the check returns a dataset name: never `default`, a path, an `@revision`
  or an `.h5` suffix;
- an empty bundle, or one that reads `default` with no data version, gives the
  metadata default and matches it;
- the bundle's own dataset and data version win over the metadata, and a
  missing data version comes from the URI's `@revision` before the metadata;
- `dataset_matches_default` holds exactly when both values equal the default
  entry's.
For any string at all, the name agrees with policyengine.py's
`dataset_logical_name`. And no agent, skill or doc sends `dataset` to an
economy route.

Set PE_SKILLS_LIVE_API=1 to also check the snapshots below against
api.policyengine.org.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

REPO_ROOT = Path(__file__).resolve().parents[2]
MICROSIM_RUNNER = REPO_ROOT / "targets" / "claude" / "agents" / "microsim-runner.md"
API_DOC_DIRS = ("skills", "targets", "docs")

# `economy_options.datasets` from api.policyengine.org on 2026-11-08.
US_METADATA_DATASETS = [
    {
        "name": "populace_us_2024",
        "label": "Microcosm",
        "title": "Certified Microcosm dataset",
        "default": True,
        "dataset_uri": (
            "hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-spm-20260915"
        ),
        "data_version": "populace-us-2024-spm-20260915",
    }
]
UK_METADATA_DATASETS = [
    {
        "name": "microcosm_uk_2024_25",
        "label": "Microcosm",
        "title": "Certified Microcosm dataset",
        "default": True,
        "dataset_uri": (
            "hf://policyengine/populace-uk-private/microcosm_uk_2024_25.h5"
            "@microcosm-uk-2024-25-national-20261025T091414Z-a6299504"
        ),
        "data_version": "microcosm-uk-2024-25-national-20261025T091414Z-a6299504",
    }
]
METADATA_DATASETS = {"us": US_METADATA_DATASETS, "uk": UK_METADATA_DATASETS}

# `result.policyengine_bundle` from a live US annual run on 2026-11-08 (policy
# 97853 over 2, region us, 2026), less its `dataset_sha256` and `spm`.
US_RESULT_BUNDLE = {
    "model_version": "2.2.1",
    "policyengine_version": "6.16.0",
    "data_version": "populace-us-2024-spm-20260915",
    "dataset": (
        "hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-spm-20260915"
    ),
}

ECONOMY_QUERY_DATASET = re.compile(r"[?&]dataset=")
DATASET_KEY_OR_KWARG = re.compile(r"""["']dataset["']\s*:|\bdataset\s*=""")
FENCED_BLOCK = re.compile(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```", re.MULTILINE | re.DOTALL)


@lru_cache(maxsize=1)
def runner_run_dataset():
    """Exec the first python block under microsim-runner's dataset check heading."""
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    section = text.split("### Dataset check (REQUIRED)", 1)[1]
    block = section.split("```python\n", 1)[1].split("```", 1)[0]
    assert "def run_dataset(" in block, "microsim-runner's dataset check no longer defines run_dataset"
    namespace: dict = {}
    exec(compile(block, str(MICROSIM_RUNNER), "exec"), namespace)  # noqa: S102
    return namespace["run_dataset"]


def run_dataset(bundle, datasets):
    return runner_run_dataset()(bundle, datasets)


def pinned_logical_name(dataset: str) -> str:
    """policyengine.py 6.16.0's `dataset_logical_name` (provenance/manifest.py:1415)."""
    return Path(dataset.rsplit("@", 1)[0]).stem


@lru_cache(maxsize=1)
def installed_logical_name():
    try:
        from policyengine.provenance.manifest import dataset_logical_name
    except ImportError:
        return None
    return dataset_logical_name


def logical_name(dataset: str) -> str:
    """The installed policyengine's `dataset_logical_name`, or the pinned 6.16.0 body."""
    return (installed_logical_name() or pinned_logical_name)(dataset)


def economy_dataset_requests(text: str) -> list[str]:
    """Return lines that send `dataset` to an economy route.

    A query string with `?dataset=` or `&dataset=` counts anywhere. A
    `"dataset":` key or a `dataset=` keyword counts inside a fenced block that
    calls an `/economy/` route, as a requests `params` dict would carry it.
    """
    hits = [line for line in text.splitlines() if ECONOMY_QUERY_DATASET.search(line)]
    for match in FENCED_BLOCK.finditer(text):
        block = match.group(1)
        if "/economy/" in block:
            hits.extend(line for line in block.splitlines() if DATASET_KEY_OR_KWARG.search(line))
    return hits


def api_docs() -> list[Path]:
    return [
        path
        for dirname in API_DOC_DIRS
        for path in sorted((REPO_ROOT / dirname).rglob("*.md"))
        if path.is_file()
    ]


# --- The API takes no dataset parameter ------------------------------------


def test_no_agent_or_skill_sends_dataset_to_the_api():
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {line.strip()}"
        for path in api_docs()
        for line in economy_dataset_requests(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, "economy requests that send dataset:\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    "sample",
    [
        'curl "https://api.policyengine.org/us/economy/1/over/2?region=us&time_period=2026&dataset=cps"',
        "GET /{country}/economy/{policy_id}/over/{baseline_id}/budget-window\n    &dataset={dataset}",
        '```python\nrequests.get(f"{base}/us/economy/{p}/over/2", params={\n    "dataset": "populace_us_2024",\n})\n```',
        '  ```python\n  url = f"{base}/us/economy/{p}/over/2"\n  requests.get(url, params=dict(region="us", dataset=name))\n  ```',
    ],
)
def test_dataset_scan_catches(sample):
    assert economy_dataset_requests(sample), f"scan missed a dataset request: {sample!r}"


@pytest.mark.parametrize(
    "sample",
    [
        "```python\nbaseline = Simulation(dataset=data, tax_benefit_model_version=pe.us.model)\n```",
        '```json\n{"dataset": "populace_us_2024", "data_version": "populace-us-2024-spm-20260915"}\n```',
        '```python\nrequests.get(f"{base}/us/economy/{p}/over/2", params={"region": "us"})\n```',
        '```python\nour_run_dataset = check["dataset"]  # from /us/economy/1/over/2\n```',
        "The API answers HTTP 400 to `dataset`.",
    ],
)
def test_dataset_scan_allows(sample):
    assert not economy_dataset_requests(sample), f"scan flagged a non-request: {sample!r}"


def test_runner_names_the_snapshot_defaults():
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    for entry in (US_METADATA_DATASETS[0], UK_METADATA_DATASETS[0]):
        assert f"`{entry['name']}`" in text, f"microsim-runner doesn't name {entry['name']}"
    assert f"`{US_METADATA_DATASETS[0]['data_version']}`" in text


# --- The metadata snapshots -------------------------------------------------


@pytest.mark.parametrize("country", ["us", "uk"])
def test_metadata_lists_one_default_whose_uri_names_it(country):
    datasets = METADATA_DATASETS[country]
    defaults = [entry for entry in datasets if entry.get("default")]
    assert len(defaults) == 1
    entry = defaults[0]
    assert logical_name(entry["dataset_uri"]) == entry["name"]
    assert entry["dataset_uri"].rsplit("@", 1)[1] == entry["data_version"]


# --- run_dataset on the shapes the API returns ------------------------------


def test_live_bundle_gives_the_default_name_and_release():
    assert run_dataset(US_RESULT_BUNDLE, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": "populace-us-2024-spm-20260915",
        "dataset_matches_default": True,
    }


@pytest.mark.parametrize("country", ["us", "uk"])
@pytest.mark.parametrize(
    "bundle",
    [
        None,  # a budget-window result
        {},
        {"dataset": "default", "data_version": None},
        {"dataset": "default", "data_version": ""},
        {"dataset": None, "data_version": None},
        {"model_version": "2.2.1"},
    ],
)
def test_default_bundle_takes_both_values_from_metadata(country, bundle):
    entry = METADATA_DATASETS[country][0]
    assert run_dataset(bundle, METADATA_DATASETS[country]) == {
        "dataset": entry["name"],
        "data_version": entry["data_version"],
        "dataset_matches_default": True,
    }


def test_default_uri_without_data_version_reads_the_uri_revision():
    bundle = {"dataset": US_METADATA_DATASETS[0]["dataset_uri"], "data_version": None}
    assert run_dataset(bundle, US_METADATA_DATASETS)["data_version"] == (
        "populace-us-2024-spm-20260915"
    )


def test_bundle_from_another_release_does_not_match():
    bundle = {
        "dataset": "hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-rev2",
        "data_version": "populace-us-2024-rev2",
    }
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": "populace-us-2024-rev2",
        "dataset_matches_default": False,
    }


def test_uri_revision_names_the_release_when_data_version_is_missing():
    bundle = {
        "dataset": "hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-rev2",
        "data_version": None,
    }
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": "populace-us-2024-rev2",
        "dataset_matches_default": False,
    }


def test_dotted_revision_stays_out_of_the_name():
    bundle = {"dataset": "hf://policyengine/populace-us/populace_us_2024.h5@v1.2.0", "data_version": None}
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": "v1.2.0",
        "dataset_matches_default": False,
    }


def test_other_dataset_never_borrows_the_default_release():
    bundle = {"dataset": "populace_us_2024_acs_local", "data_version": None}
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024_acs_local",
        "data_version": None,
        "dataset_matches_default": False,
    }


# --- Properties -------------------------------------------------------------

segment = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20)
stem = segment.filter(lambda s: s != "default")
revision = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_.-", min_size=1, max_size=30)


@st.composite
def hf_uris(draw, pinned=None):
    uri = f"hf://{draw(segment)}/{draw(segment)}/{draw(stem)}.h5"
    keep_revision = draw(st.booleans()) if pinned is None else pinned
    return uri + f"@{draw(revision)}" if keep_revision else uri


@st.composite
def metadata_lists(draw):
    """A metadata list shaped like the API's: one default whose URI names it."""
    name, version = draw(stem), draw(revision)
    default = {
        "name": name,
        "default": True,
        "dataset_uri": f"hf://policyengine/{draw(segment)}/{name}.h5@{version}",
        "data_version": version,
    }
    other_names = draw(st.lists(stem.filter(lambda s: s != name), max_size=2, unique=True))
    others = [
        {"name": other, "default": False, "dataset_uri": f"hf://o/r/{other}.h5", "data_version": None}
        for other in other_names
    ]
    position = draw(st.integers(min_value=0, max_value=len(others)))
    return [*others[:position], default, *others[position:]]


empty = st.sampled_from([None, ""])
bundle_datasets = st.one_of(empty, st.just("default"), hf_uris(), stem)
bundles = st.one_of(
    st.none(),
    st.fixed_dictionaries({"dataset": bundle_datasets, "data_version": st.one_of(empty, revision)}),
)


@given(bundle=bundles, datasets=metadata_lists())
def test_check_returns_a_dataset_name(bundle, datasets):
    name = run_dataset(bundle, datasets)["dataset"]
    assert name and name != "default"
    assert not re.search(r"[/@]|\.h5$", name)


@given(datasets=metadata_lists(), dataset=st.one_of(empty, st.just("default")), version=empty)
def test_bundle_without_values_matches_the_default(datasets, dataset, version):
    default = next(entry for entry in datasets if entry["default"])
    assert run_dataset({"dataset": dataset, "data_version": version}, datasets) == {
        "dataset": default["name"],
        "data_version": default["data_version"],
        "dataset_matches_default": True,
    }


@given(datasets=metadata_lists(), dataset=st.one_of(hf_uris(), stem), version=revision)
def test_bundle_values_win_over_metadata(datasets, dataset, version):
    check = run_dataset({"dataset": dataset, "data_version": version}, datasets)
    assert check["dataset"] == logical_name(dataset)
    assert check["data_version"] == version


@given(datasets=metadata_lists(), uri=hf_uris(pinned=True), version=empty)
def test_uri_revision_fills_a_missing_data_version(datasets, uri, version):
    check = run_dataset({"dataset": uri, "data_version": version}, datasets)
    assert check["data_version"] == uri.rsplit("@", 1)[1]


@given(bundle=bundles, datasets=metadata_lists())
def test_matches_default_exactly_when_both_values_equal_it(bundle, datasets):
    default = next(entry for entry in datasets if entry["default"])
    check = run_dataset(bundle, datasets)
    assert check["dataset_matches_default"] == (
        check["dataset"] == default["name"] and check["data_version"] == default["data_version"]
    )


any_dataset = st.text(min_size=1).filter(lambda s: s != "default" and "\x00" not in s)


@given(dataset=any_dataset, datasets=metadata_lists())
@example(dataset="hf://policyengine/populace-us/populace_us_2024.h5@v1.2.0", datasets=US_METADATA_DATASETS)
@example(dataset="name@release.1", datasets=US_METADATA_DATASETS)
def test_name_agrees_with_policyengine_dataset_logical_name(dataset, datasets):
    check = run_dataset({"dataset": dataset, "data_version": "v"}, datasets)
    assert check["dataset"] == logical_name(dataset)


@given(dataset=any_dataset)
def test_pinned_formula_matches_installed_policyengine(dataset):
    installed = installed_logical_name()
    if installed is None:
        pytest.skip("policyengine isn't installed; the pinned 6.16.0 formula stands in")
    assert pinned_logical_name(dataset) == installed(dataset)


# --- Live API (opt-in) -------------------------------------------------------

live = pytest.mark.skipif(
    os.environ.get("PE_SKILLS_LIVE_API") != "1",
    reason="live API check; set PE_SKILLS_LIVE_API=1 to run",
)


def fetch(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


@live
@pytest.mark.parametrize("country", ["us", "uk"])
def test_live_metadata_matches_the_snapshot(country):
    status, body = fetch(f"https://api.policyengine.org/{country}/metadata")
    assert status == 200
    assert body["result"]["economy_options"]["datasets"] == METADATA_DATASETS[country]


@live
@pytest.mark.parametrize(
    "path",
    [
        "us/economy/2/over/2?region=us&time_period=2026&dataset=populace_us_2024",
        "us/economy/2/over/2/budget-window?region=us&start_year=2026&window_size=2&dataset=default",
        "uk/economy/1/over/1?region=uk&time_period=2026&dataset=microcosm_uk_2024_25",
    ],
)
def test_live_economy_routes_refuse_dataset(path):
    status, body = fetch(f"https://api.policyengine.org/{path}")
    assert status == 400
    assert body["message"] == "dataset: Extra inputs are not permitted"
