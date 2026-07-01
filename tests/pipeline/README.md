# Pipeline regression tests

Fixture-based tests for the silent-failure gotchas we've discovered in
`/analyze-policy` over time. Each test corresponds to a specific bug we
already burned time on and are determined not to repeat.

## Run

```bash
python3 -m pytest tests/pipeline/
```

Tests hit local fixtures + parsers — no live API calls. Fast.

## The gotchas covered

| Test | Gotcha |
|---|---|
| `test_per_year_baseline.py` | Single-row reform-dict silently no-ops for years 2027+ when baseline has per-year rows (surfaced 2026-07-01 by std-ded +$1K). |
| `test_dataset_naming.py` | Un-advertised dataset names (`enhanced_cps_2024`, `enhanced_cps_2024_2026`) silently fall back to raw `cps`. Runner must use advertised names + validate `data_version` returned. |
| `test_verdict_enum.py` | Every verdict named in the pipeline must appear in the comparator's Output enum. `PASS-WITH-CORROBORATION` and `BLOCKED` were missing at one point. |
| `test_country_routing.py` | Auto-routed GitHub issues must use `policyengine-{country}-data`, never hardcoded `policyengine-us-data`. |
| `test_analyses_frontmatter.py` | Every archived analysis's frontmatter must have the required fields documented in `analyses/README.md`. Prevents drift as the schema evolves. |

## Adding a test

When you discover a new silent-failure mode, add a test here BEFORE fixing it. Every gotcha we've surfaced (populace SSN gap, budget-window fallback, `.inf` on int-typed params, per-year baseline rows) should have a corresponding test that would have failed pre-fix.
