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
2. **Local path (heavy, more flexible):** install the `policyengine` package (latest, `>=5.0.1`) and run through its managed `pe.{us,uk}` surfaces (see "Process — Local path").

## Inputs

- `reform_dict`: PolicyEngine parameter changes (from `parameter-locator`)
- `jurisdiction`: `{country, state?}` (e.g., `{country: us, state: ri}`, `{country: us}` for federal, or `{country: uk}`)
- `year`: simulation year (default `2026`)
- `mode`: `api` (default) or `local`
- `dataset` (optional): a dataset name from policyengine.py's bundle, such as `populace_us_2024_acs_local` or `enhanced_frs_2024_25`. Omit it to run the certified default. The API runs only the default, so take the local path for a named `dataset`, whatever `mode` says, and record `execution_mode: "local"` in the output.

## Process — API path

Load the `policyengine-api` skill for the v1 routes.

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

**Critical:** the URL is `/economy/{reform_policy_id}/over/{baseline_policy_id}`, and the baseline ID must be the country's current-law ID. The `over/{N}` segment is the **baseline policy ID** to diff against, not a year count. Common baseline IDs:

| Country | Current-law baseline policy_id |
|---|---|
| US | `2` |
| UK | `1` (`current_law_id` in `/uk/metadata`) |

A baseline ID other than the country's current-law ID usually returns a misleading parse error or computes against a stale baseline. Always use the documented current-law baseline.

```python
region = state.lower() if state else "us"
baseline_id = 2  # US current law — verify
url = f"https://api.policyengine.org/us/economy/{policy_id}/over/{baseline_id}"
response = requests.get(url, params={
    "region": region,
    "time_period": str(year),
})
```

The annual route takes `region` and `time_period`, plus optional `version` (the country model version), `target` (`general` or `cliff`), `spm` (a JSON-encoded SPM selection) and, for UK runs only, `breakdown`. policyengine-api answers HTTP 400 to any other query parameter, so a request that sends `dataset` gets "dataset: Extra inputs are not permitted". The API builds every economy request with `dataset="default"` and runs it on the one dataset `/{country}/metadata` lists under `economy_options.datasets`. On 2026-11-08 the US entry named Microcosm's `populace_us_2024` at data version `populace-us-2024-spm-20260915`, and the UK entry named Microcosm's `microcosm_uk_2024_25`. To run a reform on another dataset, take the local path.

For a UK run, call the same routes under `/uk/` with `region=uk` and baseline policy `1`. The dataset check below applies to both countries.

### Dataset check (REQUIRED)

After the run completes, name the dataset and data version behind it and check them against the default that `/{country}/metadata` lists. The result's `policyengine_bundle` reports what the simulation loaded: its `dataset` holds that file's `hf://` URI or `default`, and its `data_version` holds the release. `run_dataset` turns the URI into the dataset's name the way policyengine.py's `dataset_logical_name` does. When the bundle reads `default` or names no dataset, the function takes the name from the metadata's default entry. When the bundle leaves `data_version` empty, it reads the release from the URI's `@` revision, or from the default entry for a run on the default dataset.

```python
from pathlib import PurePosixPath


def run_dataset(bundle, datasets):
    """Return the dataset and data version behind an economy result.

    bundle: the result's `policyengine_bundle`; None for a budget-window result.
    datasets: `economy_options.datasets` from /{country}/metadata.
    """
    default = next(entry for entry in datasets if entry.get("default"))
    bundle = bundle or {}
    uri = bundle.get("dataset") or "default"
    if uri == "default":
        name = default["name"]
    else:
        name = PurePosixPath(uri.rsplit("@", 1)[0]).stem
    pinned = uri.rsplit("@", 1)[1] if "@" in uri else None
    data_version = bundle.get("data_version") or pinned
    if not data_version and name == default["name"]:
        data_version = default["data_version"]
    return {
        "dataset": name,
        "data_version": data_version,
        "dataset_matches_default": (name, data_version)
        == (default["name"], default["data_version"]),
    }
```

Fetch the metadata once per run and record the check with the model version:

```python
metadata = requests.get(f"https://api.policyengine.org/{country}/metadata").json()["result"]
result = response.json()["result"]
check = run_dataset(result.get("policyengine_bundle"), metadata["economy_options"]["datasets"])
model_version = result.get("model_version") or metadata["version"]
```

If `dataset_matches_default` comes back false, the bundle names a dataset or data release other than the default the API lists now. Record the bundle's values, since they name what the run loaded, and the comparator flags the run.

