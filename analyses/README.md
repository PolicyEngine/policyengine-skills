# Analyses archive

Every `/analyze-policy` run lands here (by default) as a dated markdown file with frontmatter.

## Path resolution

The `report-logger` agent picks the archive directory in this order:

1. `--log-to archive:<path>` if explicitly passed
2. `$PWD/analyses/` if it exists (you're in a repo with an `analyses/` folder)
3. `$POLICYENGINE_ANALYSES_DIR` environment variable if set
4. `~/.policyengine/analyses/` (auto-created)

For users running this plugin against their own repos, set `POLICYENGINE_ANALYSES_DIR` once in your shell rc, OR create an `analyses/` folder in the repo you're working in.

## File naming

`YYYY-MM-DD-<jurisdiction>-<slug>.md`

Examples:
- `2026-06-19-us-arpa-ctc-restoration.md`
- `2026-06-12-ri-h7127-state-ctc.md`
- `2026-05-08-us-salt-cap-repeal.md`

## Frontmatter (current schema)

Every archived analysis has YAML frontmatter for searchability. Minimum required fields plus optional blocks that accumulate as the pipeline runs:

```yaml
---
# Identity
policy_id: 97833                    # PE API policy_id (int)
date: 2026-06-29                    # ISO date the run happened
title: "Federal SALT cap raised by $100,000 per filing status, no phase-out (2026-2035)"
jurisdiction:
  country: us                       # us | uk | ca
  state: null                       # or "ri", "vt", "us-ny", etc.
tags: [salt, federal, itemized-deductions, tcja, obbba]

# Publication inputs — consumed downstream by the CRM publication router
# (bill-tracker / dashboard chain). description is the reform-describer's
# 1-paragraph neutral provisions summary. reform_dict is the EXACT validated
# JSON from the Phase 2 classifier, minified on a single line inside a block
# scalar. Omit reform_dict when the verdict is structural / not-possible.
description: "Raises the federal SALT deduction cap by $100,000 per filing status with no income phase-out, effective 2026 through 2035."
reform_dict: |
  {"gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": {"2026-01-01.2035-12-31": 110000}}

# Verdict (one of):
#   PASS | PASS-WITH-NOTES | PASS-WITH-CORROBORATION
#   INVESTIGATE | structural | not-possible | deployed-model-lag | BLOCKED
verdict: PASS-WITH-NOTES

# Run metadata
run_id: 97833
model_version_at_run: 1.745.0
data_version_at_run: populace-us-2024-cd-concept-budget-...
command_args: "flat $100K SALT cap, no phase-out, 2026-2035"

# Horizon (added by the Phase 0 horizon prompt)
horizon: 1                          # 1 | 10 | custom (int or list)
horizon_note: "Single-year run only. No 10-year cost reported..."

# Headline metrics — units are always $ billions and % relative
our_cost_billion_year1: 26.79
our_cost_billion_state_revenue: 0.031
our_cost_billion_10yr_actual_federal: 196.10  # ONLY when horizon > 1 (real per-year sum)
our_child_poverty_pct_change_relative: -0.0097
our_gini_pct_change_relative: 0.0495
our_top1_share_pp_change: 0.0242

# Anchor (Stage 3 preferred anchor)
anchor_url: https://policyengine.org/us/research/ways-and-means-salt-cap
anchor_normalized_cost_billion: 937.0

# External benchmarks (Stage 3 Tier 2 + Tier 3)
benchmark_sources:                  # array of {source, url, year_published, their_estimate_10yr_billion, reform_shape, delta_pct_vs_our, within_25pct, structural_note}
  - source: CRFB (Jan 2025)
    ...
external_sources_in_agreement: 2
external_sources_in_disagreement: 3
external_sources_expected_different: 1
benchmark_verdict: PASS-WITH-NOTES

# Auto-widening (reform-comparator Step 2 triggers)
auto_widening_applied: 2.73          # multiplier on tolerance band
auto_widening_triggers:
  - baseline_schedule_mismatch
  - naive_10yr_extrapolation_across_regime_shift

# Stage 5.5 corroboration (only when the corroborator ran)
stage_5_5_corroboration:
  ran: true
  overall_verdict: CORROBORATION-FAILED  # CORROBORATED | PARTIAL-CORROBORATION | CORROBORATION-FAILED | NO-CORROBORATION-POSSIBLE
  failure_mode: baseline_construction_not_model_calibration
  candidates:
    - source: CRFB Jan 2025
      mirror_policy_id: 97835
      their_yr1_implied_billion: -82.0
      our_yr1_billion: -28.90
      delta_pct: -64.8
      verdict: DRIFT-LOW
      drift_explanation: "..."
  action_items: []
  verdict_impact: "..."

# Destinations (populated after report-logger runs)
issues_opened: []                   # array of {repo, number, url, verdict_reason}
---
```

Search by grep:

```bash
grep -l "verdict: INVESTIGATE" analyses/*.md
grep -l "state: ri" analyses/*.md
grep -l "horizon: 10" analyses/*.md            # find real 10-year runs
grep -l "PASS-WITH-CORROBORATION" analyses/*.md
grep -l "CORROBORATION-FAILED" analyses/*.md   # candidates for follow-up
```

## What's NOT here

- Drafts for publication (those go in the analysis repo via `--log-to draft:...`)
- State-bill analyses being tracked in Supabase (those go via `--log-to tracker`)
- GitHub issues opened by the logger (those are referenced by issue number in the frontmatter's `issues_opened` list)
