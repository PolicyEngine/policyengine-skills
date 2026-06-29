---
policy_id: null
date: 2026-06-29
jurisdiction:
  country: us
  state: null
title: CTC filing-status-differential — +$300 per child (non-joint) / +$500 per child (joint)
verdict: structural
verdict_reason: per_child_amount_not_filing_status_indexed
tags:
  - ctc
  - federal
  - structural
  - model-extension
  - filing-status-differential
issues_opened: []
command_args: 'change the ctc by 300 and 500 for joint'
stage_2b_classification: structural
microsim_skipped: true
microsim_skipped_reason: 'Reform requires model extension; no parametric reform-dict can express filing-status-differential per-child CTC amounts.'
---

# Analysis: CTC +$300 (non-joint) / +$500 (joint) per child

## Reform (as requested)

Increase the per-child Child Tax Credit by **$300** for SINGLE, HEAD_OF_HOUSEHOLD, SURVIVING_SPOUSE, and SEPARATE filers, and by **$500** for JOINT filers. Result (per-child, ages 6-17, 2026 vintage):

| Filing status | Baseline CTC | Reform CTC |
|---|---|---|
| SINGLE | $2,200 | $2,500 |
| HEAD_OF_HOUSEHOLD | $2,200 | $2,500 |
| SURVIVING_SPOUSE | $2,200 | $2,500 |
| SEPARATE | $2,200 | $2,500 |
| JOINT | $2,200 | $2,700 |

(2026 baseline uses the post-OBBBA scheduled value of $2,200; current law uprates by $100 every two years per the schedule in `amount/base.yaml`.)

## Classification

**Verdict: `structural`** — the reform cannot be expressed as a parameter override in the deployed PolicyEngine model. A model extension is required.

### Pre-flight findings

1. **Master existence:** `gov.irs.credits.ctc.amount.base` exists, but is structured as an **age-bracketed scalar** (one amount per age range), not a filing-status-indexed amount.
2. **Formula liveness:** the leaf formula at `policyengine_us/variables/gov/irs/credits/ctc/maximum/individual/ctc_child_individual_maximum.py` reads `p.base.calc(age)` — no filing-status branch:

   ```python
   def formula(person, period, parameters):
       age = person("age", period)
       qualifying_child = person("ctc_qualifying_child", period)
       filer_meets_child_ctc_id_requirements = person.tax_unit(
           "filer_meets_child_ctc_identification_requirements", period
       )
       p = parameters(period).gov.irs.credits.ctc.amount
       return (
           qualifying_child * filer_meets_child_ctc_id_requirements * p.base.calc(age)
       )
   ```

   The `p.base.calc(age)` call returns a single amount per child by age. Filing status is not consulted.

3. **YAML structure:** `parameters/gov/irs/credits/ctc/amount/base.yaml` has `brackets:` indexed by `threshold` (age), each with a scalar `amount`. No filing-status dimension exists in the YAML schema.

4. **Phase-out is filing-status-indexed, per-child amount is not.** `gov.irs.credits.ctc.phase_out.threshold` IS filing-status-indexed (`.JOINT`, `.SINGLE`, etc.), reflecting current statute. The per-child amount is intentionally not, because IRC §24 sets a uniform per-child credit irrespective of filing status. The reform proposes a new dimension that does not exist in statute today.

### Model-change estimate

To support this reform parametrically, PolicyEngine-US needs:

**Parameter changes:**
- New parameter family: `gov.irs.credits.ctc.amount.base_by_filing_status/` with `JOINT.yaml`, `SINGLE.yaml`, `HEAD_OF_HOUSEHOLD.yaml`, `SURVIVING_SPOUSE.yaml`, `SEPARATE.yaml` — each with age brackets matching the existing `base.yaml` shape.
- Routing switch: `gov.irs.credits.ctc.amount.filing_status_differential.in_effect` (default `false`) so the existing base parameter remains live for current-law behavior.

**Formula change** in `ctc_child_individual_maximum.py`:
```python
def formula(person, period, parameters):
    age = person("age", period)
    qualifying_child = person("ctc_qualifying_child", period)
    filer_meets_child_ctc_id_requirements = person.tax_unit(
        "filer_meets_child_ctc_identification_requirements", period
    )
    filing_status = person.tax_unit("filing_status", period)
    p = parameters(period).gov.irs.credits.ctc.amount
    base_amount = where(
        p.filing_status_differential.in_effect,
        p.base_by_filing_status[filing_status].calc(age),
        p.base.calc(age),
    )
    return qualifying_child * filer_meets_child_ctc_id_requirements * base_amount
```

**Test coverage required:**
- Per-filing-status integration tests (5 statuses × at least one child age bracket).
- Phase-out interaction test: when a joint household has CTC at $2,700/child and AGI above $400K, the phase-out reduces at $50 per $1,000 — needs verification that the higher base amount flows through the phase-out correctly.
- ARPA-bracket compatibility test: when both `arpa.in_effect=true` and `filing_status_differential.in_effect=true`, the formula stack should not double-count.

**Effort estimate:**
- Code changes: ~30 LOC (formula edit) + ~50 YAML files (5 statuses × multiple inflation rows) + 1 routing switch YAML.
- Test changes: ~6-10 new integration tests.
- Review/CI: 1-2 days.
- Total: **~1 week of one PE-US engineer's time** including model docs update.

## Why this stops here

The `/analyze-policy` pipeline does NOT run a microsim for structural reforms. There is no valid reform-dict that expresses the request; submitting one with the existing parameter paths would silently produce a uniform $300 per-child increase (or a uniform $500 increase) depending on which parameter we picked, NOT the filing-status differential the user asked for. Running a misaligned microsim would produce a plausible-looking number that doesn't actually correspond to the reform — exactly the "silent failure" mode the pipeline is designed to avoid.

The classifier emits this report so the user can:
1. **Revise the reform** to fit the current model — e.g., raise the per-child amount uniformly by some weighted average ($300 × non-joint share + $500 × joint share), or split into separate analyses for two different proposals.
2. **Sponsor the model extension** by opening an issue against `policyengine-us` (auto-routed via the `report-logger` agent when `--auto-investigate` is set).
3. **Use the SALTernative-style interactive tool** (if one exists for CTC) to explore parametric variations within the current model.

## Related (PE priors for CTC reforms)

Tier 1 PE priors that DID run end-to-end (for reference shape comparison):

| Prior | Reform shape | 10yr cost | URL |
|---|---|---|---|
| Restoration of ARPA CTC | Age-bifurcated amount ($3,000 ages 6-17, $3,600 ages 0-5), fully refundable | ~$1,100B | https://policyengine.org/us/research/restoration-of-the-american-rescue-plan-acts-expanded-child-tax-credit |
| American Family Act | Same as ARPA + baby bonus | ~$1,400B | (search PE research catalog) |

None of these existing PE analyses required filing-status-differential per-child amounts — the closest precedent is the age-bifurcated ARPA structure, which is the natural template for adding a new axis to the CTC amount parameter.

## Next action (suggested)

Open an issue in `PolicyEngine/policyengine-us` proposing the model extension above, citing this archive file as the analysis context. Run `/analyze-policy "change the ctc by 300 and 500 for joint" --auto-investigate` if you want the pipeline to auto-file the issue.