**Polling:** the response starts with `status: "computing"` and carries stage fields (`stage`, `progress`, `progress_max`, `segments`) while the job runs. Wait 30s and retry. A failed run answers HTTP 502 with `status: "error"` and a `message`. Real-world wall-clock for a US economy-wide reform is **5-10 minutes**, not 1-3 minutes as some older docs suggest. Retry up to ~20 minutes before giving up.

### Reform-dict row coverage pre-flight (REQUIRED before submission)

**The `.` (dot) separator in a reform-dict date-range key does NOT sweep forward through the baseline's later rows.** A key like `"2026-01-01.2035-12-31": 33200` inserts a single value at 2026-01-01 with an end date at 2035-12-31 — but if the baseline has intermediate rows (2027-01-01, 2028-01-01, ...), those take precedence for their respective years and the reform is silently a no-op for years 2027+.

**This is exactly what happened to the std-ded +$1K reform on 2026-07-01.** Policy 97852 used `{"2026-01-01.2035-12-31": 33200}` for each filing status. The 2026 result was correct (−$17.86B), but 2027-2035 all reported budgetary_impact=0 because the baseline had inflation-indexed per-year rows the reform-dict didn't override. Policy 97853 fixed it with per-year values.

**Required pre-flight** — before submitting any policy:

1. Fetch the baseline parameter's `values` object via `/{country}/metadata` for every parameter path in the reform-dict.
2. For each parameter path, count the number of baseline rows falling inside the reform's date range.
3. If a single reform-dict row covers a date range where the baseline has >1 row, emit:

```json
{
  "warning": "reform_dict_row_coverage_mismatch",
  "parameter_path": "gov.irs.deductions.standard.amount.JOINT",
  "reform_dict_rows_in_range": 1,
  "baseline_rows_in_range": 10,
  "baseline_row_years": [2026, 2027, 2028, ..., 2035],
  "risk": "reform will only override year 2026; years 2027+ will fall back to inflation-indexed baseline values",
  "suggested_fix": "expand reform-dict to per-year values: {2026-01-01.2026-12-31: X_2026, 2027-01-01.2027-12-31: X_2027, ...}",
  "auto_expand_available": true
}
```

4. If `--auto-expand` (or the agent has authority): rewrite the reform-dict to per-year values. Compute reform value per year as `baseline[year] + delta`, where `delta` is inferred from the (single row value) − (baseline at row start date).
5. If not auto-expanding: refuse to submit the run and surface the warning to the analyst.

**Applies to any inflation-indexed parameter family**: standard deduction, tax brackets, EITC amounts, CTC amounts, phase-out thresholds. Does NOT apply to parameters with only 1-2 baseline rows in the reform window (like SALT cap under OBBBA, which has 2026 + 2030 rows only — a single reform-dict row `"2026-01-01.2035-12-31": 60000` correctly overrides both).

### Multi-year runs (horizon > 1) — use the budget-window endpoint

The API provides a native multi-year endpoint that queues all years server-side with progress tracking. **Prefer it over N parallel single-year calls** — it's simpler to poll, gives a unified response shape, and doesn't rely on client-side parallel orchestration.

```
GET /{country}/economy/{policy_id}/over/{baseline_id}/budget-window
    ?region={region}
    &start_year=YYYY
    &window_size=N
```

It also takes the annual route's optional `version` and `spm`, and it answers HTTP 400 to `dataset` as the annual route does.

Response while computing:

```json
{
  "status": "computing",
  "message": "Scoring 2029 (3 of 10 complete)...",
  "result": null,
  "progress": 30,
  "completed_years": ["2026", "2027", "2028"],
  "computing_years": ["2029"],
  "queued_years": ["2030", "2031", "2032", "2033", "2034", "2035"],
  "error": null
}
```

When `status: "ok"`, `result` holds `kind: "budgetWindow"`, `startYear`, `endYear`, `windowSize`, one `annualImpacts` row per year and a `totals` row. Each row carries `budgetaryImpact`, `taxRevenueImpact`, `federalTaxRevenueImpact`, `stateTaxRevenueImpact` and `benefitSpendingImpact` in dollars. The result carries no `policyengine_bundle` or `model_version`. Call `run_dataset(None, datasets)` to take the dataset and data version from the metadata default, and take `model_version` from `/{country}/metadata`'s `version`.

**Polling cadence:** the endpoint returns quickly; poll every 30-60s while `status == "computing"`. Wall-clock for a full 10-year US run is typically 15-25 min (depends on API queue).

