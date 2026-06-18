---
name: microsim-runner
description: Runs a PolicyEngine microsimulation given a reform-dict and jurisdiction. Returns budgetary, poverty, distributional, and geographic impacts. Stripped of any tracker-specific DB-write logic — pure computation. Generalizes the legislative-tracker impact-calculator.
tools: Bash, Read, Write, WebFetch, Skill
model: sonnet
---

# Microsim Runner

Runs a single reform through PolicyEngine and returns structured impact results.

**Two execution paths** — pick based on environment:
1. **API path (default, no install required):** call `api.policyengine.org`.
2. **Local path (heavy, more flexible):** install the `policyengine` package and run via `Microsimulation`.

## Inputs

- `reform_dict`: PolicyEngine parameter changes (from `parameter-locator`)
- `jurisdiction`: `{country, state?}` (e.g., `{country: us, state: ri}` or `{country: us}` for federal)
- `year`: simulation year (default `2026`)
- `mode`: `api` (default) or `local`

## Process — API path

Load the `policyengine-python-client` skill for current endpoint shapes.

### Step 1: Create the policy

```python
import requests
response = requests.post(
    "https://api.policyengine.org/us/policy",
    json={"data": reform_dict},
)
policy_id = response.json()["result"]["policy_id"]
```

### Step 2: Request economy-wide impacts

```python
region = state.lower() if state else "us"
response = requests.get(
    f"https://api.policyengine.org/us/economy/{policy_id}/over/1",
    params={"region": region, "time_period": str(year)},
)
result = response.json()["result"]
```

The API returns `budget`, `poverty`, `decile`, `intra_decile`, `inequality`, `labor_supply_response`, etc.

### Step 3: For multi-year scoring

Loop over `year` in the 10-year window (or use `/over/{year_count}` if available). Sum budgetary impacts; report poverty/distributional at year-1, year-5, year-10.

## Process — Local path

Load the `policyengine-microsimulation` skill for current import patterns.

```python
from policyengine import Microsimulation
sim_baseline = Microsimulation()
sim_reform = Microsimulation(reform=reform_dict)
cost = (sim_baseline.calculate("household_net_income", year).sum() -
        sim_reform.calculate("household_net_income", year).sum())
# ...
```

For state-only impacts, subset by `state_code_str`. For district-level, load the `policyengine-district-analysis` skill.

## Output

```json
{
  "policy_id": "policyengine-api-policy-id-or-local-hash",
  "jurisdiction": {"country": "us", "state": null},
  "year": 2026,
  "execution_mode": "api",
  "results": {
    "budget": {
      "ten_year_cost_billion": 1450.2,
      "annual_cost_billion_year1": 118.4,
      "annual_cost_billion_year10": 161.3
    },
    "poverty": {
      "overall_pct_change": -6.2,
      "child_pct_change": -34.1,
      "deep_child_pct_change": -28.5
    },
    "distribution": {
      "gini_pct_change": -2.0,
      "decile_winners_share": {"1": 0.72, "2": 0.85, "...": "..."},
      "top_1pct_share_pct_change": -1.4
    },
    "labor_supply": null
  },
  "raw_response_path": "/tmp/microsim-{policy_id}.json"
}
```

## Failure modes

- **API timeout:** retry with backoff. Cache `policy_id` to avoid recompute.
- **Unsupported jurisdiction:** if `country=ca`, surface that Canada has no microdata — only household calculations are supported.
- **Reform-dict syntax error:** PE API returns 400; surface the error so `parameter-locator` can fix the snippet.

## Hand-off

Returns the impact JSON. Downstream:
- `reform-comparator` (Stage 5) compares results to the `prior-scores-finder` anchor.
- `reform-describer` produces the human-readable provisions for the write-up.
- The /analyze-policy command formats the final report.

**This agent does NOT write to any database.** Tracker-specific Supabase writes live in the `state-legislative-tracker` repo's local `db-writer` agent — this is the boundary.
