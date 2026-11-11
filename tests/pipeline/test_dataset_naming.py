"""Regression tests for the dataset behind an API economy run.

policyengine-api's annual economy route takes `region`, `time_period`,
`version`, `target`, `spm` and, for the UK, `breakdown`. The budget-window
route takes `region`, `start_year`, `window_size`, `version`, `spm` and
`target`. `StrictQueryParameters` forbids every other field
(`policyengine_api/query_parameters.py` at fe2d09da0), so a request that sends
`dataset` gets HTTP 400 "dataset: Extra inputs are not permitted". The routes
build every request with `dataset="default"`, and the API runs each reform on
the one dataset `/{country}/metadata` lists under `economy_options.datasets`.

An annual result's `policyengine_bundle` names what the simulation loaded:
its `dataset` holds the file's hf:// URI or `default`, and its `data_version`
can come back empty. A budget-window result carries no bundle.
microsim-runner's dataset check, `run_dataset`, turns the URI into the
dataset's name, takes a missing name from the metadata's default entry, and
takes a missing data version only from the URI's `@revision`. The local path
runs the same check on the URI policyengine.py resolves. These tests exec both
blocks straight from microsim-runner.md, so the agent's code and the tests
can't drift apart.

Invariants, for any bundle whose dataset holds an hf:// URI, a bare dataset
name, `default` or nothing, and any metadata list with one default entry:
- the name comes from the bundle's file or bare name, less any path,
  `@revision` and `.h5` suffix, or from the default entry when the bundle names
  no dataset;
- the data version comes from the bundle, or else from the text after the
  URI's last `@`, and never from the metadata;
- `dataset_matches_default` reads false when the name differs from the default
  entry's, null when the name matches but either side lacks a data version, and
  otherwise whether the two data versions agree.
For any non-empty dataset string other than `default`, the name agrees with
policyengine.py's `dataset_logical_name`. And no agent, skill or doc sends
`dataset` to an economy route in a query string, or in a fenced block that
calls one; the scan doesn't read prose.

Set PE_SKILLS_LIVE_API=1 to also check the snapshots below against
api.policyengine.org.
"""
from __future__ import annotations

import json
import os
import re
import sys
import types
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

REPO_ROOT = Path(__file__).resolve().parents[2]
MICROSIM_RUNNER = REPO_ROOT / "targets" / "claude" / "agents" / "microsim-runner.md"
API_DOC_DIRS = ("skills", "targets", "docs")
API_DOC_FILES = ("README.md",)
PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)

# `economy_options.datasets` from api.policyengine.org: the US list on
# 2026-11-08 and the UK list on 2026-11-11.
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
            "@microcosm-uk-2024-25-national-20261107T020434Z-eeb6093e"
        ),
        "data_version": "microcosm-uk-2024-25-national-20261107T020434Z-eeb6093e",
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

# What policyengine.py's `resolve_managed_dataset_reference(country, dataset)`
# gives for each case below: the UK default from the live metadata, and the
# named files built from policyengine.py 6.16.0's bundle manifest.
LOCAL_URIS = {
    ("us", None): US_METADATA_DATASETS[0]["dataset_uri"],
    ("us", "populace_us_2024_acs_local"): (
        "hf://policyengine/populace-us/populace_us_2024_acs_local.h5"
        "@populace-us-2024-buildo-acs-local-766b7c7-20261017T030317Z"
    ),
    ("uk", None): UK_METADATA_DATASETS[0]["dataset_uri"],
    ("uk", "enhanced_frs_2024_25"): (
        "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2024_25.h5@1.58.1"
    ),
}

ECONOMY_QUERY_DATASET = re.compile(r"(?:[?&]|%26)dataset=")
DATASET_KEY_OR_KWARG = re.compile(
    r"""["']?\bdataset["']?\s*:|["']dataset["']\s*\]\s*=(?!=)|\bdataset\s*="""
)
FENCED_BLOCK = re.compile(
    r"^[ \t]*(```|~~~)[^\n]*\n(.*?)^[ \t]*\1", re.MULTILINE | re.DOTALL
)


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


def local_path_section() -> str:
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    return text.split("## Process — Local path", 1)[1].split("\n## ", 1)[0]