**Fallback:** if the budget-window run fails (`status: "error"`, or an HTTP 502), fall back to N parallel calls to the single-year endpoint. Log the fallback so the analyst knows the runner degraded gracefully.

```python
def run_horizon(country, region, policy_id, baseline_id, start_year, window_size):
    url = (
        f"https://api.policyengine.org/{country}/economy/{policy_id}/over/{baseline_id}/budget-window"
        f"?region={region}&start_year={start_year}&window_size={window_size}"
    )
    while True:
        r = requests.get(url).json()
        if r["status"] == "ok":
            return r["result"]
        if r["status"] != "computing":
            raise RuntimeError(r.get("error") or r.get("message"))
        time.sleep(60)
```

**Do NOT compute a naive `yr1 × N` extrapolation.** If the horizon is `1`, report yr-1 cost only in the archive. If the horizon is `10` (or a custom multi-year list), use the budget-window endpoint and report the actual per-year cost table AND the summed multi-year cost.

### Step 2b: Real response shape

The API returns **raw baseline and reform LEVELS**, not deltas. The agent must compute deltas itself. Top-level keys (representative):

```json
{
  "status": "ok",
  "message": null,
  "result": {
    "model_version": "2.2.1",
    "data_version": "populace-us-2024-spm-20260915",
    "policyengine_bundle": {
      "model_version": "2.2.1",
      "policyengine_version": "6.16.0",
      "data_version": "populace-us-2024-spm-20260915",
      "dataset": "hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-spm-20260915",
      ...
    },
    "budget": {
      "budgetary_impact": ...,
      "tax_revenue_impact": ...,
      "state_tax_revenue_impact": ...,
      "benefit_spending_impact": ...,
      "households": ...,
      "baseline_net_income": ...
    },
    "poverty": {
      "poverty": {
        "all": {"baseline": 0.124, "reform": 0.118},
        "adult": {...},
        "child": {"baseline": 0.143, "reform": 0.094},
        "senior": {...}
      },
      "deep_poverty": {...}
    },
    "inequality": {
      "gini": {"baseline": 0.4123, "reform": 0.4042},
      "top_1_pct_share": {"baseline": ..., "reform": ...},
      "top_10_pct_share": {"baseline": ..., "reform": ...}
    },
    "decile": {...},
    "intra_decile": {...},
    "labor_supply_response": null
  }
}
```

**Compute deltas:**
- `child_poverty_pct_change = (reform - baseline) / baseline * 100`
- `adult_poverty_pct_change = (reform - baseline) / baseline * 100` — required since some reforms move adult-only poverty (childless EITC, SALT)
- `senior_poverty_pct_change = (reform - baseline) / baseline * 100` — **required** since reforms that touch age-eligibility (ARPA EITC age-cap removal) move senior poverty more than child or overall; the EITC live test showed senior -5.4% while child was 0.0%
- `gini_pct_change = (reform_gini - baseline_gini) / baseline_gini * 100`
- `annual_cost_billion = -budgetary_impact / 1e9` (sign convention: negative budgetary_impact means revenue loss / spending → positive cost)

**Surface unusual-bucket signals.** If `senior_poverty_pct_change` is more than 2× `overall_poverty_pct_change` (or vice versa for child), include a `headline_metric_note` in the output flagging which sub-bucket is driving the result. This catches age-targeted reforms whose effect would otherwise be invisible in the "overall poverty" headline.

### Step 3: For multi-year scoring

The horizon prompt in `/analyze-policy` (see Phase 0) sets the number of years, and the budget-window endpoint above scores them in one request.

**Naive `yr1 × N` extrapolation is banned.** It silently misstates 10-year totals whenever the baseline evolves over the window (inflation-indexed thresholds, 2030 OBBBA snap-back, phase-out schedules, TCJA-style sunsets). Empirical case from 2026-07-01 std-ded +$1K: yr1×10 = $178.6B understated the real 10-year cost ($196.10B) by 10%. If the analyst asks for a single year, the archive reports one year — no fabricated 10-year total.

For a 10-year cost, call `run_horizon(country, region, policy_id, baseline_id, start_year=2026, window_size=10)` and report its `annualImpacts` rows and `totals`.

## Process — Local path

<!-- stale-ok -->
Load the `policyengine` skill for current import patterns and certified dataset names. The canonical local entry point is the top-level `policyengine` package (latest, `>=5.0.1`) pinned to the certified Microcosm bundle — **never** `from policyengine_us import Microsimulation` (unmanaged; deprecated for analysis) or a bare `from policyengine import Microsimulation` (that class does not exist).

