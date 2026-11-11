"""The dashboard manifest must not depend on incidental orderings.

``scripts/build_manifest.py`` once listed workflow edges in set-iteration
order, which follows the per-process ``PYTHONHASHSEED``, so every rebuild
reordered ``edges`` and rewrote hundreds of manifest lines with no content
change. These tests hold rebuilds byte-identical apart from ``generated_at``
and keep the repo lists independent of the inventory file's order.
"""

from __future__ import annotations

import json
import os
import re
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
    SOURCE_KIND_ORDER,
    edge_sort_key,
    extract_references,
)

BUILDER = ROOT / "scripts" / "build_manifest.py"
# PYTHONHASHSEED=0 turns hash randomization off; 1 and 2 are two fixed seeds.
# Before the fix, each of these seeds wrote the edges in a different order.
HASH_SEEDS = ("0", "1", "2")
GENERATED_AT_LINE = re.compile(r'^  "generated_at": "[^"\n]*",\n', re.MULTILINE)


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


def without_generated_at(text: str) -> str:
    stripped, count = GENERATED_AT_LINE.subn("", text)
    assert count == 1, "expected exactly one generated_at line"
    return stripped


def test_manifest_is_identical_across_hash_seeds(manifests):
    baseline_seed, *other_seeds = HASH_SEEDS
    baseline = without_generated_at(manifests[baseline_seed])
    for seed in other_seeds:
        text = without_generated_at(manifests[seed])
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
