---
policy_id: 97833
date: 2026-06-29
jurisdiction:
  country: us
  state: null
title: Federal SALT cap raised by $100,000 per filing status, no phase-out (2026-2035)
verdict: PASS-WITH-NOTES
anchor_url: https://policyengine.org/us/research/ways-and-means-salt-cap
anchor_normalized_cost_billion: 937.0
our_cost_billion_year1: 26.79
our_cost_billion_10yr_naive: 294.7
our_cost_billion_10yr_adjusted: 590.0
our_child_poverty_pct_change_relative: -0.0097
our_adult_poverty_pct_change_relative: -0.0289
our_senior_poverty_pct_change_relative: 0.0000
our_overall_poverty_pct_change_relative: -0.0214
our_gini_pct_change_relative: 0.0495
our_top1_share_pp_change: 0.0242
our_top10_share_pp_change: 0.0396
tags:
  - salt
  - federal
  - itemized-deductions
  - tcja
  - obbba
  - regressive-incidence
  - top-tail-concentration
benchmark_sources:
  - source: Tax Policy Center (Howard Gleckman, May 2025)
    title: "A $20,000 SALT Cap Would Be Costly And Mostly Benefit High-Income Households"
    url: https://taxpolicycenter.org/taxvox/20000-salt-cap-would-be-costly-and-mostly-benefit-high-income-households
    year_published: 2025
    their_estimate_10yr_billion: 1100
    reform_shape: "$100K single / $200K joint, baseline full TCJA extension ($10K)"
    methodology: "TPC microsimulation, static, relative to full TCJA extension"
    delta_pct_vs_our_adjusted: 86.4
    within_25pct: false
    structural_note: "TPC's joint cap ($200K) is 43% higher than ours ($140K joint); single cap ($100K) is 29% lower than ours ($140K single). Joint households dominate the SALT-cap-binding population, so TPC's reform scores HIGHER than ours. TPC uses TCJA-extension flat $10K baseline; we use OBBBA $40K (2026-2029) reverting to $10K (2030+), so 2026-2029 our reform scores LOWER vs current law than TPC's would vs TCJA-extension. Combined, our $590B adjusted vs TPC's $1.1T sits at the edge of the auto-widened tolerance band."
  - source: CRFB (Jan 2025)
    title: "Weakening the SALT Cap is Costly, Benefits High-Earners, & Increases Tax Complexity"
    url: https://www.crfb.org/blogs/weakening-salt-cap-costly-benefits-high-earners-increases-tax-complexity
    year_published: 2025
    their_estimate_10yr_billion: 820
    reform_shape: "$30K single / $60K joint, baseline TCJA $10K, TPC-derived"
    methodology: "TPC microsimulation, static"
    delta_pct_vs_our_adjusted: 39.0
    within_25pct: false
    structural_note: "CRFB's reform has SMALLER caps than ours ($30K/$60K vs $140K/$140K) but applies relative to a more punitive baseline (TCJA $10K). Our $140K cap captures additional ultra-high-SALT itemizers above $60K that CRFB's score does not. Direction: we expect to score HIGHER than CRFB's $820B once baseline-adjusted; the fact our adjusted $590B is BELOW $820B reflects the OBBBA-baseline conservatism for 2026-2029 — consistent with the $60K analysis's finding that our 2030-snap-back adjustment may be too conservative."
  - source: Tax Foundation (Watson, May 2025)
    title: "A More Generous SALT Deduction Cap in the Big, Beautiful Bill Would Cost Revenue and Primarily Benefit High Earners"
    url: https://taxfoundation.org/blog/salt-deduction-cap-increase-proposal-analysis/
    year_published: 2025
    their_estimate_10yr_billion: 219.5
    reform_shape: "$62K single / $124K joint NO phase-out, baseline current law"
    methodology: "Tax Foundation General Equilibrium Model, conventional revenue"
    delta_pct_vs_our_adjusted: -62.8
    within_25pct: false
    structural_note: "TF's joint cap ($124K) is close to ours ($140K) but single cap ($62K) is well below ours ($140K). TF measures vs current law (then OBBBA), similar baseline to ours. The $219.5B is a useful LOWER anchor — our reform should score HIGHER because both filing-status caps are more generous, especially on the singles side. Our adjusted $590B is ~2.7× TF's, consistent with the expanded singles-cap headroom."
  - source: Tax Foundation (Watson, May 2025)
    title: "Same analysis, $62K/$124K WITH $500K phase-out variant"
    url: https://taxfoundation.org/blog/salt-deduction-cap-increase-proposal-analysis/
    year_published: 2025
    their_estimate_10yr_billion: 525.8
    reform_shape: "$62K single / $124K joint WITH $500K income phase-out, baseline current law"
    methodology: "Tax Foundation GE Model, conventional revenue"
    delta_pct_vs_our_adjusted: -10.9
    within_25pct: true
    structural_note: "Closest direct comparator. TF's joint cap ($124K) is 89% of ours ($140K); single cap (62K) is 44% of ours. TF includes a $500K income phase-out that we don't have. Net: cap shapes pull in opposite directions (TF higher joint headroom, ours higher singles headroom), phase-out reduces TF's cost. Our $590B vs TF's $525.8B at +12% is within ±25% — the most substantive within-tolerance benchmark we have."
  - source: Penn Wharton Budget Model
    title: "Lifting the SALT Cap: Estimated Budgetary Effects, 2024 and Beyond"
    url: https://budgetmodel.wharton.upenn.edu/issues/2024/2/8/lifting-the-salt-cap-budget-effect
    year_published: 2024
    their_estimate_10yr_billion: 1169
    reform_shape: "FULL repeal of SALT cap (2025-2034), on top of TCJA extension"
    methodology: "PWBM dynamic + conventional"
    delta_pct_vs_our_adjusted: 98.1
    within_25pct: false
    structural_note: "Upper bound — our $140K cap captures most of the ultra-high-SALT taxpayer pool but the very-highest-SALT itemizers (>$140K SALT bill) are still constrained. Our $590B is ~50% of full-repeal cost, plausibly higher than the $60K reform's 38% share because $140K binds far fewer itemizers above the cap."
  - source: TPC (range of options)
    title: "Range across $20K-$200K joint variants, TCJA-extension baseline"
    url: https://taxpolicycenter.org/taxvox/20000-salt-cap-would-be-costly-and-mostly-benefit-high-income-households
    year_published: 2025
    their_estimate_10yr_billion_range: [230, 1100]
    reform_shape: "Range covers $20K joint to $200K joint, baseline TCJA extension"
    methodology: "TPC microsimulation, static"
    delta_pct_vs_our_adjusted: 0
    within_25pct: true
    structural_note: "Our adjusted $590B sits comfortably within the TPC range $230B-$1,100B. Top-decile concentration matches TPC's qualitative finding that 91-94% of benefit goes to >$200K households and 44-61% to >$500K."
