#!/usr/bin/env python3
"""Scorekeepers registry loader + CLI.

Used by prior-scores-finder to enumerate Tier 2 (official fiscal offices) and
Tier 3 (think-tanks) to consult for a given reform's jurisdiction and domain.

Usage:

    python3 scripts/scorekeepers.py list                            # all
    python3 scripts/scorekeepers.py list --country uk               # UK only
    python3 scripts/scorekeepers.py list --tier 2                   # official only
    python3 scripts/scorekeepers.py list --domain tax               # tax-scoring only
    python3 scripts/scorekeepers.py list --country us --tier 3      # US think-tanks

Programmatic:

    from scripts.scorekeepers import list_scorekeepers
    tier_2_us = list_scorekeepers(country="us", tier=2)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "presets" / "scorekeepers.yaml"


def _load_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []
    data = yaml.safe_load(REGISTRY_PATH.read_text()) or {}
    return data.get("scorekeepers") or []


def list_scorekeepers(
    *,
    country: str | None = None,
    tier: int | None = None,
    domain: str | None = None,
    include_global: bool = True,
) -> list[dict]:
    """Return scorekeepers matching the filters.

    A scorekeeper matches a country if `country` is in its `jurisdictions` list
    OR if `jurisdictions` contains "global" (and `include_global` is True).
    """
    out = []
    for sk in _load_registry():
        if tier is not None and sk.get("tier") != tier:
            continue
        if domain and domain not in (sk.get("domains") or []):
            continue
        juris = sk.get("jurisdictions") or []
        if country:
            if country in juris:
                pass
            elif include_global and "global" in juris:
                pass
            else:
                continue
        out.append(sk)
    return out


def _cli_list(args: argparse.Namespace) -> int:
    sks = list_scorekeepers(
        country=args.country,
        tier=args.tier,
        domain=args.domain,
        include_global=not args.no_global,
    )
    if not sks:
        print("No scorekeepers match the filter.", file=sys.stderr)
        return 1
    print(f"{'NAME':<32} {'TIER':<6} {'JURISDICTIONS':<24} DOMAINS")
    print("-" * 100)
    for sk in sks:
        juris = ",".join(sk.get("jurisdictions") or [])
        doms = ",".join((sk.get("domains") or [])[:4])
        print(f"{sk['name']:<32} {sk['tier']:<6} {juris:<24} {doms}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    ls = subparsers.add_parser("list", help="list scorekeepers")
    ls.add_argument("--country", choices=["us", "uk", "ca"])
    ls.add_argument("--tier", type=int, choices=[2, 3])
    ls.add_argument("--domain", help="e.g. tax, benefits, healthcare")
    ls.add_argument("--no-global", action="store_true", help="exclude OECD/IMF")
    ls.set_defaults(func=_cli_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
