"""The dashboard manifest must be complete and must not depend on accidents.

``scripts/build_manifest.py`` once listed workflow edges in set-iteration
order, which follows the per-process ``PYTHONHASHSEED``, so every rebuild
reordered ``edges`` and rewrote hundreds of manifest lines with no content
change. These tests hold rebuilds byte-identical apart from ``generated_at``,
keep the repo lists independent of the inventory file's order, keep overlap
scores independent of how the Python version or the platform rounds floats,
and check that the builder stops, without writing, when it lacks PyYAML.
"""

from __future__ import annotations

import builtins
import dataclasses
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import build_manifest  # noqa: E402
from scripts.build_manifest import (  # noqa: E402
    GENERATED_AT_LINE,
    SOURCE_KIND_ORDER,
    Artifact,
    edge_sort_key,
    extract_references,
)

BUILDER = ROOT / "scripts" / "build_manifest.py"
# PYTHONHASHSEED=0 turns hash randomization off; 1 and 2 are two fixed seeds.
# Before the fix, each of these seeds wrote the edges in a different order.
HASH_SEEDS = ("0", "1", "2")


def run_builder(output: Path, hash_seed: str) -> str:
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return output.read_text()


@pytest.fixture(scope="module")
def manifests(tmp_path_factory) -> dict[str, str]:
    """Manifest text from one builder subprocess per hash seed."""
    out_dir = tmp_path_factory.mktemp("manifests")
    return {
        seed: run_builder(out_dir / f"manifest-{seed}.json", seed)
        for seed in HASH_SEEDS
    }


def comparable(text: str) -> str:
    assert len(GENERATED_AT_LINE.findall(text)) == 1, "expected one generated_at line"
    return build_manifest.without_generated_at(text)


def test_manifest_is_identical_across_hash_seeds(manifests):
    baseline_seed, *other_seeds = HASH_SEEDS
    baseline = comparable(manifests[baseline_seed])
    for seed in other_seeds:
        text = comparable(manifests[seed])
        if text != baseline:
            before, after = json.loads(baseline), json.loads(text)
            sections = [key for key in before if before[key] != after.get(key)]
            pytest.fail(
                f"PYTHONHASHSEED={seed} and PYTHONHASHSEED={baseline_seed} wrote "
                f"different manifests; sections that differ: "
                f"{sections or 'none (key order or formatting)'}"
            )


def test_edges_are_unique_and_in_canonical_order(manifests):
    edges = json.loads(manifests[HASH_SEEDS[0]])["edges"]
    assert edges, "the repo should yield workflow edges"
    keys = [edge_sort_key(edge) for edge in edges]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys), "duplicate edges"


def test_commands_lead_the_edge_list(manifests):
    # dashboard/src/components/Drawer.tsx shows only the first 20 incoming
    # edges ("Called by"), so edge order decides which callers it shows.
    # User-facing commands come first, then agents, then bundles.
    assert SOURCE_KIND_ORDER == ("command", "agent", "bundle")
    edges = json.loads(manifests[HASH_SEEDS[0]])["edges"]
    ranks = [SOURCE_KIND_ORDER.index(edge["source_kind"]) for edge in edges]
    assert ranks == sorted(ranks)


SLUG = st.one_of(
    # Hyphenated slugs of 6+ characters also match as bare mentions.
    st.from_regex(r"[a-z][a-z0-9]{2,6}-[a-z0-9]{2,6}", fullmatch=True),
    st.from_regex(r"[a-z][a-z0-9\-]{1,12}", fullmatch=True),
)
MENTION_TEMPLATES = (
    "{}",
    "use the {} agent",
    "@{}",
    "`/{}`",
    'subagent_type="{}"',
    'Skill(skill="{}")',
)


@st.composite
def reference_cases(draw):
    """Text that mentions known ids, plus the ids in two different orders."""
    ids = {
        kind: draw(st.lists(SLUG, unique=True, max_size=6))
        for kind in ("agent", "skill", "command")
    }
    every_id = sorted({slug for slugs in ids.values() for slug in slugs})
    mentions = (
        draw(
            st.lists(
                st.tuples(
                    st.sampled_from(MENTION_TEMPLATES), st.sampled_from(every_id)
                ),
                max_size=12,
            )
        )
        if every_id
        else []
    )
    text = "\n".join(template.format(slug) for template, slug in mentions)
    reordered = {kind: draw(st.permutations(slugs)) for kind, slugs in ids.items()}
    return text, ids, reordered


@settings(deadline=None)
@given(reference_cases())
def test_extract_references_ignores_known_id_order(case):
    # The builder passes sets, whose order follows the hash seed; lists in
    # every order stand in for every order a set could iterate in.
    text, ids, reordered = case
    first = extract_references(text, ids)
    second = extract_references(text, reordered)
    assert list(first.items()) == list(second.items())


INVENTORY = build_manifest.load_org_repos()


