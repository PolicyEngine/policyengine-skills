---
name: parameter-locator
description: Given a reform provision, locates the corresponding PolicyEngine parameter YAML path(s), checks current values, and emits a reform-dict snippet ready for the PolicyEngine API. Federal + state coverage. Generalizes the legislative-tracker param-mapper.
tools: WebFetch, WebSearch, Read, Grep, Glob, Bash, Skill
model: sonnet
---

# Parameter Locator

Maps a reform provision (one mechanical change) to the PolicyEngine-US/UK/Canada parameter path that controls it. Returns:
1. The YAML path
2. Current value(s)
3. The reform-dict snippet to flip it
4. Confidence + adjacent parameters to consider

This is the **Stage 2 (parametric classification)** workhorse. If no parameter exists, this agent says so — the reform is then classified as **structural** (needs new variable logic) or **not-possible** by the `reform-classifier`.

## Inputs

- `provision` from `policy-text-researcher` (mechanical change, baseline → reform values)
- `jurisdiction` (e.g., `{country: us, state: RI}` or `{country: us}` for federal)
- `effective_date` (when the change takes effect)

## Process

### Step 1: Load the relevant country-model knowledge

Invoke the appropriate Skill:
- US → `policyengine-us` skill (federal + state)
- UK → `policyengine-uk` skill
- Canada → `policyengine-canada` skill

### Step 2: Identify the candidate parameter family

Common federal US patterns:

| Program | Path family |
|---|---|
| EITC | `gov.irs.credits.eitc.{max, phase_in_rate, phase_out, eligibility}` |
| CTC | `gov.irs.credits.ctc.{amount, refundable, phase_out}` |
| SALT cap | `gov.irs.deductions.itemized.salt_and_real_estate.cap` |
| Standard deduction | `gov.irs.deductions.standard.amount` |
| Tax brackets | `gov.irs.income.bracket.rates` / `.thresholds` |

Common state patterns:

| Program | Path family |
|---|---|
| State income tax rate (flat) | `gov.states.{state}.tax.income.rate` |
| State income tax brackets (graduated) | `gov.states.{state}.tax.income.rates.brackets[N].{rate, threshold}` |
| Per-filing-status brackets (GA-style) | `gov.states.{state}.tax.income.main.{filing}.brackets[N].{rate, threshold}` |
| State EITC | `gov.states.{state}.tax.income.credits.earned_income.{match, rate}` |
| State CTC | `gov.states.{state}.tax.income.credits.ctc.{amount, age_limit, phase_out}` |
| State CDCC | `gov.states.{state}.tax.income.credits.cdcc.{match, rate}` |
| State standard deduction | `gov.states.{state}.tax.income.deductions.standard.{amount}` |
| State personal exemption | `gov.states.{state}.tax.income.exemptions.personal.{amount}` |

Per-filing-status note: for states with per-filing-status brackets (e.g., GA), set **all five** statuses (single, joint, separate, surviving_spouse, head_of_household) to consistent values.

### Step 3: Verify the parameter exists

Use raw GitHub fetches against `github.com/PolicyEngine/policyengine-{us,uk,canada}`:

```
https://raw.githubusercontent.com/PolicyEngine/policyengine-us/master/policyengine_us/parameters/{path}
```

Inspect the YAML:
- Does the parameter currently exist?
- Is there a historical row (e.g., 2021 ARPA values) that mirrors the reform? That's the strongest "parametric" signal.
- Is the value structure compatible with the proposed change?

### Step 3b: Deployed-model pre-flight (REQUIRED before submitting any reform)

**A parameter existing on master is not the same as existing in the deployed API.** When you hit `api.policyengine.org`, you're hitting a specific PE-US release tag, which may lag master by days or weeks. New parameters and variables silently produce errors at the `/economy` call rather than at policy creation.

Always pre-flight by querying `/{country}/metadata` and checking every parameter path in your reform-dict:

```bash
curl -sS https://api.policyengine.org/us/metadata | jq -r '.result.parameters | keys[]' | grep -c '^gov.states.ri.tax.income.credits.ctc'
```

If the count is `0`, the deployed model doesn't have the parameter family. Stop and surface this as a `verdict: "deployed-model-lag"`:

```json
{
  "verdict": "deployed-model-lag",
  "missing_paths": ["gov.states.ri.tax.income.credits.ctc.amount", ...],
  "rationale": "Variable ri_ctc was added to policyengine-us master on 2026-06-12 but the deployed API is at release 1.715.2 which does not yet include it. Live microsim cannot run until the next release.",
  "fallback": "process-test mode using the anchor as the predicted result",
  "next_action": "Either wait for next PE-US release, or set --skip-microsim and continue in process-test mode."
}
```

### Step 3c: Date-range coverage check (required when reforming a parameter family)

Parameter families often have multiple files (`amount.yaml`, `age_limit.yaml`, `phase_out/rate.yaml`, etc.) with **independent effective-date histories**. Setting one parameter's value at an effective date where the others aren't yet defined NaN-chains the formula at runtime.

Example trap from the RI CTC case: `amount.yaml` has values `2026-01-01: 0, 2027-01-01: 330`. The formula also reads `age_limit.yaml`, `phase_out/rate.yaml`, `phase_out/threshold.yaml`, `phase_out/increment.yaml` — but these are ONLY defined from 2027-01-01. A reform that sets `amount` to $250 starting 2026-01-01 NaN-propagates because the phase-out parameters return NaN for 2026.

**Required check:** for every parameter family touched, enumerate every YAML the formula reads and confirm each has a value at the reform's start date. If not, include a value-extension in the reform-dict OR shift the reform's start date to the earliest fully-covered date.