@lru_cache(maxsize=1)
def local_record_block() -> str:
    blocks = [
        block
        for block in PYTHON_BLOCK.findall(local_path_section())
        if "resolve_managed_dataset_reference(" in block
    ]
    assert len(blocks) == 1, f"expected one local recording block, found {len(blocks)}"
    return blocks[0]


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

    A query string with `?dataset=`, `&dataset=` or `%26dataset=` counts
    anywhere. A `dataset:` key, quoted or not, a `["dataset"] =` assignment or
    a `dataset=` keyword counts inside a fenced block that calls an `/economy/`
    route, as a requests `params` dict or a `URLSearchParams` object would carry
    it.
    """
    hits = [line for line in text.splitlines() if ECONOMY_QUERY_DATASET.search(line)]
    for match in FENCED_BLOCK.finditer(text):
        block = match.group(2)
        if "/economy/" in block:
            hits.extend(line for line in block.splitlines() if DATASET_KEY_OR_KWARG.search(line))
    return hits


def api_docs() -> list[Path]:
    files = [
        path
        for dirname in API_DOC_DIRS
        for path in sorted((REPO_ROOT / dirname).rglob("*.md"))
        if path.is_file()
    ]
    return files + [REPO_ROOT / name for name in API_DOC_FILES if (REPO_ROOT / name).is_file()]


def expected_match(check: dict, datasets: list[dict]):
    default = next(entry for entry in datasets if entry.get("default"))
    if check["dataset"] != default["name"]:
        return False
    if check["data_version"] and default.get("data_version"):
        return check["data_version"] == default["data_version"]
    return None


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
        'requests.get("https://api.policyengine.org/us/economy/1/over/2?region=us%26dataset=cps")',
        '```python\nrequests.get(f"{base}/us/economy/{p}/over/2", params={\n    "dataset": "populace_us_2024",\n})\n```',
        '  ```python\n  url = f"{base}/us/economy/{p}/over/2"\n  requests.get(url, params=dict(region="us", dataset=name))\n  ```',
        '```python\nparams = {"region": "us"}\nparams["dataset"] = name\nrequests.get(f"{base}/us/economy/{p}/over/2", params=params)\n```',
        '~~~python\nrequests.get(f"{base}/us/economy/{p}/over/2", params={"dataset": name})\n~~~',
        '```ts\nfetch(`${BASE}/us/economy/${id}/over/2?` + new URLSearchParams({ region: "us", dataset: name }));\n```',
        "```\nGET /{country}/economy/{policy_id}/over/{baseline_id}/budget-window\n    dataset: {dataset}\n```",
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
        '```python\nif check["dataset"] == default["name"]:  # /us/economy/1/over/2\n    pass\n```',
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
def test_bundle_without_a_release_names_the_default_and_leaves_the_match_open(country, bundle):
    entry = METADATA_DATASETS[country][0]
    assert run_dataset(bundle, METADATA_DATASETS[country]) == {
        "dataset": entry["name"],
        "data_version": None,
        "dataset_matches_default": None,
    }


@pytest.mark.parametrize(
    ("data_version", "matches"),
    [("populace-us-2024-spm-20260915", True), ("populace-us-2024-rev2", False)],
)
def test_bundle_reading_default_keeps_its_own_release(data_version, matches):
    bundle = {"dataset": "default", "data_version": data_version}
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": data_version,
        "dataset_matches_default": matches,
    }


def test_default_uri_without_data_version_reads_the_uri_revision():
    bundle = {"dataset": US_METADATA_DATASETS[0]["dataset_uri"], "data_version": None}
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": "populace-us-2024-spm-20260915",
        "dataset_matches_default": True,
    }


def test_unpinned_default_uri_leaves_the_release_unknown():
    bundle = {"dataset": "hf://policyengine/populace-us/populace_us_2024.h5", "data_version": None}
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024",
        "data_version": None,
        "dataset_matches_default": None,
    }


@pytest.mark.parametrize(
    ("bundle", "data_version"),
    [(US_RESULT_BUNDLE, "populace-us-2024-spm-20260915"), (None, None)],
)
def test_metadata_default_without_a_release_never_raises(bundle, data_version):
    # policyengine-api's metadata carries `data_version` and `dataset_uri` only
    # when its bundle records them (`policyengine_api/constants.py` at fe2d09da0).
    datasets = [{"name": "populace_us_2024", "label": "Microcosm", "default": True}]
    assert run_dataset(bundle, datasets) == {
        "dataset": "populace_us_2024",
        "data_version": data_version,
        "dataset_matches_default": None,
    }


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


@pytest.mark.parametrize(
    ("uri", "name", "data_version"),
    [
        ("hf://o/r/a@b.h5@rev", "a@b", "rev"),
        ("hf://o/r/x.h5@a@b", pinned_logical_name("hf://o/r/x.h5@a@b"), "b"),
    ],
)
def test_revision_is_the_text_after_the_last_at(uri, name, data_version):
    check = run_dataset({"dataset": uri, "data_version": None}, US_METADATA_DATASETS)
    assert (check["dataset"], check["data_version"]) == (name, data_version)


def test_other_dataset_at_the_default_release_does_not_match():
    bundle = {
        "dataset": "hf://policyengine/populace-us/populace_us_2024_acs_local.h5@populace-us-2024-spm-20260915",
        "data_version": "populace-us-2024-spm-20260915",
    }
    assert run_dataset(bundle, US_METADATA_DATASETS)["dataset_matches_default"] is False


def test_other_dataset_never_borrows_the_default_release():
    bundle = {"dataset": "populace_us_2024_acs_local", "data_version": None}
    assert run_dataset(bundle, US_METADATA_DATASETS) == {
        "dataset": "populace_us_2024_acs_local",
        "data_version": None,
        "dataset_matches_default": False,
    }


# --- The local path ---------------------------------------------------------


class FakeMetadataAPI:
    """Stands in for `requests` on the local path: GET /{country}/metadata."""

    def __init__(self, country: str):
        self.country = country
        self.urls: list[str] = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        body = {
            "result": {
                "version": "x",
                "economy_options": {"datasets": METADATA_DATASETS[self.country]},
            }
        }
        return types.SimpleNamespace(json=lambda: body)


def run_local_record(monkeypatch, country, dataset):
    """Exec the runner's local recording block with policyengine and the API faked."""
    resolved: list[tuple] = []

    def resolve_managed_dataset_reference(country_id, name=None):
        resolved.append((country_id, name))
        return LOCAL_URIS[(country_id, name)]

    manifest = types.ModuleType("policyengine.provenance.manifest")
    manifest.resolve_managed_dataset_reference = resolve_managed_dataset_reference
    monkeypatch.setitem(sys.modules, "policyengine", types.ModuleType("policyengine"))
    monkeypatch.setitem(sys.modules, "policyengine.provenance", types.ModuleType("policyengine.provenance"))
    monkeypatch.setitem(sys.modules, "policyengine.provenance.manifest", manifest)
    api = FakeMetadataAPI(country)
    namespace = {
        "country": country,
        "dataset": dataset,
        "requests": api,
        "run_dataset": runner_run_dataset(),
    }
    exec(compile(local_record_block(), str(MICROSIM_RUNNER), "exec"), namespace)  # noqa: S102
    return namespace["check"], resolved, api.urls