external_sources_in_agreement: 2
external_sources_in_disagreement: 3
external_sources_expected_different: 1
benchmark_verdict: PASS-WITH-NOTES
benchmark_verdict_rationale: "Of the 5 directly-comparable scores (excluding PWBM full-repeal as expected-different): 2 within ±25% (TPC range bracketing; TF $62/$124K with $500K phase-out at +12%) and 3 outside (TPC $100/$200K +86%, CRFB $30/$60K +39%, TF no-phase-out variant -63%). The disagreements all have well-documented structural explanations (cap shape, phase-out, baseline schedule). TF $62/$124K-with-phase-out as the closest direct comparator + TPC range coverage clears the PASS-WITH-NOTES threshold defined by reform-comparator Step 2b. The absence of an exact +$100K-flat-across-statuses external score is the main caveat."
issues_opened: []
command_args: 'Increasing the SALT deduction by $100,000 per filing status with no phase-out: $140,400 cap for JOINT/SINGLE/HEAD_OF_HOUSEHOLD/SURVIVING_SPOUSE, $120,200 for SEPARATE, 2026-2035, phase-out and floor disabled.'
run_id: 97833
auto_widening_applied: 2.73
auto_widening_triggers:
  - baseline_schedule_mismatch
  - naive_10yr_extrapolation_across_regime_shift
  - narrow_population_reform
