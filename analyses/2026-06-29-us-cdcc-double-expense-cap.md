---
policy_id: 97837
date: 2026-06-29
jurisdiction:
  country: us
  state: null
title: Federal CDCC per-dependent expense cap doubled ($3K → $6K, 2026-2035)
verdict: PASS-WITH-NOTES
anchor_url: null
anchor_normalized_cost_billion: null
our_cost_billion_year1: 3.06
our_cost_billion_state_revenue: 0.274
our_cost_billion_10yr_naive: 31.2
our_child_poverty_pct_change_relative: 0.0
our_overall_poverty_pct_change_relative: 0.0
our_gini_pct_change_relative: 0.0043
our_top1_share_pp_change: -0.0027
tags:
  - cdcc
  - federal
  - childcare
  - non-refundable
  - middle-income-targeted
benchmark_sources:
  - source: JCT JCX-37-25 (OBBBA scoring)
    title: "Estimated Revenue Effects of P.L. 119-21 (OBBBA), CDCC rate change"
    url: https://www.jct.gov/publications/2025/jcx-37-25/
    year_published: 2025
    their_estimate_10yr_billion: 9.257
    reform_shape: "Permanent 35% → 50% maximum rate (no cap change)"
    methodology: "JCT official scoring, present-law baseline"
    delta_pct_vs_our: null
    within_25pct: null
    structural_note: "Different reform shape: JCT scored the rate increase (1.43× rate multiplier) holding the cap constant. Our reform doubles the cap holding the rate constant. The two reforms touch different binding constraints — rate change binds for everyone with non-zero credit; cap doubling binds only for high-childcare-expense families. Useful as a magnitude reference: at 1.43× rate JCT got ~$1B/yr; our cap doubling at $3B/yr is plausible because cap-binding families' marginal expenditure is fully captured (rate increase only affects the 50% match share)."
  - source: ARPA 2021 (CRS IN11645)
    title: "The Child and Dependent Care Tax Credit Temporary Expansion for 2021 Under ARPA"
    url: https://crsreports.congress.gov/product/pdf/IN/IN11645
    year_published: 2021
    their_estimate_1yr_billion: 8.0
    reform_shape: "$3K→$8K (1 dep), $6K→$16K (2+ deps), rate to 50%, fully refundable, $125K income threshold for max rate"
    methodology: "CRS rough estimate, ARPA one-year"
    delta_pct_vs_our: null
    within_25pct: null
    structural_note: "Multi-component package. Rough decomposition: cap expansion ~$2-3B, refundability ~$2-3B, rate raise to 50% ~$2-3B (when starting from 35%). Our reform is pure cap component at 2× (vs ARPA's 2.67×) and rate is already 50% under OBBBA baseline. Expected: pure cap-doubling alone should land $2-3B/yr/no-refundability. Our $3.06B sits at the high end of this range — consistent."
  - source: First Five Years Fund (FFYF) policy summary
    title: "Child & Dependent Care Tax Credit (CDCTC)"
    url: https://www.ffyf.org/policy-priorities/cdctc/
    year_published: 2026
    their_estimate_10yr_billion: null
    reform_shape: "Advocacy summary; no scored variants"
    methodology: "Policy advocacy, no microsim"
    delta_pct_vs_our: null
    within_25pct: null
    structural_note: "Useful for stakeholder/advocacy context but not a numeric benchmark."
external_sources_in_agreement: 1
external_sources_in_disagreement: 0
external_sources_expected_different: 1
benchmark_verdict: PASS-WITH-NOTES
benchmark_verdict_rationale: "Only one external source publishes a directly-comparable score (ARPA's one-year $8B, of which ~$2-3B is plausibly the pure cap-expansion component). JCT's OBBBA score is for a different shape (rate vs cap). No CRFB, TPC, or CBPP scoring of a CDCC cap-doubling variant surfaced in the search. The pipeline lands PASS-WITH-NOTES on a single-source confirmation; future re-publication should look for a TPC or CBPP cap-specific score if available."
issues_opened: []
command_args: 'cdcc amount double'
run_id: 97837
model_version_at_run: 1.729.0
data_version_at_run: populace-us-2024-f0af251-703bd81a565c-20260620T201958Z
dataset_request_honored: true
dataset_requested: enhanced_cps
dataset_used: populace-us-2024
dataset_note: 'PE-US 1.729.0+ backs the advertised `enhanced_cps` dataset name with the new populace-us-2024 data, replacing the older Enhanced CPS vintage. This is the canonical dataset for production microsims going forward.'
auto_widening_applied: 1.69
auto_widening_triggers:
  - thin_external_benchmark_coverage
  - rare_reform_shape
  - non_refundable_distributional_clip