@pytest.mark.parametrize(
    ("country", "dataset", "expected"),
    [
        ("us", None, ("populace_us_2024", "populace-us-2024-spm-20260915", True)),
        (
            "us",
            "populace_us_2024_acs_local",
            (
                "populace_us_2024_acs_local",
                "populace-us-2024-buildo-acs-local-766b7c7-20261017T030317Z",
                False,
            ),
        ),
        (
            "uk",
            None,
            (
                "microcosm_uk_2024_25",
                "microcosm-uk-2024-25-national-20261107T020434Z-eeb6093e",
                True,
            ),
        ),
        ("uk", "enhanced_frs_2024_25", ("enhanced_frs_2024_25", "1.58.1", False)),
    ],
)
def test_local_path_records_the_dataset_it_loaded(monkeypatch, country, dataset, expected):
    check, resolved, urls = run_local_record(monkeypatch, country, dataset)
    assert resolved == [(country, dataset)]
    assert urls == [f"https://api.policyengine.org/{country}/metadata"]
    assert (check["dataset"], check["data_version"], check["dataset_matches_default"]) == expected


def test_local_path_loads_the_dataset_it_was_asked_for():
    calls = [
        args
        for block in PYTHON_BLOCK.findall(local_path_section())
        for args in re.findall(r"ensure_datasets\(([^)]*)\)", block)
    ]
    assert calls, "the local path no longer calls ensure_datasets"
    for args in calls:
        assert re.search(r"\bdatasets=\[dataset\]", args), f"ensure_datasets ignores the caller's dataset: {args!r}"


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
    """A metadata list shaped like the API's: one default, which may lack its release."""
    name, version = draw(stem), draw(revision)
    default = {"name": name, "default": True}
    if draw(st.booleans()):
        default["dataset_uri"] = f"hf://policyengine/{draw(segment)}/{name}.h5@{version}"
        default["data_version"] = version
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


