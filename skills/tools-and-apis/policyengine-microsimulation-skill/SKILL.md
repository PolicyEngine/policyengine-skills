---
name: policyengine-microsimulation
description: |
  ALWAYS USE THIS SKILL for PolicyEngine microsimulation, population-level analysis, winners/losers calculations.
  Default to policyengine.py (`policyengine.core.Simulation`) for population simulations. Use country-package
  `Microsimulation` classes directly only for low-level country-package debugging or when policyengine.py cannot
  expose the needed behavior.
  Triggers: microsimulation, share who would lose/gain, policy impact, national average, weighted analysis, cost, revenue impact, budgetary, estimate the cost, federal revenues, tax revenue, budget score, how much would it cost, how much would the policy cost, total cost of, aggregate impact, cost to the government, revenue loss, fiscal impact, poverty impact, child poverty, deep poverty, poverty rate, poverty reduction, how many people lifted out of poverty, SPM poverty, distributional impact, state tax, state-level, California, New York, UBI, universal basic income, flat tax, standard deduction, winners and losers, winners, losers, inequality, Gini, decile, SALT, marginal tax rate, effective tax rate.
  NOT for single-household calculations like "what would my benefit be" - use policyengine-us or policyengine-uk for those. Use this skill's code pattern; explore codebase for parameter paths if needed.
---

# PolicyEngine Microsimulation

## Documentation References

- **Microsimulation API**: https://policyengine.github.io/policyengine-us/usage/microsimulation.html
- **Parameter Discovery**: https://policyengine.github.io/policyengine-us/usage/parameter-discovery.html
- **Reform.from_dict()**: https://policyengine.github.io/policyengine-core/usage/reforms.html

## CRITICAL: Default to policyengine.py

For UK and US population analysis, start from the `policyengine` package:

```python
from policyengine.core import Simulation
from policyengine.tax_benefit_models.uk import ensure_datasets, uk_latest
from policyengine.tax_benefit_models.us import ensure_datasets as ensure_us_datasets, us_latest
```

Why this matters:
- `policyengine.py` carries the release-pinned country model and data bundle.
- It avoids accidentally using a local dirty `policyengine_uk`/`policyengine_us` checkout.
- It avoids pulling an arbitrary Hugging Face `main` snapshot when the released bundle already pins data.

Only use `policyengine_uk.Microsimulation` or `policyengine_us.Microsimulation` directly when you are debugging the country package, writing tests inside that repo, or blocked by a missing `policyengine.py` API. If you do that, state the country package version and dataset/HF revision in the result.

## CRITICAL: Use MicroSeries — never strip weights or fetch them manually

**MicroSeries handles all weighting automatically. Never convert to numpy, strip types, or do manual weight math.**

In `policyengine.py`, MicroSeries live in `simulation.output_dataset.data.<entity>["variable"]`. In direct country-package fallback APIs, `calc()`/`calculate()` also return MicroSeries.

### NEVER strip MicroSeries weights

MicroSeries carry embedded weights and entity context. Any of these operations strip both, producing silently wrong results:

| Anti-pattern | Why it's wrong |
|---|---|
| `np.array(series)` | Converts to unweighted numpy array |
| `series.values` / `series.to_numpy()` | Same — strips weights and entity context |
| `series.astype(float)` / `.astype(int)` | Converts MicroSeries to plain pandas Series, losing weight metadata |
| `float(series.sum())` | Premature scalar extraction — usually a sign of manual weight math nearby |
| `np.average(x, weights=w)` | Manual weighting — `.mean()` already does this correctly |

### NEVER fetch weight variables manually

PolicyEngine output columns already know their weights. There is no reason to fetch `household_weight`, `spm_unit_weight`, `person_weight`, or `tax_unit_weight` yourself for weighted statistics. If you are using a country-package fallback and writing `sim.calc("spm_unit_weight", ...)`, something is wrong — `calc()` handles weight mapping internally via the `map_to` parameter.