@settings(deadline=None, max_examples=50)
@given(st.permutations(range(len(INVENTORY))))
def test_known_repos_ignore_inventory_order(order):
    # A refresh of scripts/policyengine_repos.json can list the same repos in
    # a new order; target_repos, known_repos and repo_coverage follow
    # build_known_repos, so its result has to stay the same. Hypothesis
    # permutes indices, so a failure prints a list of numbers rather than
    # the whole inventory.
    assert len(INVENTORY) > 1
    inventory = [INVENTORY[i] for i in order]
    with patch.object(build_manifest, "load_org_repos", return_value=inventory):
        assert build_manifest.build_known_repos() == build_manifest.KNOWN_REPO_KINDS


# ---------------------------------------------------------------------------
# The builder needs PyYAML, and the dashboard needs what PyYAML gives it.
# ---------------------------------------------------------------------------

# Runs the builder as a script in an interpreter where `import yaml` fails,
# as it does under macOS's /usr/bin/python3.
WITHOUT_PYYAML = """\
import runpy, sys
sys.modules["yaml"] = None
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def test_builder_stops_without_pyyaml_and_writes_nothing(tmp_path):
    output = tmp_path / "manifest.json"
    output.write_text("the committed manifest")
    result = subprocess.run(
        [sys.executable, "-c", WITHOUT_PYYAML, str(BUILDER), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "needs PyYAML" in result.stderr
    assert "uv run python scripts/build_manifest.py" in result.stderr
    assert output.read_text() == "the committed manifest"


def test_frontmatter_keeps_yaml_types():
    # The Analyses page formats these numbers with toFixed and reads the
    # nested jurisdiction; a parser that returned strings broke both.
    text = (
        "---\n"
        "policy_id: 97759\n"
        "our_gini_pct_change_relative: -0.25\n"
        "jurisdiction:\n"
        "  country: us\n"
        "  state: null\n"
        "---\n"
        "body\n"
    )
    meta, body = build_manifest.parse_frontmatter(text)
    assert meta == {
        "policy_id": 97759,
        "our_gini_pct_change_relative": -0.25,
        "jurisdiction": {"country": "us", "state": None},
    }
    assert body == "body\n"


@pytest.mark.parametrize(
    ("frontmatter", "problem"),
    [
        ("name: [unclosed", "isn't valid YAML"),
        ("- a list\n- not a mapping", "must be a YAML mapping, not list"),
    ],
)
def test_bad_frontmatter_stops_the_build_and_names_the_file(frontmatter, problem):
    text = f"---\n{frontmatter}\n---\nbody\n"
    with pytest.raises(build_manifest.FrontmatterError, match=problem) as raised:
        build_manifest.parse_frontmatter(text, "skills/example/SKILL.md")
    assert str(raised.value).startswith("skills/example/SKILL.md: ")


NUMERIC_ANALYSIS_FIELDS = (
    "cost_billion_year1",
    "cost_billion_10yr_actual",
    "gini_pct_change",
    "top1_pp_change",
    "child_poverty_pct_change",
)


def test_analyses_reach_the_dashboard_as_numbers(manifests):
    # dashboard/src/pages/Analyses.tsx calls toFixed on these fields, which
    # throws on a string, and filters on jurisdiction.country.
    analyses = json.loads(manifests[HASH_SEEDS[0]])["analyses"]
    assert analyses, "the repo should have archived analyses"
    for entry in analyses:
        for name in NUMERIC_ANALYSIS_FIELDS:
            value = entry[name]
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            assert value is None or is_number, (entry["file"], name, value)
        assert entry["jurisdiction"]["country"], entry["file"]


# ---------------------------------------------------------------------------
# --check, which CI runs on Linux.
# ---------------------------------------------------------------------------


def test_check_passes_when_only_generated_at_differs(manifests, tmp_path):
    on_disk = tmp_path / "manifest.json"
    on_disk.write_text(
        GENERATED_AT_LINE.sub(
            '  "generated_at": "2000-01-01T00:00:00Z",\n', manifests[HASH_SEEDS[0]]
        )
    )
    before = on_disk.read_text()
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--check", "--output", str(on_disk)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert on_disk.read_text() == before, "--check must not write"


def test_check_fails_on_a_stale_manifest(manifests, tmp_path, capsys):
    fresh = manifests[HASH_SEEDS[0]]
    stale = json.loads(fresh)
    stale["overlaps"][0]["score"] += 0.01
    on_disk = tmp_path / "manifest.json"
    on_disk.write_text(build_manifest.render_manifest(stale))
    before = on_disk.read_text()
    assert build_manifest.check_manifest(on_disk, fresh) == 1
    err = capsys.readouterr().err
    assert "Sections that differ: overlaps" in err
    assert '"score"' in err, "the diff should show the line that changed"
    assert "uv run python scripts/build_manifest.py" in err
    assert on_disk.read_text() == before, "--check must not write"


def test_check_fails_when_the_manifest_is_missing(manifests, tmp_path, capsys):
    missing = tmp_path / "manifest.json"
    assert build_manifest.check_manifest(missing, manifests[HASH_SEEDS[0]]) == 1
    assert "doesn't exist" in capsys.readouterr().err
    assert not missing.exists(), "--check must not write"


# ---------------------------------------------------------------------------
# Overlaps.
# ---------------------------------------------------------------------------


def test_overlaps_follow_artifact_order(manifests):
    # Artifact order keeps a one-skill edit from re-sorting the whole list;
    # dashboard/src/data.ts sorts pairs by score for the views that rank them.
    manifest = json.loads(manifests[HASH_SEEDS[0]])
    position = {(a["kind"], a["id"]): i for i, a in enumerate(manifest["artifacts"])}
    keys = [
        (position[(p["a"]["kind"], p["a"]["id"])], position[(p["b"]["kind"], p["b"]["id"])])
        for p in manifest["overlaps"]
    ]
    assert keys, "the repo should yield overlap pairs"
    assert all(a < b for a, b in keys), "a comes before b"
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys), "duplicate pairs"


def sample_artifacts() -> list[Artifact]:
    """A few small artifacts that share words, so several pairs overlap."""
    texts = {
        "budget-scoring": "score budget reforms with microsimulation budget windows",
        "budget-windows": "budget windows for reforms and microsimulation scoring",
        "poverty-impacts": "poverty impacts of reforms with microsimulation",
        "frontend-review": "review frontend pull requests for accessibility",
    }
    return [
        Artifact(
            id=slug,
            kind="skill",
            name=slug,
            description=text,
            body=text,
            category="test",
            path=f"skills/{slug}/SKILL.md",
        )
        for slug, text in texts.items()
    ]


def one_percent_high_sum(iterable, start=0):
    total = builtins.sum(iterable, start)
    return total * 1.01 if isinstance(total, float) else total


def test_overlaps_never_use_builtin_sum(monkeypatch):
    # The built-in sum() rounds floats differently on Python 3.11 and on
    # 3.12 and later, so scores summed with it, and the shared_terms order
    # they decide, changed with the Python version. compute_overlaps sums
    # with math.fsum, which rounds exactly on every version. A sum() that
    # gives other answers makes this test fail on any version if sum()
    # comes back, where a manifest comparison would catch it only on 3.11.
    artifacts = sample_artifacts()
    expected = build_manifest.compute_overlaps(artifacts)
    assert expected, "the sample artifacts should overlap"
    monkeypatch.setattr(build_manifest, "sum", one_percent_high_sum, raising=False)
    assert build_manifest.compute_overlaps(artifacts) == expected, (
        "compute_overlaps summed floats with the built-in sum(); use math.fsum"
    )


def test_overlaps_never_use_the_c_librarys_log(monkeypatch):
    # math.log rounds as the platform's C library does, so IDF from it
    # could differ between macOS and Linux. compute_overlaps takes ln from
    # the decimal module instead (smoothed_idf).
    artifacts = sample_artifacts()
    expected = build_manifest.compute_overlaps(artifacts)
    real_log = math.log
    monkeypatch.setattr(math, "log", lambda *args: real_log(*args) * 1.01)
    assert build_manifest.compute_overlaps(artifacts) == expected, (
        "compute_overlaps took IDF from math.log; use smoothed_idf"
    )


# Few words, so pairs overlap often and many terms tie in shared_terms.
WORDS = ("budget", "reform", "poverty", "scoring", "windows", "microsim", "frontend")


@st.composite
def overlap_cases(draw):
    """Artifacts, an order to list them in, and their bodies' words reordered."""
    word_lists = draw(
        st.lists(st.lists(st.sampled_from(WORDS), min_size=1, max_size=10), min_size=2, max_size=6)
    )
    artifacts = [
        Artifact(
            id=f"artifact-{i}",
            kind=draw(st.sampled_from(("skill", "agent", "command"))),
            name="",
            description="",
            body=" ".join(words),
            category="test",
            path=f"artifact-{i}.md",
        )
        for i, words in enumerate(word_lists)
    ]
    order = draw(st.permutations(range(len(artifacts))))
    reworded = [" ".join(draw(st.permutations(words))) for words in word_lists]
    return artifacts, order, reworded


def by_pair(overlaps: list[dict]) -> dict:
    return {
        frozenset({(p["a"]["kind"], p["a"]["id"]), (p["b"]["kind"], p["b"]["id"])}): (
            p["score"],
            p["shared_terms"],
        )
        for p in overlaps
    }


@settings(deadline=None)
@given(overlap_cases())
def test_overlaps_ignore_artifact_order_and_word_order(case):
    # A pair's score and shared_terms depend on the two texts' words, not on
    # where each word first appears or on which artifact comes first: fsum
    # rounds exactly in any order, and shared_terms break ties by term.
    artifacts, order, reworded = case
    expected = build_manifest.compute_overlaps(artifacts)
    listed_otherwise = build_manifest.compute_overlaps([artifacts[i] for i in order])
    assert by_pair(listed_otherwise) == by_pair(expected)
    words_moved = build_manifest.compute_overlaps(
        [
            dataclasses.replace(a, body=body)
            for a, body in zip(artifacts, reworded, strict=True)
        ]
    )
    assert words_moved == expected