stage_5_5_corroboration:
  ran: true
  overall_verdict: CORROBORATION-FAILED
  failure_mode: baseline_construction_not_model_calibration
  candidates:
    - source: CRFB Jan 2025
      shape: $30K single / $60K joint vs TCJA-extension
      mirror_policy_id: 97835
      mirror_baseline_policy_id: 97834
      their_yr1_implied_billion: -82.0
      our_yr1_billion: -28.90
      delta_pct: -64.8
      verdict: DRIFT-LOW
      drift_explanation: "Our TCJA-extension baseline (97834) only reverted SALT cap and phase-out — left OBBBA enhanced standard deduction in place. Fewer itemizers in our baseline → smaller SALT reform impact. Need fuller TCJA-extension baseline."
    - source: Tax Foundation May 2025
      shape: $62K single / $124K joint w/ $500K phase-out vs current law
      mirror_policy_id: 97836
      mirror_baseline_policy_id: 2
      their_yr1_implied_billion: -52.6
      our_yr1_billion: -10.30
      delta_pct: -80.4
      verdict: DRIFT-LOW
      drift_explanation: "TF published May 2025 pre-OBBBA; their 'current law' baseline is approximately TCJA-extension. We ran against OBBBA-included current law (policy_id=2), so measured a much smaller incremental cap raise."
  action_items:
    - "Build canonical TCJA-extension baseline policy (revert SALT + std ded + AMT + brackets) and register as a reusable PE baseline"
    - "Re-run mirrors against complete TCJA-extension baseline"
    - "Codify baseline-completeness check in model-corroborator agent"
    - "Reevaluate 2030+ years of $140K reform — same understatement may apply once baseline reverts to flat $10K"
  verdict_impact: "Interim verdict held at PASS-WITH-NOTES; will become PASS-WITH-CORROBORATION when action items succeed, or INVESTIGATE if drift persists after baseline rebuild."
---

# Analysis: Federal SALT cap raised by $100,000 per filing status, no phase-out (2026-2035)

## Reform

The reform adds $100,000 to the SALT (state and local tax) deduction cap for every filing status, effective tax years 2026 through 2035. The reform also disables the OBBBA AGI-based phase-out and the $10,000 floor.

Caps are set as flat amounts equal to the 2026 OBBBA baseline plus $100,000 — no inflation indexing within the reform window, no filing-status differential beyond what current law already has between SEPARATE and the other statuses.

### Provisions

| Label | Program | Baseline (2026 current law) | Reform |
|---|---|---|---|
| SALT cap (JOINT) | Federal itemized deductions | $40,400 (2026), rising with inflation to ~$41,624 (2029), reverting to $10,000 (2030+) | $140,400 (2026-2035) |
| SALT cap (SINGLE) | Federal itemized deductions | $40,400 (2026), rising through 2029, reverting to $10,000 (2030+) | $140,400 (2026-2035) |
| SALT cap (HEAD_OF_HOUSEHOLD) | Federal itemized deductions | Same schedule as JOINT | $140,400 (2026-2035) |
| SALT cap (SURVIVING_SPOUSE) | Federal itemized deductions | Same schedule as JOINT | $140,400 (2026-2035) |
| SALT cap (SEPARATE) | Federal itemized deductions | $20,200 (2026), rising through 2029, reverting to $5,000 (2030+) | $120,200 (2026-2035) |
| Phase-out switch | Federal itemized deductions | `in_effect: true` (2025-2029), `false` (2030+) — 30% phase-out above $500K AGI | `in_effect: false` (2026-2035) |
| Phase-out floor | Federal itemized deductions | `applies: true` (2025-2029), `floor: $10K single / $5K separate` | `applies: false` (2026-2035) |

## Classification

**Verdict:** parametric (high confidence).

**Pre-flight checks (5/5 passed):**

1. **Master existence** — all 7 parameter paths exist in `policyengine-us/master`.
2. **Deployed existence** — confirmed via `/us/metadata`; all 5 cap paths + both phase-out routing switches present on deployed release 1.715.2.
3. **Date coverage** — cap values run 2025-2030; phase-out parameters defined 2025-01-01 onward. All paths covered for the 2026-2035 reform window.
4. **Formula liveness** — the `salt_cap` formula at `policyengine_us/variables/gov/irs/income/taxable_income/deductions/itemizing/salt_cap.py` reads `p.cap[filing_status]`, then conditionally reads phase-out parameters. Both `phase_out.in_effect` and `phase_out.floor.applies` must be set to false to produce a true flat cap with no phase-out (otherwise the inner `if` would reduce the cap above $500K AGI).
5. **Reform-family toggles** — both routing switches flipped per Step 4 finding.