```python
# ❌ WRONG — fetching weights and doing manual math
liheap = output.spm_unit["dc_liheap_payment"].astype(float)  # strips weights
weights = output.spm_unit["spm_unit_weight"].astype(float)    # unnecessary
total = float((liheap * weights).sum())                              # manual weighting
avg = float(np.average(liheap[liheap > 0], weights=weights[liheap > 0]))  # numpy

# ✅ CORRECT — MicroSeries does everything
liheap = output.spm_unit["dc_liheap_payment"]
total = liheap.sum()                  # Weighted total
avg = liheap[liheap > 0].mean()       # Weighted mean of recipients

# ❌ WRONG — np.array() strips weights AND entity context
change_arr = np.array(output.tax_unit["income_tax"])
weights = np.array(output.household["household_weight"])
# These may be DIFFERENT LENGTHS (tax units vs households)!
losers = weights[change_arr < -1].sum()  # SILENTLY WRONG

# ✅ CORRECT — keep as MicroSeries, all operations are weighted
income_tax_b = baseline.output_dataset.data.tax_unit["income_tax"]
income_tax_r = reformed.output_dataset.data.tax_unit["income_tax"]
tax_change = income_tax_r - income_tax_b
loser_count = (tax_change > 1).sum()    # Weighted count of losers
loser_share = (tax_change > 1).mean()   # Weighted share of losers
avg_change = tax_change.mean()          # Weighted mean change
total_change = tax_change.sum()         # Weighted total
```

### Entity-level matching

When comparing variables across entities, use `map_to` to align them — never mix raw arrays from different entities:

```python
# ❌ WRONG - income_tax is tax_unit level, household_weight is household level
tax = np.array(output.tax_unit["income_tax"])        # tax units
wt = np.array(output.household["household_weight"])  # households
# tax and wt have DIFFERENT lengths — any indexing is wrong

# ✅ CORRECT - map income_tax to household level, or just use MicroSeries
tax = output.tax_unit["income_tax"]  # tax_unit level MicroSeries
losers = (tax > 0).sum()  # Weighted count, correct entity
```

## Quick start

```python
from datetime import datetime
from policyengine.core import Simulation, Policy, ParameterValue
from policyengine.tax_benefit_models.uk import ensure_datasets, uk_latest

YEAR = 2026

datasets = ensure_datasets(years=[YEAR], data_folder="./data")
dataset = datasets[f"enhanced_frs_2023_24_{YEAR}"]

baseline = Simulation(dataset=dataset, tax_benefit_model_version=uk_latest)
baseline.ensure()

param = uk_latest.get_parameter("gov.hmrc.income_tax.allowances.personal_allowance.amount")
policy = Policy(
    name="Personal allowance GBP 15,000",
    parameter_values=[
        ParameterValue(
            parameter=param,
            value=15_000,
            start_date=datetime(YEAR, 1, 1),
        )
    ],
)

reformed = Simulation(
    dataset=dataset,
    tax_benefit_model_version=uk_latest,
    policy=policy,
)
reformed.ensure()

baseline_income = baseline.output_dataset.data.household["household_net_income"]
reformed_income = reformed.output_dataset.data.household["household_net_income"]
change = reformed_income - baseline_income

print(f"Average impact: GBP {change.mean():,.0f}")
print(f"Total cost: GBP {change.sum() / 1e9:,.1f}bn")
print(f"Share losing: {(change < 0).mean():.1%}")
```

## API methods

- **Default: `policyengine.core.Simulation`** - run `simulation.ensure()` and read weighted outputs from `simulation.output_dataset.data.<entity>["variable"]`.
- **UK fallback only: `policyengine_uk.Microsimulation.calculate()`** - use only when working inside/debugging PolicyEngine-UK.
- **US fallback only: `policyengine_us.Microsimulation.calc()`** - use only when working inside/debugging PolicyEngine-US.
- All of these return MicroSeries with automatic weighting. Use `.sum()`, `.mean()`, boolean masks, arithmetic operators, and `groupby`.
- If you use a country-package fallback method, use the `period=` keyword: `sim.calc("variable", period=2026)`, not `sim.calc("variable", 2026)`.

## Creating reforms

### Default: policyengine.py `Policy`

```python
from datetime import datetime
from policyengine.core import Policy, ParameterValue

param = uk_latest.get_parameter("gov.hmrc.income_tax.rates.uk[0].rate")
policy = Policy(
    name="Basic rate 25%",
    parameter_values=[
        ParameterValue(
            parameter=param,
            value=0.25,
            start_date=datetime(2026, 1, 1),
        )
    ],
)

reformed = Simulation(
    dataset=dataset,
    tax_benefit_model_version=uk_latest,
    policy=policy,
)
reformed.ensure()
```

