# Presets library

Callable-by-name reform-dicts and baseline policies for `/analyze-policy` and adjacent agents. Presets exist so:

- Analysts don't have to hand-type `gov.irs.credits.ctc.amount.arpa[0].amount` every time they want to score ARPA CTC restoration.
- Stage 5.5 model corroboration has turn-key mirror candidates when it needs to run "the same shape TPC scored."
- Agents can reference reforms by stable identifier across the archive, issues, and blog drafts.

## Directory layout

```
presets/
├── reforms/     # named reform-dicts
│   ├── arpa-ctc-restoration.yaml
│   ├── obbba-salt-bump.yaml
│   └── ...
└── baselines/   # named baseline policies
    ├── tcja-extension.yaml
    ├── pre-obbba.yaml
    └── ...
```

Each preset is a self-contained YAML file with metadata + a reform-dict block.

## Preset shape

```yaml
name: arpa-ctc-restoration            # kebab-case slug used to reference it
description: "Reinstate ARPA-era CTC ($3,600 ages 0-5, $3,000 ages 6-17, fully refundable)"
country: us
category: reform                      # reform | baseline
parameter_families: [ctc]             # tags for KB search + related-analysis linking
published_scores:                     # optional: what external sources have scored this shape
  - source: JCT
    url: "..."
    ten_year_billion: 1100
  - source: TPC
    url: "..."
    ten_year_billion: 1200
reform_dict:
  gov.irs.credits.ctc.amount.arpa[0].amount:
    "2026-01-01.2035-12-31": 3600
  gov.irs.credits.ctc.amount.arpa[1].amount:
    "2026-01-01.2035-12-31": 3000
  gov.irs.credits.ctc.phase_out.arpa.in_effect:
    "2026-01-01.2035-12-31": true
  gov.irs.credits.ctc.refundable.fully_refundable:
    "2026-01-01.2035-12-31": true
```

For baseline presets, `category: baseline` and the `reform_dict` describes the parameter overrides that construct the baseline (e.g., tcja-extension reverts SALT + std ded + AMT to TCJA-continued values).

## Using presets

### From `/analyze-policy`

```
/analyze-policy preset:arpa-ctc-restoration
/analyze-policy preset:arpa-ctc-restoration --horizon 10
/analyze-policy preset:arpa-ctc-restoration vs baseline:tcja-extension
```

Under the hood: `policy-text-researcher` recognizes the `preset:<name>` syntax, loads the YAML, and skips the text-extraction stage entirely (the reform-dict is already structured).

### From `model-corroborator` (Stage 5.5)

The corroborator inspects `benchmark_sources[].preset_slug` on each Tier-3 external. When a slug is set, it loads the preset instead of building a mirror reform-dict from a prose `reform_shape` description. Removes translation error from the mirror step.

### From scripts

```python
from scripts.presets import load_preset

preset = load_preset("arpa-ctc-restoration")
reform_dict = preset["reform_dict"]
```

## Adding a preset

1. Copy a nearby preset file, edit values.
2. Add a `published_scores` block if any external source has scored this shape — this is what makes Stage 5.5 corroboration turn-key.
3. Rebuild the manifest: `python3 scripts/build_manifest.py`. Presets show up in the dashboard `Catalog` tab.
4. When you use the preset in an analysis, cite it in the archive frontmatter: `preset: arpa-ctc-restoration`.

## Seed presets

- **`arpa-ctc-restoration`** — Full ARPA CTC ($3,600 / $3,000, refundable, no phase-out).
- **`obbba-salt-bump`** — OBBBA's 2025 SALT cap raise ($10K → $40K joint, $500K phase-out).

## Seed baselines

- **`tcja-extension`** — TCJA continued indefinitely: SALT $10K, standard deduction reverted, AMT reverted, tax rates continued. Required for corroborating any external score that used "TCJA extension" as its baseline (CRFB, TPC most-published SALT/CTC scores use this).

### Wanted next (not yet authored)

- **`pre-obbba`** — current law just before OBBBA enactment, for mirroring 2024–early-2025
  published scores. Authoring it requires care (many OBBBA provisions to unwind); do not
  reference it in commands until the YAML exists — `load_preset` raises on missing names.
