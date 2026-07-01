#!/usr/bin/env python3
"""Search the analyses archive as a knowledge base.

Used by prior-scores-finder to check whether the same (or a similar) reform
has already been analyzed, so we can seed Tier-0 anchors and offer
duplicate-run detection instead of doing a cold web search each time.

Usage:

    python3 scripts/analyses_kb.py search --country us --family ctc
    python3 scripts/analyses_kb.py search --country us --family salt --contains "cap"
    python3 scripts/analyses_kb.py similar --file analyses/2026-07-01-us-...md
    python3 scripts/analyses_kb.py duplicates                # detect near-duplicate runs

Programmatic:

    from scripts.analyses_kb import search_analyses, find_similar
    hits = search_analyses(country="us", parameter_families=["ctc"])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "dashboard" / "src" / "data" / "manifest.json"


def _load_analyses() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    return json.loads(MANIFEST_PATH.read_text()).get("analyses", [])


def search_analyses(
    *,
    country: str | None = None,
    state: str | None = None,
    parameter_families: list[str] | None = None,
    verdict: str | None = None,
    contains: str | None = None,
) -> list[dict]:
    """Return matching archived analyses ordered by date descending."""
    hits = []
    for a in _load_analyses():
        if country and a.get("jurisdiction", {}).get("country") != country:
            continue
        if state and a.get("jurisdiction", {}).get("state") != state:
            continue
        if verdict and a.get("verdict") != verdict:
            continue
        if parameter_families:
            tags = set(a.get("tags") or [])
            if not any(fam in tags for fam in parameter_families):
                continue
        if contains and contains.lower() not in (a.get("title") or "").lower():
            continue
        hits.append(a)
    hits.sort(key=lambda a: a.get("date") or "", reverse=True)
    return hits


def find_similar(target: dict, *, threshold: float = 0.5) -> list[tuple[dict, float]]:
    """Find archived analyses similar to a target reform.

    Similarity is a naive Jaccard over (country, state, tags).
    Returns (analysis, score) sorted by score descending.
    """
    target_country = (target.get("jurisdiction") or {}).get("country")
    target_state = (target.get("jurisdiction") or {}).get("state")
    target_tags = set(target.get("tags") or [])

    scored = []
    for a in _load_analyses():
        if a.get("file") == target.get("file"):
            continue
        j = a.get("jurisdiction") or {}
        c_score = 1.0 if j.get("country") == target_country else 0.0
        s_score = 1.0 if j.get("state") == target_state else 0.5
        a_tags = set(a.get("tags") or [])
        tag_score = (
            len(target_tags & a_tags) / len(target_tags | a_tags)
            if (target_tags | a_tags)
            else 0.0
        )
        score = 0.4 * c_score + 0.1 * s_score + 0.5 * tag_score
        if score >= threshold:
            scored.append((a, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def detect_duplicates(threshold: float = 0.8) -> list[tuple[dict, dict, float]]:
    """Detect near-duplicate archived runs (same reform scored more than once)."""
    analyses = _load_analyses()
    pairs = []
    for i, a in enumerate(analyses):
        for b in analyses[i + 1 :]:
            j_a = a.get("jurisdiction") or {}
            j_b = b.get("jurisdiction") or {}
            if j_a.get("country") != j_b.get("country"):
                continue
            tags_a = set(a.get("tags") or [])
            tags_b = set(b.get("tags") or [])
            if not (tags_a and tags_b):
                continue
            jaccard = len(tags_a & tags_b) / len(tags_a | tags_b)
            if jaccard >= threshold:
                pairs.append((a, b, jaccard))
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def _format_hit(a: dict) -> str:
    return (
        f"  {a.get('date') or '—':<12} {a.get('verdict') or '—':<28} "
        f"{a.get('title')}\n"
        f"    file={a.get('file')} tags={','.join(a.get('tags') or [])}"
    )


def _cli_search(args: argparse.Namespace) -> int:
    hits = search_analyses(
        country=args.country,
        state=args.state,
        parameter_families=args.family.split(",") if args.family else None,
        verdict=args.verdict,
        contains=args.contains,
    )
    if not hits:
        print("No matching analyses.", file=sys.stderr)
        return 1
    print(f"{len(hits)} matches:")
    for a in hits:
        print(_format_hit(a))
    return 0


def _cli_similar(args: argparse.Namespace) -> int:
    if not args.file:
        print("--file <path> required", file=sys.stderr)
        return 1
    target_file = Path(args.file).name
    analyses = _load_analyses()
    target = next((a for a in analyses if a.get("file") == target_file), None)
    if not target:
        print(f"No archived analysis with file={target_file}", file=sys.stderr)
        return 1
    scored = find_similar(target, threshold=args.threshold)
    if not scored:
        print("No similar analyses above threshold.")
        return 0
    print(f"Analyses similar to {target_file} (threshold={args.threshold}):")
    for a, score in scored:
        print(f"  score={score:.2f}")
        print(_format_hit(a))
    return 0


def _cli_duplicates(args: argparse.Namespace) -> int:
    pairs = detect_duplicates(threshold=args.threshold)
    if not pairs:
        print(f"No duplicate candidates above threshold={args.threshold}.")
        return 0
    for a, b, score in pairs:
        print(f"\njaccard={score:.2f}")
        print(_format_hit(a))
        print(_format_hit(b))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    s = subparsers.add_parser("search", help="search analyses")
    s.add_argument("--country")
    s.add_argument("--state")
    s.add_argument("--family", help="comma-separated tag filter")
    s.add_argument("--verdict")
    s.add_argument("--contains", help="substring match on title")
    s.set_defaults(func=_cli_search)

    sim = subparsers.add_parser("similar", help="find analyses similar to a file")
    sim.add_argument("--file", required=True)
    sim.add_argument("--threshold", type=float, default=0.5)
    sim.set_defaults(func=_cli_similar)

    dup = subparsers.add_parser("duplicates", help="detect near-duplicate runs")
    dup.add_argument("--threshold", type=float, default=0.8)
    dup.set_defaults(func=_cli_duplicates)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