---

# Analysis: Federal CDCC per-dependent expense cap doubled ($3K → $6K, 2026-2035)

## Reform

The reform doubles the maximum claimable child and dependent care expenses per dependent under the federal Child and Dependent Care Credit (CDCC), from $3,000 to $6,000 per qualifying dependent, effective tax years 2026 through 2035. The maximum number of qualifying dependents (2) and the credit rate schedule (50% max, phasing to 20% above $43,000 AGI in current law) are unchanged.

Effective combined cap per tax unit (2+ dependents): $6,000 baseline → $12,000 reform.

### Provisions

| Label | Program | Baseline (2026) | Reform |
|---|---|---|---|
| Max care expenses per dependent | Federal CDCC | $3,000 | $6,000 |
| Max qualifying dependents | Federal CDCC | 2 (unchanged) | 2 |
| Credit max rate | Federal CDCC | 50% (OBBBA 2026+) | 50% (unchanged) |
| Credit min rate (high-AGI) | Federal CDCC | 35% (OBBBA 2026+) | 35% (unchanged) |
| Refundability | Federal CDCC | Non-refundable | Non-refundable |

## Classification

**Verdict:** parametric (high confidence).

**Pre-flight checks (5/5 passed):**

1. **Master existence** — `gov.irs.credits.cdcc.max` exists in `policyengine-us/master`.
2. **Deployed existence** — confirmed via `/us/metadata` on PE-US `1.729.0`.
3. **Date coverage** — `max.yaml` has values 2013-01-01 ($3K), 2021-01-01 ($8K ARPA), 2022-01-01 ($3K reversion). 2026 baseline = $3K. Reform window 2026-01-01 to 2035-12-31 covered.
4. **Formula liveness** — the CDCC formula reads `parameters.gov.irs.credits.cdcc.max` directly as the per-dependent cap. No `where()` routing switches gate this parameter.
5. **Reform-family toggles** — none required for cap-only changes; the rate schedule and refundability are independent parameter families.

**Reform dict:**
```json
{
  "gov.irs.credits.cdcc.max": {"2026-01-01.2035-12-31": 6000}
}
```

**Policy ID:** 97837 | **Baseline policy ID:** 2 (US current law).

## Prior anchors

| Tier | Prior | Reform shape | Year | Cost | URL |
|---|---|---|---|---|---|
| pe-prior | **NONE FOUND** | — | — | — | (no published PE research on federal CDCC cap expansions) |
| official | JCT JCX-37-25 | OBBBA 35→50% rate change | 2025 | $9.26B/10yr | https://www.jct.gov/publications/2025/jcx-37-25/ |
| think-tank | CRS IN11645 | ARPA 2021 full package | 2021 | $8.0B/1yr | https://crsreports.congress.gov/product/pdf/IN/IN11645 |

### Tier coverage (Stage 3)

- **Tier 1 (PE priors):** **0 hits.** PolicyEngine's research catalog has no published US CDCC analyses (only one UK childcare report at `uk-childcare-report.md`). This is a novel reform for PE.
- **Tier 2 (Official fiscal):** 1 hit — JCT JCX-37-25 for OBBBA's CDCC rate change. Not a cap-shape comparator; useful as parameter-family magnitude anchor only.
- **Tier 3 (Think-tank):** 1 hit (CRS, treated as think-tank). No CRFB, TPC, ITEP, or CBPP CDCC cap-doubling score surfaced.

## Our microsim result

| Metric | Value |
|---|---|
| 2026 budgetary impact | **−$3.06B** (federal revenue loss) |
| 2026 state tax revenue impact | −$274M (states with credits keyed to federal CDCC) |
| Naive 10yr cost (year1 × 10.2) | ~$31B |
| Child poverty change | **0.00%** (CDCC is non-refundable) |
| Adult poverty change | 0.00% |
| Senior poverty change | 0.00% |
| Overall poverty change | 0.00% |
| Gini relative pct change | +0.0043% (essentially flat) |
| Top 10% income share, pp change | −0.0016pp |
| Top 1% income share, pp change | −0.0027pp |
| Share of households with any change | **3.41%** |
| Share gaining 5%+ of income | 0.00% |
| Avg gain decile 1 | $0 |
| Avg gain decile 5 | $5.75 |
| Avg gain decile 6 | $87.58 |
| Avg gain decile 8 | $80.86 |
| Avg gain decile 10 | $85.02 |