Baseline-vs-reform economy analysis (budget, poverty, deciles, inequality in one pass):

```python
import policyengine as pe
from policyengine.core import Simulation

loaded = pe.us.ensure_datasets(
    datasets=[dataset] if dataset else None,  # None loads the certified default
    years=[year],
    data_folder="./data",
)
data = next(iter(loaded.values()))
baseline = Simulation(dataset=data, tax_benefit_model_version=pe.us.model)
reform = Simulation(dataset=data, tax_benefit_model_version=pe.us.model, policy=reform_dict)
analysis = pe.us.economic_impact_analysis(baseline, reform)  # deciles, poverty, inequality
budget = pe.us.calculate_budgetary_impact(baseline, reform)  # total / federal / state split
```

`Simulation(policy=reform_dict)` takes the same flat reform dict as the API path. Call `economic_impact_analysis` before any manual `ensure()` — it configures the output variables both simulations need. policyengine.py 6.16.0's US bundle serves two datasets by name: the certified default `populace_us_2024` and `populace_us_2024_acs_local`.

For a UK run, follow the same pattern with `pe.uk`, which has `economic_impact_analysis` but no `calculate_budgetary_impact`, and whose analysis result carries no budget total. Take a UK run's cost from policyengine-uk's household `gov_balance`, which adds `gov_tax` and subtracts `gov_spending`. pe.uk's default outputs leave it out, so pass `extra_variables={"household": ["gov_balance"]}` to both `Simulation`s. The reform's weighted total minus the baseline's gives the change in the government's balance, and `annual_cost_billion_year1` takes the opposite sign, in £ billions. `pe.uk.ensure_datasets(years=[year])` loads the certified default, Microcosm's `microcosm_uk_2024_25`, from a private Hugging Face repo, so set `HUGGING_FACE_TOKEN`. When the caller names a dataset, load it by name: `pe.uk.ensure_datasets(datasets=[dataset], years=[year])`. policyengine.py serves the Enhanced FRS and FRS files that policyengine-uk-data builds (`enhanced_frs_2024_25`, `frs_2024_25`, and their 2023-24 and `_tiny` siblings) only by name, from the `dataset_overlays` in its bundle manifest. It downloads them from the gated `policyengine/policyengine-uk-data-private` repo, so the token also needs access there. Say in the result that a run on one of them left the certified default.

Record the dataset the run used and its version for the output, in either country:

```python
from policyengine.provenance.manifest import dataset_logical_name, resolve_managed_dataset_reference

uri = resolve_managed_dataset_reference(country, dataset)  # dataset=None gives the certified default
dataset_name = dataset_logical_name(uri)  # e.g. "microcosm_uk_2024_25"
data_version = uri.rsplit("@", 1)[1]  # the revision the bundle pins
```

For the analyst MicroSeries surface (weighted `.calc()` on the certified default `populace_us_2024`):

```python
import policyengine as pe

sim = pe.us.managed_microsimulation()                       # certified default dataset
sim.calc("household_net_income", period=year).sum()         # US: .calc(); UK: .calculate()
```