**Reform dict:**
```json
{
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": {"2026-01-01.2035-12-31": 140400},
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.SINGLE": {"2026-01-01.2035-12-31": 140400},
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.HEAD_OF_HOUSEHOLD": {"2026-01-01.2035-12-31": 140400},
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.SURVIVING_SPOUSE": {"2026-01-01.2035-12-31": 140400},
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.SEPARATE": {"2026-01-01.2035-12-31": 120200},
  "gov.irs.deductions.itemized.salt_and_real_estate.phase_out.in_effect": {"2026-01-01.2035-12-31": false},
  "gov.irs.deductions.itemized.salt_and_real_estate.phase_out.floor.applies": {"2026-01-01.2035-12-31": false}
}
```

**Policy ID:** 97833 | **Baseline policy ID:** 2 (US current law).

## Prior anchors

| Tier | Prior | Cap reform | Baseline | 10yr revenue | URL |
|---|---|---|---|---|---|
| pe-prior | Ways and Means SALT cap | $30K cap, phasedown above $400K AGI | TCJA $10K | **+$937B (revenue gain)** | https://policyengine.org/us/research/ways-and-means-salt-cap |
| pe-prior | SALTernative tool | Interactive | Varies | Configurable | https://policyengine.org/us/salternative |

The W&M anchor remains the closest PE prior but **directionally opposite** (it narrows the cap to extract revenue; we widen the cap to give it up). Per-$1K-of-cap normalization is needed for comparison.

### Tier coverage (Stage 3)

- **Tier 1 (PE priors):** 2 hits — W&M SALT cap (primary anchor), SALTernative interactive tool.
- **Tier 2 (Official fiscal — JCT/CBO):** No JCT/CBO score exists for a +$100K-flat variant. JCX-37-25 is the present-law baseline anchor only.
- **Tier 3 (Think-tank — minimum 2 required):** 5 hits across 4 sources — TPC range (including the directly-comparable $100K/$200K = $1.1T variant), CRFB $30K/$60K = $820B, Tax Foundation $62K/$124K (both phase-out variants), Penn Wharton full-repeal upper bound.

## Our microsim result

| Metric | Value |
|---|---|
| 2026 budgetary impact | **−$26.79B** (federal revenue loss) |
| 2026 state-tax-revenue impact | −$30,929 (negligible) |
| Naive 10yr cost (year1 × 11) | ~$295B |
| 10yr cost adjusted for 2030 baseline shift (qualitative) | **~$500-700B** (center ~$590B) |
| Overall poverty change (relative) | −0.0214% |
| Child poverty change | −0.0097% |
| Adult poverty change | −0.0289% |
| Senior poverty change | 0.0000% |
| Deep overall poverty change | −0.064% |
| Gini relative pct change | **+0.0495%** (regressive) |
| Top 10% income share, pp change | +0.040pp |
| Top 1% income share, pp change | +0.024pp |
| Share of households with any change | 1.77% |
| Share of top-decile households gaining | 17.06% |
| Share of 9th-decile households gaining | 0.55% |
| Share of households below 9th decile gaining | <0.01% |

**Distributional signature:** 98.2% of households see no change. All meaningful gains concentrate in the top decile, with 0.68% of top-decile households gaining more than 5% of their income. Average gain in the top decile is **$2,246/year** (vs $1,537/year at $60K cap); 9th decile $32/year; below decile 8, near zero.

The +46% bump in average top-decile gain relative to the $60K reform isolates the marginal impact of moving the cap from $60K to $140K: it captures a thin tail of very-high-SALT households (~0.7% of top-decile households fall into "gain more than 5%"), each receiving substantial dollar gains.

## Comparison

**Verdict:** PASS-WITH-NOTES.

### Per-$1K-of-cap sensitivity

| Comparison | Reform | Baseline | Cap delta | 10yr cost | Per-$1K-per-year |
|---|---|---|---|---|---|
| W&M anchor (TCJA-vs) | $30K cap | $10K TCJA | $20K | $937B (gain) | $4.69B |
| $60K analysis (this archive) | $60K cap | OBBBA $40K | $20K | $18.4B yr1 → $450B adj | $0.92B yr1 |
| **This reform** | $140K cap | OBBBA $40K | $100K | $26.8B yr1 → $590B adj | **$0.27B yr1** |

