#!/usr/bin/env python3
"""Preset loader and CLI for reforms + baselines.

Usage:

    python3 scripts/presets.py list                        # list all presets
    python3 scripts/presets.py list --category reform
    python3 scripts/presets.py list --country us
    python3 scripts/presets.py show <name>                 # print a preset's reform-dict

Programmatic:

    from scripts.presets import load_preset, list_presets
    p = load_preset("arpa-ctc-restoration")
    print(p["reform_dict"])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR = ROOT / "presets"


def load_preset(name: str) -> dict:
    """Load a preset by name (searches both reforms/ and baselines/)."""
    for subdir in ("reforms", "baselines"):
        path = PRESETS_DIR / subdir / f"{name}.yaml"
        if path.exists():
            preset = yaml.safe_load(path.read_text()) or {}
            preset["_source_file"] = str(path.relative_to(ROOT))
            preset["_category_from_dir"] = subdir[:-1]
            return preset
    raise FileNotFoundError(f"No preset named {name!r} in presets/reforms or presets/baselines")


def list_presets(
    *,
    category: str | None = None,
    country: str | None = None,
    parameter_family: str | None = None,
) -> list[dict]:
    """List presets, optionally filtered."""
    out: list[dict] = []
    for subdir in ("reforms", "baselines"):
        directory = PRESETS_DIR / subdir
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            preset = yaml.safe_load(path.read_text()) or {}
            preset["_source_file"] = str(path.relative_to(ROOT))
            preset["_category_from_dir"] = subdir[:-1]
            if category and preset.get("category") != category:
                continue
            if country and preset.get("country") != country:
                continue
            if parameter_family:
                fams = preset.get("parameter_families") or []
                if parameter_family not in fams:
                    continue
            out.append(preset)
    return out


def _cli_list(args: argparse.Namespace) -> int:
    presets = list_presets(
        category=args.category, country=args.country, parameter_family=args.family
    )
    if not presets:
        print("No presets match the filter.", file=sys.stderr)
        return 1
    print(f"{'NAME':<32} {'CATEGORY':<10} {'COUNTRY':<8} FAMILIES")
    print("-" * 90)
    for p in presets:
        fams = ",".join(p.get("parameter_families") or [])
        print(
            f"{p['name']:<32} {p.get('category', '—'):<10} "
            f"{p.get('country', '—'):<8} {fams}"
        )
    return 0


def _cli_show(args: argparse.Namespace) -> int:
    preset = load_preset(args.name)
    print(json.dumps(preset, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    list_p = subparsers.add_parser("list", help="list presets")
    list_p.add_argument("--category", choices=["reform", "baseline"])
    list_p.add_argument("--country", choices=["us", "uk", "ca"])
    list_p.add_argument("--family", help="filter by parameter family tag")
    list_p.set_defaults(func=_cli_list)

    show_p = subparsers.add_parser("show", help="print a preset")
    show_p.add_argument("name")
    show_p.set_defaults(func=_cli_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