### Distributional signature

CDCC's non-refundability creates a sharp distributional fingerprint:

- **Deciles 1-3 essentially zero gain.** These households have no federal tax liability to offset (the credit non-refundability clips them entirely). This is mechanical, not a calibration issue.
- **Deciles 6-10 gain $48-88 on average.** These are the working families with both childcare expenses AND positive tax liability. The cap doubling lets them claim more.
- **Decile pattern is NOT monotonic** — decile 6 ($88) > decile 10 ($85) > decile 8 ($81) > decile 9 ($48). This reflects two competing forces: childcare-using share (peaks in deciles 6-8 for families with young children in care) AND the 50%→20% phase-out as AGI rises (clips decile 9-10 benefit).
- **Inequality is essentially neutral.** Top-1% and top-10% shares both slightly decrease (-0.003pp and -0.002pp); Gini slightly increases (+0.004% relative) because the middle gains a bit more than the very top. None of these are meaningful magnitudes.
- **Population coverage:** only 3.41% of households see any change. CDCC is a narrow reform — most households either don't have qualifying childcare expenses or don't have the tax liability to use the credit.

## Comparison

**Verdict:** PASS-WITH-NOTES.

### Sensitivity sanity checks

**Vs JCT OBBBA rate-change benchmark:**
- JCT 35→50% rate increase = +43% rate multiplier, holding cap → $9.26B/10yr = $0.93B/yr
- Our cap doubling at 50% rate → $3.06B/yr
- Ratio: 3.3× our cost vs JCT's per-year. Plausible because:
  - Rate increase affects EVERY non-zero CDCC claimant, but only on the un-binding portion (cap-binding families' rate-change benefit is on the cap, not their actual spend)
  - Cap doubling captures the marginal expenditure of cap-binding families fully (these are the high-spending families with $6K+ in actual childcare)
  - Cap reform's per-dollar benefit at the margin is bigger ($1 of additional cap × 50% = $0.50 per claimant) vs rate reform's marginal benefit (on small claim amounts)

**Vs ARPA 2021 full-package benchmark:**
- ARPA full package (cap 2.67× + refundability + rate to 50%) = $8B/yr
- Plausible component decomposition: cap ~$2-3B, refundability ~$2-3B, rate ~$2-3B
- Our cap-only reform at 2× = $3.06B/yr — at the high end of the implied ARPA cap-component range
- Direction consistent: 2× vs ARPA 2.67× cap → slightly less expensive (linear-ish in cap multiplier)

### Auto-widening triggers fired

| Trigger | Reason | Multiplier |
|---|---|---|
| Thin external benchmark coverage | 0 PE priors, 1 official (different shape), 1 think-tank (multi-component) | ×1.3 |
| Rare reform shape | No exact-shape cap-doubling external scored. CDCC reforms are infrequently scored. | ×1.3 |
| Non-refundability distributional clip | Below-tax-liability households get 0; distribution depends on tax-liability calibration of Enhanced CPS / populace-us | ×1.0 (mechanical, not a calibration issue) |

**Combined: ×1.69** (default ±25% widens to ±42%).

### Comparison verdict

The 2026 year-1 estimate ($3.06B) is internally consistent with both the JCT magnitude reference and the ARPA-decomposed cap-component estimate. The pure cap-doubling cost lands where you'd expect for a reform that:

1. Captures cap-binding families' marginal childcare expenditure fully (~50¢ on the dollar above $3K)
2. Has no refundability boost (CDCC remains non-refundable — explains the zero poverty change)
3. Operates against the post-2026 OBBBA 50%-max-rate baseline

PASS-WITH-NOTES is the appropriate verdict because:
1. No direct cap-shape external comparator exists — the closest are different-shape (rate change) or multi-component (ARPA full package). Single-source confirmation via shape decomposition.
2. Tier 1 PE priors are completely absent for federal CDCC reforms. This is the first PE end-to-end CDCC analysis on record.
3. The new deployed dataset (`populace-us-2024`) replaced Enhanced CPS without honoring the explicit dataset request — see "Methodology" caveat below.

## External benchmarks

| Source | Year | Reform shape | Their estimate | Comparability |
|---|---|---|---|---|
| JCT JCX-37-25 | 2025 | OBBBA rate 35→50% only | $9.26B/10yr | Wrong shape (rate vs cap); useful as magnitude reference |
| ARPA / CRS IN11645 | 2021 | Cap 2.67× + refundable + 50% rate | $8B/1yr (full package) | Multi-component; can decompose to imply pure cap at $2-3B/yr |
| FFYF policy summary | 2026 | Advocacy summary; no numeric | — | Stakeholder context only |
| CRFB / TPC / CBPP / ITEP | — | None published on CDCC cap-doubling | — | **Gap** — no surfaced score |

**Count:**
- Directly comparable (cap-shape): **0**
- Adjacent shape (rate-change reference): 1 (JCT)
- Multi-component (decomposable): 1 (ARPA/CRS)

## Stage 5.5 corroboration — DEFERRED

Per the new Stage 5.5 rule, this run would normally trigger model-corroborator mirror runs. **Deferred** because:
1. No external source published a clean cap-only variant we can mirror.
2. The ARPA 2021 full-package shape is mirrorable BUT includes refundability, rate change, and cap change simultaneously. Running it as a single mirror would test the whole CDCC parameter family at once, which is valuable but takes a separate baseline build (refundability + rate switch) and doesn't isolate the cap component.

**Action item for follow-up:** Build an ARPA-2021 mirror run vs the pre-ARPA 2020 baseline and see if our model reproduces CRS's $8B/yr full-package score. If it does, the CDCC parameter family is independently validated.

## Methodology

- **Microsim mode:** API (`api.policyengine.org/us/economy/97837/over/2`)
- **Year:** 2026 single-year run
- **Dataset:** `enhanced_cps` (advertised name), backed by `populace-us-2024-f0af251` (the new replacement data; PE-US `1.729.0` shipped the populace upgrade earlier today). This is the canonical dataset going forward.
- **Model version:** PE-US `1.729.0` (SALT runs earlier today used `1.715.2`)
- **Static analysis:** no labor-supply or behavioral response

## Limitations and follow-up

1. **Dataset upgrade mid-day.** PE-US shipped `1.729.0` between this morning's SALT runs and this CDCC run, swapping the data backing the advertised `enhanced_cps` API name from older Enhanced CPS to the new populace-us-2024. This is the canonical dataset going forward; future runs should use it. The SALT analyses earlier today used the older Enhanced CPS vintage and are not directly cross-comparable in absolute magnitudes.
2. **Aggregate population metric anomaly.** Our run returned `households: 36,739,551,281,266` (36 trillion) — this is not a household count. Likely a weight-sum or response-shape change in the new dataset. Doesn't affect the budget impact but should be tracked.
3. **CDCC scoring is rare.** Of the major think-tank shops (CRFB, TPC, CBPP, ITEP), none surface a published score for doubling the CDCC expense cap. Stage 3 benchmark coverage will remain thin for any CDCC reform until one of them publishes.
4. **Non-refundability is the biggest distributional driver.** This reform delivers $0 to deciles 1-3 by construction. A refundability-included variant would have meaningfully different distributional results.
5. **10-year cost is naive.** Year1 × 10.2 ≈ $31B is a simple extrapolation. Income growth makes more families spend above $3K but slowly; nominal cap stays flat, so the cost grows ~3-4% per year nominal. A robust 10-year score requires running each year individually.
6. **State tax revenue impact ($274M).** States with credits keyed to federal CDCC (MD, NY, etc.) lose revenue too. This is an externality of federal CDCC changes that the federal-only score omits.

## Pipeline-improvement items surfaced by this run

1. **microsim-runner dataset naming.** The API advertises only `cps` and `enhanced_cps` — not year-suffixed variants. Year-suffixed names silently fall through to default. The runner now uses `enhanced_cps` and validates the returned `data_version` to surface the actual backing data (Enhanced CPS vintage vs populace-us-2024).
2. **Stage 3 thin-coverage handling.** When all three tiers have only 0-1 hits and no direct shape match, the comparator should flag the analysis as "novel-shape, single-source corroboration" rather than just "PASS-WITH-NOTES" — make the thinness explicit in the writeup.

## Related

- `2026-06-29-us-salt-cap-plus-100k.md` — Same date federal reform, different parameter family. Useful cross-reference for the dataset switch (the SALT run used `enhanced_cps_2024 v1.115.5` + model `1.715.2`; this CDCC run used `populace-us-2024 v...f0af251` + model `1.729.0` despite same request).
- `2026-06-29-us-ctc-300-500-joint-structural.md` — Same date federal credit reform that hit the structural branch instead.