For complex reforms, pass a `simulation_modifier` to `Policy`. The modifier receives the underlying country-model simulation:

```python
from policyengine.core import Policy

def remove_two_child_limit(sim):
    sim.tax_benefit_system.parameters.get_child(
        "gov.dwp.universal_credit.elements.child.limit.child_count"
    ).update(period="year:2026:10", value=float("inf"))
    sim.tax_benefit_system.reset_parameter_caches()

policy = Policy(
    name="Remove UC two-child limit",
    simulation_modifier=remove_two_child_limit,
)
```

### Country-package fallback APIs

Use these only when policyengine.py cannot do the task:

- US fallback: `policyengine_us.Microsimulation` plus `policyengine_core.reforms.Reform.from_dict(...)`
- UK fallback: `policyengine_uk.Microsimulation(reform=dict)`; do not use `Reform.from_dict()` for UK.

## Datasets

### Default: use `ensure_datasets()`

```python
from policyengine.tax_benefit_models.uk import ensure_datasets as ensure_uk_datasets
from policyengine.tax_benefit_models.us import ensure_datasets as ensure_us_datasets

uk = ensure_uk_datasets(
    datasets=["enhanced_frs_2023_24"],
    years=[2026],
    data_folder="./data",
)
efrs = uk["enhanced_frs_2023_24_2026"]

us = ensure_us_datasets(
    datasets=["enhanced_cps_2024"],
    years=[2026],
    data_folder="./data",
)
ecps = us["enhanced_cps_2024_2026"]
```

`ensure_datasets()` returns released, version-aligned datasets for the installed `policyengine` package when you pass logical dataset names such as `enhanced_frs_2023_24` or `enhanced_cps_2024`. Use explicit Hugging Face URLs only when selecting an unmanaged dataset, and include the pinned `@revision` in the URL.

For congressional district analysis, use the `policyengine-district-analysis` skill.

### Memory considerations

State-level datasets are large (~590MB each). Loading two `Simulation` objects simultaneously (baseline + reformed) requires ~2GB+ RAM. Options:
- **Preferred**: Use the national dataset (default) — it includes all states with proper weighting
- **If state-calibrated weights needed**: Compute baseline values first, delete the baseline object (`del baseline`), then create the reformed simulation

## Key MicroSeries Methods