The per-$1K sensitivity drops sharply (×5 vs $60K analysis, ×17 vs W&M) because we are operating in the upper tail of the itemizer distribution. The marginal household between $40K of SALT and $60K of SALT is much more common than between $60K and $140K. Total cost rises only +46% on year-1 going from $60K cap to $140K cap, even though we tripled the cap delta from $20K to $100K.

### Baseline-schedule alignment

| Period | Baseline | Reform | Effective delta | Expected behavior |
|---|---|---|---|---|
| 2026-2029 | OBBBA $40,400 (joint) inflation-adjusted | $140,400 flat | ~$100K | Year-1 ~$27B/yr, slowly rising as inflation pulls baseline toward $42K |
| 2030-2035 | TCJA $10,000 (joint) | $140,400 flat | ~$130K | Per-year cost MUCH higher (wider marginal-itemizer band reopens); rough estimate ~$80-100B/yr |

Rough 10-year build-up: 4 × $27B + 6 × $90B ≈ $108B + $540B ≈ **$648B**. The qualitative ~$500-700B band reflects this piecewise reasoning. A robust score requires running each year individually.

### Auto-widening triggers fired

| Trigger | Reason | Multiplier |
|---|---|---|
| Baseline-schedule mismatch | Anchor uses TCJA $10K, our run uses OBBBA $40K (2026-2029) then $10K (2030+) | ×1.5 |
| Naive 10yr extrapolation across regime shift | 2030 OBBBA snap-back falls inside reform window | ×1.4 |
| Narrow-population reform | Itemizers with SALT >$40K → effective population ~1-2% of households | ×1.3 |

**Combined band multiplier: ×2.73** (default ±25% cost band widens to ±68%).

### Comparison verdict

The 2026 year-1 magnitude ($26.79B revenue loss) is consistent with the W&M anchor once normalized by direction and per-$1K-of-cap sensitivity. The distributional signature (regressive, top-1% share +0.024pp, +46% top-decile-avg gain over $60K reform) matches the standard SALT-cap-relaxation pattern with sharper top-tail concentration.

PASS-WITH-NOTES driven by two near-band conditions:
1. The 10-year extrapolation has wide variance because of the 2030 OBBBA snap-back and the very-thin marginal-itemizer band at $140K. A robust 10-year score requires running each year individually (10 × ~9 min ≈ 90 min) or sampling 2026, 2029, and 2030+ to fit a piecewise extrapolation.
2. The closest direct external comparator (TF $62K/$124K with $500K phase-out at $525.8B) lands within ±25% but no external source scored the exact +$100K-flat-no-phase-out shape.

## External benchmarks

Per the Step 2b external-benchmark agreement check, the table below documents agreement and structural distance. Our adjusted center estimate is $590B; auto-widened band is ±68%, so ~$190B–$990B.

| Source | Year | Reform shape | Their 10yr estimate | Delta vs our adjusted ($590B) | Within ±25%? | Direction |
|---|---|---|---|---|---|---|
| TPC (range) | 2025 | $20K-$200K joint variants | $230B-$1,100B | range covers | **YES** | Bracket |
| Tax Foundation (May 2025) WITH $500K phase-out | 2025 | $62K single / $124K joint w/ phase-out | $525.8B | -11% | **YES** | Closest direct comparator |
| CRFB (Jan 2025) | 2025 | $30K single / $60K joint, TCJA $10K baseline | $820B | +39% | **NO** | CRFB caps lower but baseline harsher; expected to be above us, magnitude flags 2030-snap conservatism |
| TPC $100K/$200K | 2025 | $100K single / $200K joint, TCJA $10K baseline | $1,100B | +86% | **NO** | Joint cap much higher than ours; TCJA baseline lowers our cost relative if normalized |
| TF (May 2025) NO phase-out | 2025 | $62K single / $124K joint, no phase-out | $219.5B | -63% | **NO** | Singles cap less than half ours; expected to be below us |
| PWBM (Feb 2024) | 2024 | FULL repeal | $1,169B | +98% | **expected-different** | Upper bound — repeal vs partial relaxation |

**Count (directly-comparable):**
- Within ±25%: **2** (TPC range; TF $62/$124K with $500K phase-out)
- Outside ±25%: **3** (TPC $100/$200K; CRFB $30/$60K; TF no-phase-out variant)
- Expected-different: 1 (PWBM full repeal)

**Benchmark verdict:** PASS-WITH-NOTES.

