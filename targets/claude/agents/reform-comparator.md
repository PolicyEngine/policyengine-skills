---
name: reform-comparator
description: Stage-5 comparator. Takes the microsim output and the prior-scores anchor, returns PASS (within expected band, write up the result) or INVESTIGATE (mismatch, trigger calibration-diagnostics). Normalizes single-year vs 10-year scores and accounts for dataset-version drift.
tools: Read, Bash, Skill
model: sonnet
---

# Reform Comparator

Stage 5 of `/analyze-policy`. Compares our microsim output to the prior-scores anchor and decides whether the result is consistent or needs investigation.

## Inputs

- `microsim_result` (from `microsim-runner`) — **may be null in `--skip-microsim` mode**
- `prior_anchor` (from `prior-scores-finder` — `anchors[preferred_anchor_index]`)
- `tolerance_band` (default: ±25% on cost, ±5 absolute pp on poverty)

### When `microsim_result` is null (`--skip-microsim` mode)

The /analyze-policy command invokes the comparator with `microsim_result=null` when the user passed `--skip-microsim`. In that case:

1. Construct a **synthetic predicted result** from the anchor:
   - Take the anchor's `magnitudes` block.
   - Normalize per Step 1 below (year alignment + 10-year extrapolation if needed).
   - Emit the normalized values as the "predicted" result with `synthetic: true` flag.
2. Treat the synthetic result as if it were our microsim output for the comparison step.
3. Return verdict — typically PASS by construction. This is intentional: process-test mode validates the **pipeline plumbing**, not the actual numerical agreement.
4. In the output, set `verdict_caveat: "process-test — predicted result derived from anchor, not from live microsim"` so the downstream report doesn't claim a real validation.

The synthetic-result schema mirrors `microsim_result`:

```json
{
  "synthetic": true,
  "predicted_from_anchor": "Restoration of ARPA CTC",
  "results": {
    "budget": {"annual_cost_billion_year1": 110.2},
    "poverty": {"child_pct_change": -37.0},
    "distribution": {"gini_pct_change": -1.9}
  }
}
```

## Process

### Step 1: Normalize the prior to our run

Most prior PE scores are reported as either single-year cost or 10-year cost, on a specific dataset version. To compare apples-to-apples:

1. **Year alignment.** If the anchor reports 2023 single-year cost and our run is 2026 multi-year, uprate the anchor:
   - Wage growth: assume +2.5-3.5%/yr nominal (use CBO macroeconomic projections if explicit).
   - Population growth: +0.5-0.7%/yr.
   - Combined uprating factor: anchor_2023 × (1 + 0.035)^(2026-2023) ≈ × 1.10 for 2026 single-year.
2. **Single-year → 10-year extrapolation.** If anchor is single-year and our run is 10-year, multiply by ~10.5-11.5 (accounting for growth over the window). Or, if anchor is a 5-year score and ours is 10-year, double.
3. **Dataset version note.** If the anchor used the older CPS dataset and our run uses Enhanced CPS, flag a known direction-of-difference (Enhanced CPS typically yields ~5-10% higher refundable-credit costs).

### Step 2: Compute the comparison

For each headline metric:

| Metric | Our result | Normalized prior | Δ (abs) | Δ (pct) | Within tolerance? |
|---|---|---|---|---|---|
| 10yr cost | $1,450B | $1,100-1,300B | +$200B | +14% | YES |
| Child poverty Δ | -34.1% | -30-40% | within range | — | YES |
| Gini Δ | -2.0% | -1.9% | -0.1pp | -5% | YES |

### Step 3: Verdict

- **`PASS`** — all headline metrics within 0–80% of the tolerance band. Proceed to write-up.
- **`PASS-WITH-NOTES`** — at least one metric within 80–100% of the band (i.e., not breached, but close enough to warrant a flag). Proceed, but list the close-call metrics in the write-up so the reader knows where to look if the result is republished against a refined anchor.
- **`INVESTIGATE`** — at least one headline metric outside the tolerance band. Trigger `calibration-diagnostics` with the deviation signature.

Example: tolerance is ±25% on cost. Δ within 0–20% → PASS. Δ within 20–25% → PASS-WITH-NOTES. Δ > 25% → INVESTIGATE.

### Step 4: Build the deviation signature (for INVESTIGATE)

When triggering `calibration-diagnostics`, pass a precise signature so the diagnostics agent can hypothesize:

```json
{
  "verdict": "INVESTIGATE",
  "deviation_signature": {
    "primary_metric": "child_poverty_pct_change",
    "our_value": -17.0,
    "anchor_value": -34.0,
    "magnitude_off_by": "half",
    "direction": "under-states-impact",
    "related_metrics_okay": ["10yr_cost"],
    "related_metrics_also_off": [
      {"metric": "gini_pct_change", "our_value": -0.9, "anchor_value": -1.9, "direction": "under-states-impact"}
    ],
    "parallel_deviation_note": "child_poverty and gini both off by ~half in the same direction while cost is roughly correct — suggests a SINGLE upstream driver (one calibration target affecting both distributional and poverty outputs simultaneously) rather than two independent problems."
  },
  "hypothesis_seeds": [
    "Cost is roughly correct but poverty + Gini both understate by half — dollars flow to the right households but their per-unit benefit is too small to lift them across thresholds. Likely: refundability switch not firing for non-filers, OR SPM unit aggregation is splitting beneficiaries across units."
  ]
}
```

**Parallel deviations are diagnostic.** When two related metrics are off in the same direction by similar magnitudes, that's strong evidence of one upstream cause. Always populate `related_metrics_also_off` for any metric outside tolerance, and write the `parallel_deviation_note` if a pattern emerges. The diagnostics agent uses this to rank hypotheses (single-driver hypotheses score higher when the pattern is parallel).

## Output

```json
{
  "verdict": "PASS" | "PASS-WITH-NOTES" | "INVESTIGATE",
  "comparison_table": [...],
  "normalization_notes": "Anchor 2023 single-year cost uprated 1.10x for 2026; extrapolated to 10-year by *10.8.",
  "deviation_signature": null | {...},
  "methodology_carried_forward": {
    "anchor_dataset": "Enhanced CPS 2023",
    "anchor_static_or_dynamic": "static",
    "anchor_url": "https://policyengine.org/us/research/...",
    "our_run_dataset": "Enhanced CPS 2026",
    "our_run_mode": "api"
  },
  "next_stage": "write-report" | "diagnose-calibration"
}
```

The `methodology_carried_forward` block threads through to the `reform-describer` and the final report's Methodology section. Always populate it — if a value is unknown (e.g., process-test mode), set it to `"unknown"` rather than omitting.

## Tolerance defaults

- **Budgetary cost:** ±25% of normalized prior.
- **Poverty Δ (overall, child, deep):** ±5 absolute percentage points OR ±20% relative, whichever is wider.
- **Gini Δ:** ±0.5 absolute pp.
- **Top-decile share of benefit:** ±10 absolute pp.

For known-noisy cases (small states, narrow populations), widen to ±35% / ±10pp.

## Hand-off

- `PASS` → `/analyze-policy` writes the report and exits.
- `INVESTIGATE` → invoke `calibration-diagnostics` with the deviation signature.