@settings(deadline=None)
@given(bundle=bundles, datasets=metadata_lists())
def test_check_returns_a_dataset_name(bundle, datasets):
    name = run_dataset(bundle, datasets)["dataset"]
    assert name and name != "default"
    assert not re.search(r"[/@]|\.h5$", name)


@settings(deadline=None)
@given(datasets=metadata_lists(), dataset=st.one_of(empty, st.just("default")), version=empty)
def test_bundle_without_values_names_the_default_and_no_release(datasets, dataset, version):
    default = next(entry for entry in datasets if entry["default"])
    assert run_dataset({"dataset": dataset, "data_version": version}, datasets) == {
        "dataset": default["name"],
        "data_version": None,
        "dataset_matches_default": None,
    }


@settings(deadline=None)
@given(datasets=metadata_lists(), dataset=st.one_of(hf_uris(), stem), version=revision)
def test_bundle_values_win_over_metadata(datasets, dataset, version):
    check = run_dataset({"dataset": dataset, "data_version": version}, datasets)
    assert check["dataset"] == logical_name(dataset)
    assert check["data_version"] == version


@settings(deadline=None)
@given(datasets=metadata_lists(), uri=hf_uris(pinned=True), version=empty)
@example(datasets=US_METADATA_DATASETS, uri="hf://o/r/x.h5@a@b", version=None)
def test_uri_revision_fills_a_missing_data_version(datasets, uri, version):
    check = run_dataset({"dataset": uri, "data_version": version}, datasets)
    assert check["data_version"] == uri.rsplit("@", 1)[1]


@settings(deadline=None)
@given(bundle=bundles, datasets=metadata_lists())
def test_data_version_never_comes_from_the_metadata(bundle, datasets):
    given_dataset = (bundle or {}).get("dataset") or ""
    if not (bundle or {}).get("data_version") and "@" not in given_dataset:
        assert run_dataset(bundle, datasets)["data_version"] is None


@settings(deadline=None)
@given(bundle=bundles, datasets=metadata_lists())
def test_match_is_false_null_or_the_release_comparison(bundle, datasets):
    check = run_dataset(bundle, datasets)
    assert check["dataset_matches_default"] is expected_match(check, datasets)


any_dataset = st.text(min_size=1).filter(lambda s: s != "default" and "\x00" not in s)


@settings(deadline=None)
@given(dataset=any_dataset, datasets=metadata_lists())
@example(dataset="hf://policyengine/populace-us/populace_us_2024.h5@v1.2.0", datasets=US_METADATA_DATASETS)
@example(dataset="name@release.1", datasets=US_METADATA_DATASETS)
@example(dataset="hf://o/r/a@b.h5@rev", datasets=US_METADATA_DATASETS)
@example(dataset="name@x@y", datasets=US_METADATA_DATASETS)
@example(
    dataset="hf://policyengine/populace-uk-private/microcosm_uk_2024_25_calibration.npz@rev",
    datasets=UK_METADATA_DATASETS,
)
def test_name_agrees_with_policyengine_dataset_logical_name(dataset, datasets):
    check = run_dataset({"dataset": dataset, "data_version": "v"}, datasets)
    assert check["dataset"] == logical_name(dataset)


@settings(deadline=None)
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


RELEASE_KEYS = ("dataset_uri", "data_version")


@live
@pytest.mark.parametrize("country", ["us", "uk"])
def test_live_metadata_matches_the_snapshot_apart_from_the_release(country):
    # Each certified build moves the release, so compare everything else and
    # check that each live release agrees with its URI.
    status, body = fetch(f"https://api.policyengine.org/{country}/metadata")
    assert status == 200
    datasets = body["result"]["economy_options"]["datasets"]

    def without_release(entries):
        return [{k: v for k, v in entry.items() if k not in RELEASE_KEYS} for entry in entries]

    assert without_release(datasets) == without_release(METADATA_DATASETS[country])
    for entry in datasets:
        if entry.get("data_version"):
            check = run_dataset({"dataset": entry["dataset_uri"]}, datasets)
            assert (check["dataset"], check["data_version"]) == (entry["name"], entry["data_version"])


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