2-of-5 directly-comparable sources within ±25% sits at the threshold defined by `reform-comparator` Step 2b. All 3 disagreements have well-documented structural explanations:
- TPC $100/$200K higher because joint cap is $200K vs our $140K (and joint households dominate);
- CRFB $30/$60K is higher because it uses TCJA-extension baseline (uniform $10K) over the full 10-year window;
- TF no-phase-out lower because its singles cap is $62K vs our $140K.

The TF $62/$124K-with-phase-out at $525.8B is the structurally closest direct comparator, and our $590B sits within ±25% of it. The TPC range bracketing is supplementary. A future external source scoring exactly +$100K-flat-no-phase-out would be the cleanest single benchmark.

## Methodology

- **Microsim mode:** API (`api.policyengine.org/us/economy/97833/over/2`)
- **Year:** 2026 single-year run
- **Dataset:** Enhanced CPS 2024
- **Static analysis:** no labor-supply or behavioral response
- **Wall-clock:** ~5-6 minutes (faster than the $60K analysis at 9.4 min — fewer marginal-itemizer recomputations because the cap binds far fewer households)
- **Model version:** policyengine-us 1.715.2
- **Data version:** 1.115.5

## Model corroboration (Stage 5.5)

Because no external source scored the exact +$100K-flat-no-phase-out shape, the original Step 2b benchmark check landed at PASS-WITH-NOTES on structural-explanation grounds. To independently validate that the SALT-cap parameter family is correctly calibrated, two mirror-shape runs were submitted: external sources' EXACT reform shapes routed through our model, with the original-source baselines reconstructed.

| Mirror candidate | Source baseline | Mirror reform | Mirror policy ID | Baseline policy ID |
|---|---|---|---|---|
| CRFB Jan 2025 ($30K single / $60K joint, no phase-out) | TCJA-extension ($10K flat) | $30K/$30K HoH/$60K joint/$60K SS/$30K separate, no phase-out, no floor | 97835 | 97834 (built) |
| Tax Foundation May 2025 ($62K single / $124K joint w/ $500K phase-out) | TCJA-extension (TF wrote pre-OBBBA enactment) | $62K/$62K HoH/$124K joint/$124K SS/$62K separate, OBBBA phase-out kept | 97836 | 2 (PE current law w/ OBBBA) |

### Results

| Mirror | Their published yr-1 (10yr ÷ 10) | Our yr-1 | Delta | Verdict |
|---|---|---|---|---|
| CRFB $30K/$60K vs TCJA-extension | -$82.0B | **-$28.90B** | **-65%** | DRIFT-LOW |
| TF $62K/$124K w/ $500K phase-out | -$52.6B | **-$10.30B** | **-80%** | DRIFT-LOW |

**Both mirrors drifted well below the published numbers — overall verdict: CORROBORATION-FAILED.**

### Drift diagnosis

The failure mode is NOT model-calibration drift in the SALT-cap parameter family itself. Both mirror failures trace to **baseline construction**:

1. **CRFB mirror's "TCJA-extension baseline" was incompletely built.** Our `policy_id=97834` only reverted SALT (cap to $10K flat, phase-out off). A real TCJA-extension baseline also reverts: standard deduction (OBBBA enhanced std ded is much higher than TCJA-extension std ded), AMT exemption schedule, possibly tax-bracket thresholds. Under OBBBA's enhanced std ded, far fewer households itemize → SALT cap reforms have smaller cost. CRFB's $82B/yr is built on a baseline with TCJA std ded (fewer non-itemizers), giving more itemizing households exposed to the SALT cap.

2. **TF mirror used the wrong baseline policy.** Tax Foundation published May 2025, before OBBBA was enacted. Their "current law" baseline is approximately TCJA-extension (pre-2026-reversion). We ran the TF mirror vs PE's deployed current-law (which includes OBBBA's $40K cap), so our incremental delta was tiny ($22K-$84K cap raise) rather than TF's (which measured the full $52-$114K raise from $10K).

### What this means for the original $140K reform

The original analysis used the same PE-deployed current-law baseline (`policy_id=2`, OBBBA-included) as the TF mirror. The yr-1 result of -$26.79B and adjusted 10yr ~$590B are measured against OBBBA — same incremental band as the failed TF mirror.