For state- or district-level impacts, load `populace_us_2024_acs_local` **by name** and scope a `Simulation` with `RowFilterStrategy(variable_name="state_fips", ...)` from `policyengine.core.scoping_strategy` — never a per-state or per-district H5 file (policyengine.py's bundle serves none, and PolicyEngine archived `policyengine-us-data`). See the `policyengine` skill's regional-analysis section.

## Output

The agent normalizes the raw API response into this canonical shape. **Always include the raw response path** so downstream agents can re-check the source levels.

```json
{
  "policy_id": "97748",
  "baseline_policy_id": "2",
  "jurisdiction": {"country": "us", "state": null},
  "year": 2026,
  "execution_mode": "api",
  "dataset": "populace_us_2024",
  "data_version": "populace-us-2024-spm-20260915",
  "dataset_matches_default": true,
  "model_version": "2.2.1",
  "wall_clock_seconds": 480,
  "results": {
    "budget": {
      "annual_cost_billion_year1": 86.6,
      "ten_year_cost_billion_actual": null,
      "ten_year_cost_billion_actual_note": "null unless horizon > 1; naive yr1×N extrapolation is banned"
    },
    "years_run": [2026],
    "per_year_budget_billion": {"2026": 86.6},
    "poverty": {
      "overall_baseline": 0.124, "overall_reform": 0.118, "overall_pct_change": -4.8,
      "child_baseline": 0.143, "child_reform": 0.094, "child_pct_change": -34.3,
      "adult_baseline": 0.108, "adult_reform": 0.105, "adult_pct_change": -2.8,
      "senior_baseline": 0.092, "senior_reform": 0.087, "senior_pct_change": -5.4,
      "deep_child_baseline": ..., "deep_child_reform": ..., "deep_child_pct_change": ...
    },
    "distribution": {
      "gini_baseline": 0.4123, "gini_reform": 0.4042, "gini_pct_change_relative": -2.0, "gini_pp_change_absolute": -0.81,
      "top_1pct_share_baseline": ..., "top_1pct_share_reform": ..., "top_1pct_share_change_absolute": -0.5
    },
    "labor_supply": null
  },
  "raw_response_path": "/tmp/microsim-{policy_id}.json"
}
```

**`dataset` and `data_version`** name the dataset that backed the run and its version. /analyze-policy records them in the archive's frontmatter as `dataset_at_run` and `data_version_at_run`, and report-logger routes a UK data issue by the dataset. On the API path, the dataset check in "Process — API path" reads both from `response.json()["result"]["policyengine_bundle"]` and fills any gap from `/{country}/metadata` under `economy_options.datasets`. A budget-window result carries no bundle, so both values come from the metadata's default entry. On the local path, compute them as "Process — Local path" shows. `model_version` comes from the result's `model_version`, or from `/{country}/metadata`'s `version` for a budget-window run.

**Sign conventions:**
- `annual_cost_billion`: positive = revenue/spending COST to government (reform makes the gov spend more or collect less). For a cap repeal like SALT, this is a positive number (revenue loss to gov).
- `gini_pct_change_relative` (e.g., -2.0%): change relative to baseline Gini. Use this for comparison to published PE scores, which typically report relative change.
- `gini_pp_change_absolute` (e.g., -0.81pp): absolute percentage-point change. Use for tolerance bands.

The comparator agent expects BOTH absolute and relative values for Gini — published priors don't always specify which they report.

## Failure modes & known gotchas

- **API timeout:** retry with backoff. Cache `policy_id` to avoid recompute. Real wall-clock is 5-10 minutes for full US economy; don't time out under 20 minutes.
- **Unsupported jurisdiction:** if `country=ca`, surface that Canada has no microdata — only household calculations are supported.
- **Reform-dict syntax error:** PE API returns 400; surface the error so `parameter-locator` can fix the snippet.
- **HTTP 400 "dataset: Extra inputs are not permitted":** the economy request sent a `dataset` query parameter. Drop it; to run a named dataset, take the local path.
- **Silently-wrong reforms:** the API may accept a half-baked reform-dict (e.g., setting CTC bracket amounts without enabling `phase_out.arpa.in_effect`) and return numbers that look plausible but are wrong. ALWAYS sanity-check the result against the prior anchor before continuing. If cost is off by >30%, suspect a missing toggle/switch and re-read the country-model formula file.
- **`Infinity` encoding depends on the parameter's value type.** The policy DB stores reform-dicts as JSON in a MySQL JSON column, which rejects bare `Infinity`.
  - **Float-typed parameters** (caps, thresholds, amounts): accept either the string `".inf"` OR a large numeric like `1e15`. Prefer `.inf` for clarity.
  - **Integer-typed parameters** (ages, qualifying-children counts): the string `".inf"` fails silently — the POST is accepted but the `/economy` call later returns `status: "error", message: null` with no diagnostic. Use a large *integer* like `999` instead.
  - When unsure, read the YAML — if it has `value_type: int` or values look like integers (no decimal), use the integer form.
- **Wrong baseline ID:** a baseline ID other than the country's current-law ID returns a parse error or a stale baseline. Always use `/over/{baseline_policy_id}` — see Step 2.
- **Multi-year discontinuities:** TCJA / OBBBA / similar regime-shift parameters make single-year results unrepresentative of a 10-year window. When the reform touches a parameter that sunsets or inflates, run all 10 years (`--horizon 10`) — do NOT extrapolate. The 2026-07-01 std-ded +$1K empirical case: yr1×10 = $178.6B understated the real 10-year cost ($196.10B) by 10%.

## Hand-off

Returns the impact JSON. Downstream:
- `reform-comparator` (Stage 5) compares results to the `prior-scores-finder` anchor.
- `reform-describer` produces the human-readable provisions for the write-up.
- The /analyze-policy command formats the final report.

**This agent does NOT write to any database.** Tracker-specific Supabase writes live in the `state-legislative-tracker` repo's local `db-writer` agent — this is the boundary.