MicroSeries (from [microdf](https://github.com/PolicyEngine/microdf)) handles all weighting automatically — see the `microdf` skill for full documentation.

```python
output = baseline.output_dataset.data
income = output.household["household_net_income"]

# Basic weighted statistics
income.mean()           # Weighted mean
income.sum()            # Weighted sum
income.median()         # Weighted median
(income > 50000).mean() # Weighted share meeting condition

# Inequality metrics (see microdf skill for more)
income.gini()           # Weighted Gini coefficient
```

### Inequality & Distributional Analysis

Use built-in MicroSeries methods — never reimplement Gini or other inequality metrics manually:

**Include the full distribution by default.** PolicyEngine distributional tables
should not drop the bottom 5%, trim nonpositive incomes, or otherwise exclude
income tails unless the user explicitly requests that exclusion or you are
replicating a cited external method. If you do apply an exclusion, make it
visible in the table/chart labels and methodology.

```python
baseline_income = baseline.output_dataset.data.household["household_net_income"]
reformed_income = reformed.output_dataset.data.household["household_net_income"]

# Gini coefficient change
print(f"Baseline Gini: {baseline_income.gini():.4f}")
print(f"Reform Gini:   {reformed_income.gini():.4f}")

# Poverty rate (boolean MicroSeries — .mean() gives weighted rate)
baseline_in_poverty = baseline.output_dataset.data.person["person_in_poverty"]
print(f"SPM poverty rate: {baseline_in_poverty.mean():.1%}")

# Decile-level analysis
income.decile_rank()    # Assign decile ranks (1-10)
```

## Poverty analysis

### Overall and child poverty

Use `household_weight` (the only calibrated weight) with MicroSeries arithmetic for all poverty calculations. No `.values` or `np.sum()` needed.

```python
baseline_out = baseline.output_dataset.data
reform_out = reformed.output_dataset.data

# Overall poverty rate — .mean() gives weighted rate automatically
baseline_in_poverty = baseline_out.person["person_in_poverty"]
reform_in_poverty = reform_out.person["person_in_poverty"]
baseline_poverty_rate = baseline_in_poverty.mean()
reform_poverty_rate = reform_in_poverty.mean()
print(f"Poverty: {baseline_poverty_rate:.1%} -> {reform_poverty_rate:.1%}")

# Child poverty rate — filter by is_child, then .mean()
is_child = baseline_out.person["is_child"]
baseline_child_pov_rate = (baseline_in_poverty * is_child).sum() / is_child.sum()
reform_child_pov_rate = (reform_in_poverty * is_child).sum() / is_child.sum()
print(f"Child poverty: {baseline_child_pov_rate:.1%} -> {reform_child_pov_rate:.1%}")

# People lifted out of poverty
people_lifted = baseline_in_poverty.sum() - reform_in_poverty.sum()
children_lifted = (baseline_child_pov_rate - reform_child_pov_rate) * is_child.sum()
```

> **WARNING: Never subtract boolean MicroSeries directly.** NumPy 2.4+ raises `TypeError` on boolean subtraction (`True - False`). Use `.mean()` to get float rates first, then subtract:
> ```python
> # ❌ DON'T: diff = baseline_in_poverty - reform_in_poverty  # TypeError in numpy 2.4+
> # ✅ DO: compute rates with .mean(), then subtract floats
> baseline_rate = baseline_in_poverty.mean()
> reform_rate = reform_in_poverty.mean()
> reduction_pp = baseline_rate - reform_rate
> ```

### Deep poverty

`in_deep_poverty` is at the SPM unit level. Map it to person level before calculating person-weighted rates:

```python
baseline_in_deep_poverty = baseline_out.map_to_entity(
    source_entity="spm_unit",
    target_entity="person",
    columns=["in_deep_poverty"],
    how="project",
)["in_deep_poverty"]
reform_in_deep_poverty = reform_out.map_to_entity(
    source_entity="spm_unit",
    target_entity="person",
    columns=["in_deep_poverty"],
    how="project",
)["in_deep_poverty"]

baseline_deep_rate = baseline_in_deep_poverty.mean()
reform_deep_rate = reform_in_deep_poverty.mean()
print(f"Deep poverty: {baseline_deep_rate:.1%} -> {reform_deep_rate:.1%}")

# Deep child poverty rate
baseline_deep_child_rate = (baseline_in_deep_poverty * is_child).sum() / is_child.sum()
reform_deep_child_rate = (reform_in_deep_poverty * is_child).sum() / is_child.sum()
print(f"Deep child poverty: {baseline_deep_child_rate:.1%} -> {reform_deep_child_rate:.1%}")
```

### Subgroup analysis note

MicroSeries arithmetic handles subgroup analysis — you should rarely need `.values`. Use boolean MicroSeries masks to filter and use `.sum()` / `.mean()` directly.

## UK microsimulation

### Key differences from US

- **Default API remains policyengine.py**: use `Simulation`, `ensure_datasets()`, and `simulation.output_dataset.data`.
- **UK poverty variables**: `in_poverty_bhc` (before housing costs) and `in_poverty_ahc` (after housing costs) are household-level. UK poverty analysis typically reports both BHC and AHC rates; always note which measure you are using.
- **UK entity structure**: `household`, `benunit` (benefit unit), `person`.
- **Fallback only**: direct `policyengine_uk.Microsimulation` uses `.calculate()`, not `.calc()`, and accepts reform dicts directly.

### Example: UK personal allowance reform with poverty analysis

```python
from datetime import datetime
from policyengine.core import Simulation, Policy, ParameterValue
from policyengine.tax_benefit_models.uk import ensure_datasets, uk_latest

YEAR = 2026
datasets = ensure_datasets(years=[YEAR], data_folder="./data")
dataset = datasets[f"enhanced_frs_2023_24_{YEAR}"]

baseline = Simulation(dataset=dataset, tax_benefit_model_version=uk_latest)
baseline.ensure()

param = uk_latest.get_parameter("gov.hmrc.income_tax.allowances.personal_allowance.amount")
policy = Policy(
    name="Personal allowance GBP 15,000",
    parameter_values=[
        ParameterValue(
            parameter=param,
            value=15_000,
            start_date=datetime(YEAR, 1, 1),
        )
    ],
)
reformed = Simulation(dataset=dataset, tax_benefit_model_version=uk_latest, policy=policy)
reformed.ensure()

baseline_out = baseline.output_dataset.data
reform_out = reformed.output_dataset.data

baseline_income = baseline_out.household["household_net_income"]
reform_income = reform_out.household["household_net_income"]
cost = (reform_income - baseline_income).sum()

# Poverty (BHC) is household-level. Project it to people for person-weighted rates.
baseline_pov_person = baseline_out.map_to_entity(
    source_entity="household",
    target_entity="person",
    columns=["in_poverty_bhc"],
    how="project",
)["in_poverty_bhc"]
reform_pov_person = reform_out.map_to_entity(
    source_entity="household",
    target_entity="person",
    columns=["in_poverty_bhc"],
    how="project",
)["in_poverty_bhc"]

print(f"Cost: GBP {cost / 1e9:,.1f}bn")
print(f"Poverty (BHC): {baseline_pov_person.mean():.1%} -> {reform_pov_person.mean():.1%}")
```

## CRITICAL: Budgetary impact calculation

### Start with a BOTEC range before running code, and flag if the point estimate diverges

### Use `household_net_income` for total cost — but understand what it includes

**The budgetary cost of a reform is the change in `household_net_income`, NOT the change in the
directly-modified program variable.** A reform that changes one program (e.g., CTC) can have
cascading effects on other taxes and benefits through interactions (refundability, phase-outs,
benefit clawbacks). Summing only the program-specific variable will undercount the true cost.

This matches the pattern used in the PolicyEngine API (`policyengine-api/endpoints/economy/compare.py`).

**IMPORTANT: `household_net_income` includes state tax effects.** Many states inherit federal
`taxable_income`, so a federal reform that changes `taxable_income` will indirectly change
state taxes too. For **federal-only** revenue estimates, use `income_tax` directly:

```python
base = baseline.output_dataset.data
ref = reformed.output_dataset.data

# Total cost including state tax interactions
total_cost = (
    ref.household["household_net_income"].sum()
    - base.household["household_net_income"].sum()
) / 1e9

# Federal-only revenue impact (use this when scoring a federal bill)
federal_rev = (
    ref.tax_unit["income_tax"].sum()
    - base.tax_unit["income_tax"].sum()
) / 1e9

# Break out all components
state_tax_cost = (
    base.tax_unit["state_income_tax"].sum()
    - ref.tax_unit["state_income_tax"].sum()
) / 1e9
benefit_cost = (
    ref.household["household_benefits"].sum()
    - base.household["household_benefits"].sum()
) / 1e9

print(f"Total budgetary cost: ${total_cost:,.1f}B")
print(f"Federal income tax revenue change: ${federal_rev:,.1f}B")
print(f"State/local tax revenue loss: ${state_tax_cost:,.1f}B")
print(f"Benefit spending increase: ${benefit_cost:,.1f}B")
```

**Why not sum the program variable directly?** Example: making the CTC fully refundable
shifts credits from non-refundable to refundable, changing `income_tax` by much more than
the `ctc` variable itself changes. The `household_net_income` change captures the full effect.

### Per-program decomposition

Individual program changes are still useful for understanding *where* the cost comes from,
but they don't substitute for the total `household_net_income` cost above.

```python
programs = [
    ("tax_unit", "income_tax"),
    ("tax_unit", "ctc"),
    ("tax_unit", "eitc"),
    ("spm_unit", "snap"),
    ("person", "ssi"),
    ("household", "household_benefits"),
]
for entity, prog in programs:
    b = getattr(base, entity)[prog].sum()
    r = getattr(ref, entity)[prog].sum()
    if abs(r - b) > 1e6:
        print(f"{prog}: ${(r - b) / 1e9:+.1f}B")
```

## Current law context

**Always check baseline parameter values before interpreting reform impacts.** Tax law changes frequently (TCJA, OBBBA, etc.). Use the model version object to look up current-law values:

```python
from policyengine.tax_benefit_models.us import us_latest

param = us_latest.get_parameter("gov.irs.credits.ctc.amount.base[0].amount")
print([(v.start_date, v.end_date, v.value) for v in param.parameter_values[-5:]])
```

## Finding parameter paths

```bash
rg "salt" policyengine_us/parameters/gov/irs/ -g "*.yaml"
```

**Parameter tree:** `gov.irs.deductions`, `gov.irs.credits`, `gov.states.{state}.tax`

**Patterns:** Filing status variants (SINGLE, JOINT, etc.), bracket syntax `[index]`, date format `'YYYY-MM-DD.YYYY-MM-DD'`

### CRITICAL: Bracket path syntax for scale parameters

When referencing bracket/scale parameters, the bracket index goes directly on the scale node — there is NO `.brackets` in the path.

```python
# ✅ Correct — bracket index on the scale node
'gov.irs.credits.ctc.amount.base[0].amount'
'gov.states.ca.tax.income.rates.single[8].rate'
'gov.states.ca.tax.income.rates.single[8].threshold'

# ❌ Wrong — ".brackets" does not exist in the path
'gov.irs.credits.ctc.amount.base.brackets[0].amount'
'gov.states.ca.tax.income.rates.single.brackets[8].rate'
```

The YAML file has a `brackets:` list, but the parameter tree flattens it. The index attaches to the node containing the brackets (the YAML filename without `.yaml`), not to a child called `brackets`.

To verify a path, inspect the parameter tree:
```python
from policyengine.tax_benefit_models.us import us_latest

param = us_latest.get_parameter("gov.irs.credits.ctc.amount.base[0].amount")
print(param.name)
print([(v.start_date, v.end_date, v.value) for v in param.parameter_values[-5:]])
```

### Two types of bracket parameters

1. **ParameterScale** (marginal rate schedules, single YAML with `brackets:` at root):
   - Path: `parent_node.scale_name[index].rate` or `.threshold`
   - Example: `gov.states.ca.tax.income.rates.single[8].rate`

2. **ParameterNode with indexed children** (folder-based, separate YAML files):
   - Path: `node_name[index].child_name`
   - Example: `gov.irs.credits.ctc.amount.base[0].amount`

Both use `[index]` syntax in reform paths — the difference is in the YAML structure. Use `us_latest.get_parameter(...)` or `uk_latest.get_parameter(...)` to navigate and verify paths.

## Complete analysis recipe: single-program impact with breakdowns

This pattern covers the common case of analyzing a single benefit or tax variable with subgroup breakdowns. All operations stay in MicroSeries — no manual weights, no numpy, no `.astype()`.

```python
output = simulation.output_dataset.data

# Output columns are weighted MicroSeries
benefit = output.spm_unit["dc_liheap_payment"]
income_level = output.spm_unit["dc_liheap_income_level"]
unit_size = output.spm_unit["spm_unit_size"]

# Summary stats — .sum() and .mean() are weighted automatically
recipients = (benefit > 0)
print(f"Total spending:  ${benefit.sum():>12,.0f}")
print(f"Recipient units: {recipients.sum():>12,.0f}")
print(f"Avg benefit:     ${benefit[recipients].mean():>12,.0f}")

# Subgroup breakdowns — boolean mask preserves MicroSeries weights
for level in range(1, 11):
    at_level = recipients & (income_level == level)
    if at_level.any():
        print(f"Level {level}: {at_level.sum():,.0f} units, "
              f"avg ${benefit[at_level].mean():,.0f}, "
              f"total ${benefit[at_level].sum():,.0f}")

# Size breakdown (grouped)
for size in [1, 2, 3]:
    mask = recipients & (unit_size == size)
    if mask.any():
        print(f"Size {size}: {mask.sum():,.0f} units, avg ${benefit[mask].mean():,.0f}")
large = recipients & (unit_size >= 4)
if large.any():
    print(f"Size 4+: {large.sum():,.0f} units, avg ${benefit[large].mean():,.0f}")
```

## Common variables for microsimulation

### Weights
- `household_weight` is the calibrated source weight, but you should almost never fetch it directly. PolicyEngine output columns are MicroSeries and already carry the right weights. Use `output.map_to_entity(...)` to align entities instead of doing manual weight math.

### Person-level
- `person_in_poverty` — SPM poverty indicator (boolean)
- `is_child` — under 18
- `age`, `employment_income`

### Household-level
- `household_net_income` — net income after taxes/transfers
- `household_count_people` — number of people in household

### SPM unit-level
- `spm_unit_size`, `spm_unit_count_children`
- `in_poverty`, `in_deep_poverty`

### Tax/benefit variables
- `income_tax`, `ctc`, `eitc`, `snap`, `ssi`
