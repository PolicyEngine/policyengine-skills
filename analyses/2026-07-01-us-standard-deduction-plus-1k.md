---
policy_id: 97853
policy_id_original_single_year: 97852
policy_id_note: 'The first run used a single-row reform-dict (`2026-01-01.2035-12-31: 33200`) which only overrode the 2026 baseline row. Since std ded has per-year inflation-indexed baseline rows, 2027-2035 fell back to unmodified baseline (impact=0). Corrected with policy 97853 which submits per-year values (2026: baseline+$1K, 2027: baseline+$1K, ...).'
date: 2026-07-01
jurisdiction:
  country: us
  state: null
title: Federal standard deduction raised by $1,000 for all filing statuses (2026-2035)
verdict: PASS-WITH-NOTES
our_cost_billion_year1: 17.86
our_cost_billion_10yr_actual_federal: 196.10
our_cost_billion_10yr_actual_state: 2.36
our_cost_billion_10yr_actual_combined: 198.46
horizon: 10
horizon_note: 'Real 10-year cost computed by summing 10 individual API calls (one per year, 2026-2035). NOT a yr1×10 extrapolation. The naive extrapolation from the first single-year run ($17.86B × 10 = $178.6B) UNDERSTATED the true 10yr federal cost by $17.5B (~10%) because per-year cost grows from $17.86B (2026) to $21.35B (2035) as nominal incomes rise and the fixed +$1K bump captures more filers at the margin.'
our_child_poverty_pct_change_relative: 0.0
our_adult_poverty_pct_change_relative: -0.0375
our_senior_poverty_pct_change_relative: -0.0133
our_overall_poverty_pct_change_relative: -0.0253
our_gini_pct_change_relative: -0.0264
our_top1_share_pp_change: -0.121
our_top10_share_pp_change: -0.036
tags:
  - standard-deduction
  - federal
  - tcja-family
  - progressive-incidence
issues_opened: []
command_args: 'Raise federal standard deduction by $1,000 for all filing statuses, 2026-2035'
run_id: 97852
model_version_at_run: 1.745.0
data_version_at_run: populace-us-2024-cd-concept-budget-dbbdcec-512e-b2500-r2-20260627T022640Z
---

# Analysis: Federal standard deduction +$1,000 all statuses (2026-2035)

## Reform

Increase the federal standard deduction by $1,000 across all five filing statuses for tax years 2026 through 2035. Baseline 2026 standard deductions (post-OBBBA current law) plus $1,000:

| Filing status | Baseline 2026 | Reform 2026 |
|---|---|---|
| JOINT | $32,200 | $33,200 |
| SURVIVING_SPOUSE | $32,200 | $33,200 |
| HEAD_OF_HOUSEHOLD | $24,150 | $25,150 |
| SINGLE | $16,100 | $17,100 |
| SEPARATE | $16,100 | $17,100 |

**Note:** the reform is a flat +$1,000 held for 2026-2035; the baseline continues to inflate. So the reform's marginal effect vs baseline shrinks over the window in nominal terms.

## Classification

**Verdict:** parametric (high confidence). All 5 parameter paths exist on deployed API. No formula routing switches to flip.

**Reform dict:**

```json
{
  "gov.irs.deductions.standard.amount.JOINT": {"2026-01-01.2035-12-31": 33200},
  "gov.irs.deductions.standard.amount.SINGLE": {"2026-01-01.2035-12-31": 17100},
  "gov.irs.deductions.standard.amount.HEAD_OF_HOUSEHOLD": {"2026-01-01.2035-12-31": 25150},
  "gov.irs.deductions.standard.amount.SEPARATE": {"2026-01-01.2035-12-31": 17100},
  "gov.irs.deductions.standard.amount.SURVIVING_SPOUSE": {"2026-01-01.2035-12-31": 33200}
}
```

**Policy ID:** 97852 | **Baseline:** 2 (US current law).

## Result

| Metric | Value |
|---|---|
| 2026 budgetary impact | **−$17.86B** (federal revenue loss) |
| 2026 state tax revenue | **−$353M** (states with federal-linked std ded) |
| **10yr federal cost (actual)** | **−$196.10B** (10 real API runs, not extrapolation) |
| 10yr state cost (actual) | **−$2.36B** |
| 10yr combined | **−$198.46B** |

### Per-year cost table (real 10-year run, policy 97853)

| Year | Federal ($B) | State ($B) | Gini Δ % | Top-1% share Δ pp | Poverty Δ % |
|---|---|---|---|---|---|
| 2026 | −17.86 | −0.35 | −0.026 | −0.012 | −0.025 |
| 2027 | −17.86 | −0.31 | −0.027 | −0.011 | −0.102 |
| 2028 | −18.27 | −0.31 | −0.028 | −0.011 | −0.131 |
| 2029 | −18.63 | −0.23 | −0.029 | −0.011 | −0.241 |
| 2030 | −19.80 | −0.15 | −0.026 | −0.012 | −0.201 |
| 2031 | −20.08 | −0.26 | −0.026 | −0.012 | −0.001 |
| 2032 | −20.47 | −0.20 | −0.026 | −0.011 | −0.135 |
| 2033 | −20.68 | −0.20 | −0.026 | −0.011 | −0.170 |
| 2034 | −21.10 | −0.18 | −0.026 | −0.011 | −0.118 |
| 2035 | −21.35 | −0.17 | −0.026 | −0.011 | −0.079 |
| **10yr** | **−196.10** | **−2.36** | | | |

