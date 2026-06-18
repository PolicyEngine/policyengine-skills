---
name: calibration-diagnostics
description: Stage-6 agent. Given a deviation signature (where the microsim disagrees with the prior), identifies the most likely calibration targets / imputed variables driving the gap. Reads policyengine-us-data calibration targets and known-issues to produce a ranked diagnostic checklist. The single highest-expertise stage — converts tribal knowledge into a callable agent.
tools: WebFetch, WebSearch, Read, Bash, Skill
model: opus
---

# Calibration Diagnostics

Triggered only when `reform-comparator` returns `INVESTIGATE`. Hypothesizes which calibration targets or imputed variables in `policyengine-us-data` (and equivalents) are driving the mismatch.

Loads the `policyengine-calibration-diagnostics` skill for the full sensitivity registry.

## Inputs

- `deviation_signature` (from `reform-comparator`)
- `reform` (provisions + reform-dict)
- `jurisdiction`
- `anchor` (the prior-scores anchor for context)

## Process

### Step 1: Match the program family to known sensitivities

Programs differ in which calibration inputs matter most. Use the `policyengine-calibration-diagnostics` skill index. Typical sensitivities:

| Program | High-sensitivity inputs |
|---|---|
| EITC | Takeup by family-size; childless adult earnings distribution; tax-unit definition; eligible age cohort |
| CTC | Non-filer share + non-filer takeup; imputed child age distribution; SPM threshold; refundability mechanic |
| SNAP | Eligible-unit takeup (~80%); deductions stack; categorical eligibility; state options |
| SALT cap | Itemizer share (post-TCJA ~10%); state income/property tax imputation; top-1% AGI calibration; AMT interaction |
| State income tax | State weights from CPS (small-state variance); state-AGI tail imputation; conformity rules |
| Refundable credits broadly | Non-filer share (CPS undercounts non-filers); takeup distribution by income |

### Step 2: Apply the deviation signature

Cross-reference the signature with the sensitivity table. Examples:

**Signature: "cost roughly right, poverty impact understates by 50%"** (e.g., CTC case)
- Hypothesis 1: **CTC takeup for non-filers** — if takeup is set too low for the population that benefits most from refundability, dollars flow but don't lift households out.
- Hypothesis 2: **Baseline child poverty rate** — if the calibrated baseline is too low, the percentage reduction looks compressed.
- Hypothesis 3: **SPM unit definition** — if related individuals are split into separate SPM units, the per-unit benefit is too small to clear thresholds.

**Signature: "cost too high, benefit distributed too evenly across deciles"** (e.g., SALT case)
- Hypothesis 1: **Itemizer share over-states** — too many filers in the dataset itemize, so cap removal benefits cascade down.
- Hypothesis 2: **State income tax imputation flat** — if state tax is imputed at the federal income level rather than state-specific marginal rates, the regressive signature disappears.
- Hypothesis 3: **Top-1% AGI calibration** — under-weighted top tail compresses the upper-decile concentration.

**Signature: "small-state cost very volatile vs prior"**
- Hypothesis 1: **CPS state sample size** — RI has ~3-4k person-records; calibration target uncertainty is high.
- Hypothesis 2: **State weight target mismatch** — ACS marginals are calibrated, but the joint distribution (state × AGI × kids) may not be.
- Hypothesis 3: **Conformity assumption** — state-federal interaction parameter may have changed since the prior was scored.

### Step 3: Generate the diagnostic checklist

```json
{
  "ranked_hypotheses": [
    {
      "rank": 1,
      "calibration_input": "ctc_non_filer_takeup",
      "location": "policyengine-us-data/utils/loss.py + takeup parameter",
      "expected_direction_of_effect": "raising takeup increases poverty reduction proportionally",
      "test_to_run": "Set ctc takeup to 0.95 and rerun reform; if poverty impact closes 80%+ of the gap, this is the cause.",
      "related_issues": ["github.com/PolicyEngine/policyengine-us/issues/4276 (EITC takeup)"]
    },
    {
      "rank": 2,
      "calibration_input": "imputed_child_age_distribution",
      "location": "policyengine-us-data — imputation step",
      "expected_direction_of_effect": "more 0-5 children → higher cost (the $3,600 tier)",
      "test_to_run": "Compare ECPS age-0-5 share to ACS published 2023; if off by >5%, recalibrate.",
      "related_issues": []
    },
    ...
  ],
  "next_action": "Run hypothesis #1 first (cheapest, highest-likelihood).",
  "calibration_dashboard_panels": [
    "https://policyengine.github.io/calibration-diagnostics/ctc-takeup",
    "https://policyengine.github.io/calibration-diagnostics/child-age-distribution"
  ]
}
```

(Dashboard URLs are illustrative — point at actual `calibration-diagnostics` repo deployment when known.)

### Step 4: Sources to consult

- `github.com/PolicyEngine/policyengine-us-data` — calibration targets in `utils/loss.py`; documentation site at `policyengine.github.io/policyengine-us-data`.
- `github.com/PolicyEngine/calibration-diagnostics` — the live dashboard (see Repos tab in the ecosystem dashboard).
- Open issues on `policyengine-us` and `policyengine-us-data` matching the program keyword.

## Output

A ranked diagnostic checklist that an experienced PolicyEngine engineer can act on, AND a non-expert user can at least understand the candidate causes. Each hypothesis includes a runnable test.

## Hand-off

Returns the checklist to `/analyze-policy`, which writes the final report including:
- The original microsim result
- The mismatch direction
- The ranked diagnostic hypotheses
- The recommended next test

If `--auto-investigate` is set, can chain into perturbation runs (top-1 hypothesis test) before reporting.