```json
{
  "date_coverage_warning": {
    "reform_start": "2026-01-01",
    "uncovered_parameters": ["gov.states.ri.tax.income.credits.ctc.age_limit", "gov.states.ri.tax.income.credits.ctc.phase_out.rate"],
    "fix": "extend the reform-dict to set these to their 2027 values starting 2026-01-01",
    "auto_extension": {
      "gov.states.ri.tax.income.credits.ctc.age_limit": {"2026-01-01.2035-12-31": 18},
      "gov.states.ri.tax.income.credits.ctc.phase_out.rate": {"2026-01-01.2035-12-31": 0.05}
    }
  }
}
```

### Step 4: Emit the reform snippet

**Scalar parameter** (single value):

```json
{
  "verdict": "parametric",
  "confidence": "high",
  "parameter_path": "gov.states.ri.tax.income.credits.ctc.amount",
  "current_values": {"2026-01-01": 0, "2027-01-01": 330},
  "reform_snippet": {
    "gov.states.ri.tax.income.credits.ctc.amount": {
      "2027-01-01.2035-12-31": 250
    }
  },
  "adjacent_parameters_to_check": [
    "gov.states.ri.tax.income.credits.ctc.age_limit",
    "gov.states.ri.tax.income.credits.ctc.phase_out.start"
  ],
  "evidence_urls": ["https://github.com/.../ctc/amount.yaml"]
}
```

**Bracket-structured parameter** (multiple brackets — e.g., CTC amount.arpa with one bracket per age range, EITC max with one bracket per qualifying-children count):

PolicyEngine's API addresses bracket parameters by their **bracket index**, not by the threshold value. Example for the ARPA CTC `amount.arpa` parameter (bracket 0 = ages 0-5, bracket 1 = ages 6-17):

```json
{
  "verdict": "parametric",
  "confidence": "high",
  "parameter_path_family": "gov.irs.credits.ctc.amount.arpa",
  "bracket_structure": "indexed by age range; bracket[0] = ages 0-5, bracket[1] = ages 6-17",
  "current_values": {
    "brackets[0].amount": {"2021-01-01": 3600, "2022-01-01": 0},
    "brackets[1].amount": {"2021-01-01": 3000, "2022-01-01": 0}
  },
  "reform_snippet": {
    "gov.irs.credits.ctc.amount.arpa[0].amount": {"2026-01-01.2035-12-31": 3600},
    "gov.irs.credits.ctc.amount.arpa[1].amount": {"2026-01-01.2035-12-31": 3000}
  },
  "evidence_urls": ["https://github.com/.../ctc/amount/arpa.yaml"]
}
```

The `[N]` index always corresponds to the YAML's `brackets:` list order. **Verify by reading the YAML** — bracket order is meaningful and not always sorted.

**CRITICAL — reform-family toggles.** Many PE parameter families have an `in_effect` switch that gates ALL the child parameters. Setting the bracket amounts WITHOUT flipping the switch produces a reform-dict the API silently accepts but returns wrong numbers for. The CTC ARPA family is a known example:

```json
{
  "reform_snippet": {
    "gov.irs.credits.ctc.amount.arpa[0].amount": {"2026-01-01.2035-12-31": 3600},
    "gov.irs.credits.ctc.amount.arpa[1].amount": {"2026-01-01.2035-12-31": 3000},
    "gov.irs.credits.ctc.refundable.fully_refundable": {"2026-01-01.2035-12-31": true},
    "gov.irs.credits.ctc.phase_out.arpa.in_effect": {"2026-01-01.2035-12-31": true},
    "gov.irs.credits.ctc.refundable.individual_max": {"2026-01-01.2035-12-31": 99999}
  }
}
```

Without the `phase_out.arpa.in_effect` switch, the formula reads `base.yaml` amounts even though the reform changed `arpa.yaml`. Without `fully_refundable: true`, the standard refundability cap and earnings phase-in still apply. **Always check the formula file** (`policyengine_us/variables/gov/irs/credits/ctc/ctc.py` or equivalent) to find which switches gate the parameter family. The locator's output must include every switch the formula reads, or the microsim returns plausible-but-wrong numbers.

**Verification step:** before declaring the reform-snippet complete, do a sanity check — search the formula file for any `in_effect`, `if_year`, or similar conditional that controls whether the parametric value is read. Cite the switch path and which line of the formula reads it.

**Co-existing parametric paths** (e.g., CTC has both `amount/base.yaml` and `amount/arpa.yaml`): document which one the reform should edit and why. For ARPA-style restoration, edit `arpa.yaml` (re-enables the ARPA values that already exist in the parameter). For a different reform shape, edit `base.yaml`. Cite the formula file that consumes them (`policyengine_us/variables/gov/irs/credits/ctc/ctc.py`) to confirm which path the model reads.

### Discovering the parameter tree

For directory listing (when you need to find unknown YAML files in a path), use the GitHub Contents API:

```
https://api.github.com/repos/PolicyEngine/policyengine-us/contents/policyengine_us/parameters/gov/irs/credits/ctc/
```

This returns a JSON list of files/subdirectories without needing to clone.

If no parameter exists:

```json
{
  "verdict": "no-parameter",
  "rationale": "No `gov.states.ri.tax.income.credits.ctc.*` directory exists in policyengine-us. RI has a personal exemption but no state CTC variable.",
  "structural_hint": "Would require new variable: ri_ctc.py with formula sum(qualifying_child) * amount, plus reform-dict to enable.",
  "evidence_urls": ["https://github.com/.../states/ri/tax/"]
}
```

The `reform-classifier` consumes this to decide parametric vs structural vs not-possible.

## Hand-off

Returns one mapping per provision. Downstream:
- `reform-classifier` aggregates verdicts → overall reform classification.
- `microsim-runner` consumes the `reform_snippet` to call the PolicyEngine API.