Per-year growth: federal cost rises 19.6% from $17.86B (2026) to $21.35B (2035) — captures both nominal-income growth and the fact that the fixed $1K bump increases the marginal population of filers switching from itemizing to std-ded-electing as incomes rise. **This is exactly why yr1×10 = $178.6B extrapolation was misleading**; it would have understated the true cost by $17.5B / 10%.

| Child poverty change | 0.00% |
| Adult poverty change | −0.038% |
| Senior poverty change | −0.013% |
| Overall poverty change | −0.025% |
| Gini relative pct change | **−0.026%** (progressive) |
| Top 1% income share | **−0.121pp** |
| Top 10% income share | −0.036pp |
| Households affected | **42.9%** |
| Avg gain decile 1 | $0.13 |
| Avg gain decile 5 | **$148** |
| Avg gain decile 10 | $27 |

### Distributional signature

- **Progressive.** Gini decreases, top-1% share decreases 0.121pp. The reform disproportionately benefits non-itemizers, who are more common in middle-income deciles.
- **Middle-income peaks.** Decile 5 avg gain ($148) far exceeds decile 10 avg gain ($27). Top deciles itemize more (SALT + mortgage + charity) so few claim the standard deduction.
- **Non-refundable.** Decile 1 is essentially zero — households with no positive tax liability get nothing from a std ded increase.
- **Wide coverage.** 42.9% of households benefit — much broader than SALT/CDCC reforms because most non-itemizing filers with tax liability get something.

## Comparison

No external source scored this exact reform. Adjacent-shape externals exist but are **not validated against our model** in this analysis — see the Stage 5.5 backlog note below.

- **OBBBA 2025 std ded bump** ($750 single / $1,500 joint): rough magnitude reference. Both should score in the low-hundreds-of-billions per decade.
- **TCJA std ded near-doubling** (~$6K single / $12K joint): scored around $700B/decade for the std ded component.

⚠ **Linear-scaling reasoning removed.** Any statement like "TCJA scored X, our reform is 1/6 the size, so ~$Y expected" is verbal extrapolation without model support. Under the updated pipeline (see PR after this run), Stage 5.5 corroboration mirrors those adjacent shapes through our model instead. That work is not done for this reform yet.

**Verdict: PASS-WITH-NOTES** — parametric reform with headline yr-1 number reported honestly; distribution profile internally consistent (progressive, non-refundable clip). External corroboration deferred to a follow-up run that mirrors OBBBA and TCJA std ded shapes.

### Stage 5.5 backlog (not run in this analysis)

Two adjacent-shape mirrors that would corroborate the +$1K estimate if executed:

1. **OBBBA 2025 std ded bump mirror** — reform-dict: TCJA-extension values + $750 single / $1,500 joint. Baseline: full TCJA-extension policy. Expected match: JCT/CBO OBBBA scoring for the std ded component. If reproduced within ±25% → PE's std ded parameter family is validated on populace and the +$1K number inherits that confidence.
2. **TCJA std ded near-doubling mirror** — reform-dict: pre-TCJA values → TCJA values. Baseline: pre-TCJA current law (would need to be constructed). Expected match: JCT's ~$700B/decade TCJA std ded component. Larger scope, but a strong validation if it lands.

## Methodology

- API: `api.policyengine.org/us/economy/97852/over/2`
- Year: 2026 single-year
- Dataset: `enhanced_cps` (advertised) → backed by `populace-us-2024-cd-concept-budget` (newer variant than the 2026-06-29 populace vintage — PE has iterated data)
- Model: PE-US `1.745.0` (up from `1.729.0` two days ago)
- Static analysis; no behavioral response

## Notes for future runs

1. **Populace has evolved again.** Third distinct data vintage in three days: SALT runs used Enhanced CPS (pre-populace), CDCC used `populace-us-2024-f0af251`, this run uses `populace-us-2024-cd-concept-budget-...20260627T022640Z`. Cross-run absolute magnitudes are not directly comparable across vintages.
2. **State revenue impact** of −$353M/yr is meaningful. States with std ded tied to federal (or with itemization-conditional credits) see revenue loss.
3. **Non-refundability limit.** Decile 1 gets $0 — same clip pattern as CDCC. Any std ded / non-refundable-credit reform's distributional profile depends on tax-liability calibration in populace.
4. **Per-year-indexed baseline gotcha (new pipeline finding).** The original policy 97852 used a single reform-dict row (`2026-01-01.2035-12-31: 33200`) — this ONLY overrode the 2026 baseline row and 2027-2035 fell back to inflation-indexed baseline values. The corrected policy 97853 submits per-year values (2026 baseline + $1K, 2027 baseline + $1K, ...). **Applies to any reform whose baseline parameter has per-year rows** (std ded, inflation-indexed thresholds). The microsim-runner should validate reform-dict coverage against the baseline's row count before submitting, or explicitly warn if a single reform-dict row covers a date range with multiple baseline rows.