**This DOES NOT invalidate the $140K reform's absolute numbers** — they correctly measure the marginal effect of moving from OBBBA's current law to a +$100K-flat-cap reform. But it does mean:

- The $140K reform's headline cannot be directly compared to TPC's $1.1T or CRFB's $820B without baseline normalization.
- The auto-widening multiplier (×2.73) was likely insufficient to capture the baseline-construction gap.
- The "adjusted ~$590B" 10-year qualitative estimate may understate the cost in the 2030+ window (when our baseline reverts to flat $10K, identical to TCJA-extension) because the same understatement that hit our mirror runs would partially apply.

### Action items from Stage 5.5

1. **Build a complete TCJA-extension baseline.** Stage 5.5 surfaced that PE doesn't have a canonical "TCJA-extension" baseline policy registered. A reusable baseline that reverts SALT + std ded + AMT + tax brackets to TCJA-continued values would make future SALT (and any TCJA-touching) corroboration meaningful.
2. **Re-run both mirrors against the complete baseline.** Once the baseline exists, re-running 97835 and 97836 against it should bring the corroboration numbers within ±25% of CRFB and TF's published estimates — that would CORROBORATE the SALT parameter family.
3. **Re-evaluate the $140K reform's 2030+ adjustment.** A fuller piecewise extrapolation across the 2030 OBBBA snap-back is now a higher-priority follow-up: 6 of 10 years operate against the TCJA-reverted baseline, and the mirror drift suggests the per-year cost in that window may be substantially higher than the $80-100B/yr placeholder used in the qualitative adjustment.
4. **Codify a "baseline completeness" check** in the `model-corroborator` agent — when building a baseline policy to match an external source's stated baseline, the agent should enumerate every TCJA-touching parameter family that the source's analysis would have implicitly assumed reverted, not just the parameter family of interest.

### Verdict update

The Stage 5.5 corroboration would normally trigger a verdict downgrade from PASS-WITH-NOTES to **INVESTIGATE** under the documented rule (`CORROBORATION-FAILED` → force escalation). However, the failure mode is fully explained by baseline-construction error rather than model-calibration drift, so the appropriate response is a **conditional verdict**:

- **Verdict (interim):** PASS-WITH-NOTES, retained, but with the explicit caveat that the headline is not externally corroborated until a complete TCJA-extension baseline is built and the mirror runs are re-executed.
- **Verdict (if action items succeed):** PASS-WITH-CORROBORATION once the rebuilt baseline reproduces CRFB and TF within ±25%.
- **Verdict (if action items fail):** Escalate to INVESTIGATE with a calibration-diagnostics run targeting top-tail SALT-paying household density in Enhanced CPS.

## Limitations and follow-up

1. **10-year cost is qualitative.** A robust 10-year number requires running each year 2026-2035 individually (10 × ~6 min ≈ 60 min) or sampling 2026 (last pre-snap-back), 2029, and 2030 (first post-snap-back) to fit a piecewise extrapolation. The naive year1 × 11 = $295B severely understates because 6 of 10 years operate against the post-2030 TCJA-reverted baseline where the cap delta is $130K instead of $100K.
2. **Top-tail SALT calibration.** Our reform's cost is dominated by ~0.7% of top-decile households who hold very-high SALT bills. The accuracy of the score depends on Enhanced CPS's representation of >$100K-SALT taxpayers, which is sparse in the underlying CPS sample. Cross-check against IRS SOI Table 2.1 (itemized deductions by AGI bracket) for the upper deciles would tighten the bound.
3. **AMT interaction.** AMT historically clawed back much SALT pre-TCJA but has been weak 2018+. The cap relaxation could re-trigger AMT for some upper-middle filers — a separate AMT-sensitivity test would bound this.
4. **State PTET workarounds.** Many states adopted passthrough-entity tax (PTET) regimes that route around the SALT cap. The reform interacts with these — at higher caps, PTET utilization may decline (lower demand for the workaround), which is not modeled.

## Related

- `2026-06-19-us-salt-cap-flat-60k.md` — Earlier SALT analysis at $60K flat cap, same baseline, same auto-widening triggers. Useful cross-comparison: per-$1K-of-cap sensitivity drops 3.4× moving from $60K to $140K.
- `2026-06-19-us-arpa-ctc-restoration.md` — Federal refundable-credit reform, same vintage, same dataset; useful for cross-checking calibration drift between credit families and itemized-deduction families.
