---
name: policyengine-district-analysis
description: Analyze policy impacts for congressional districts and representatives' constituents. Use when the user mentions a specific district (NY-17, CA-52), a representative's name, or asks about geographic policy impacts at district level. Provides HuggingFace district datasets.
---

# Congressional District Policy Analysis

## Documentation References

- **Microsimulation API**: https://policyengine.github.io/policyengine-us/usage/microsimulation.html
- **Parameter Discovery**: https://policyengine.github.io/policyengine-us/usage/parameter-discovery.html

## CRITICAL: Use policyengine.py and MicroSeries - No Manual Weights Ever

**MicroSeries handles all weighting automatically. Use `policyengine.core.Simulation`; never access `.weights`, `.values`, or do manual weight math.**

```python
# ✅ CORRECT
base = baseline.output_dataset.data
ref = reformed.output_dataset.data
baseline_income = base.map_to_entity(
    source_entity="household",
    target_entity="person",
    columns=["household_net_income"],
    how="project",
)["household_net_income"]
reformed_income = ref.map_to_entity(
    source_entity="household",
    target_entity="person",
    columns=["household_net_income"],
    how="project",
)["household_net_income"]
change = reformed_income - baseline_income
loser_share = (change < 0).mean()  # Weighted automatically!

# ❌ WRONG
loser_share = change.weights[change.values < 0].sum() / change.weights.sum()
```

## Complete Example

```python
from datetime import datetime
from policyengine.core import Simulation, Policy, ParameterValue
from policyengine.provenance.manifest import resolve_region_dataset_path
from policyengine.tax_benefit_models.us import ensure_datasets, us_latest

# 1. Load district data
# IMPORTANT: Single-digit districts need zero-padding (CT-01, not CT-1)
district = "NY-17"  # Mike Lawler's district
district_dataset = resolve_region_dataset_path(
    "us",
    "congressional_district",
    district_code=district,
)
datasets = ensure_datasets(datasets=[district_dataset], years=[2026], data_folder="./data")
dataset = datasets[f"{district}_2026"]

baseline = Simulation(dataset=dataset, tax_benefit_model_version=us_latest)
baseline.ensure()

# 2. Define reform
salt_caps = {
    "gov.irs.deductions.itemized.salt_and_real_estate.cap.SINGLE": 10_000,
    "gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": 10_000,
    "gov.irs.deductions.itemized.salt_and_real_estate.cap.SEPARATE": 5_000,
    "gov.irs.deductions.itemized.salt_and_real_estate.cap.HEAD_OF_HOUSEHOLD": 10_000,
    "gov.irs.deductions.itemized.salt_and_real_estate.cap.SURVIVING_SPOUSE": 10_000,
}
policy = Policy(
    name="SALT cap",
    parameter_values=[
        ParameterValue(
            parameter=us_latest.get_parameter(path),
            value=value,
            start_date=datetime(2026, 1, 1),
        )
        for path, value in salt_caps.items()
    ],
)

reformed = Simulation(dataset=dataset, tax_benefit_model_version=us_latest, policy=policy)
reformed.ensure()

# 3. Calculate impact - MicroSeries handles weights automatically.
base = baseline.output_dataset.data
ref = reformed.output_dataset.data
baseline_income = base.map_to_entity(
    source_entity="household",
    target_entity="person",
    columns=["household_net_income"],
    how="project",
)["household_net_income"]
reformed_income = ref.map_to_entity(
    source_entity="household",
    target_entity="person",
    columns=["household_net_income"],
    how="project",
)["household_net_income"]
person_change = reformed_income - baseline_income
household_change = ref.household["household_net_income"] - base.household["household_net_income"]

# 4. Results - no manual weight math needed
print(f"Share losing: {(person_change < 0).mean():.1%}")
print(f"Average person impact: ${person_change.mean():,.0f}")
print(f"Total household impact: ${household_change.sum()/1e6:,.1f}M")
```

## Compare to National

```python
national_datasets = ensure_datasets(
    datasets=["enhanced_cps_2024"],
    years=[2026],
    data_folder="./data",
)
national_dataset = national_datasets["enhanced_cps_2024_2026"]

national_baseline = Simulation(dataset=national_dataset, tax_benefit_model_version=us_latest)
national_reformed = Simulation(
    dataset=national_dataset,
    tax_benefit_model_version=us_latest,
    policy=policy,
)
national_baseline.ensure()
national_reformed.ensure()

national_base = national_baseline.output_dataset.data
national_ref = national_reformed.output_dataset.data
national_change = (
    national_ref.map_to_entity(
        source_entity="household",
        target_entity="person",
        columns=["household_net_income"],
        how="project",
    )["household_net_income"]
    - national_base.map_to_entity(
        source_entity="household",
        target_entity="person",
        columns=["household_net_income"],
        how="project",
    )["household_net_income"]
)

print(f"District: {(person_change < 0).mean():.1%} lose")
print(f"National: {(national_change < 0).mean():.1%} lose")
```
