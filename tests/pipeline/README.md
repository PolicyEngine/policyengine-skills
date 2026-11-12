# Pipeline regression tests

Fixture-based tests for the silent-failure gotchas we've discovered in
`/analyze-policy` over time. Each test corresponds to a specific bug we
already burned time on and are determined not to repeat.

## Run

```bash
python3 -m pytest tests/pipeline/
```

Tests hit local fixtures and parsers, make no live API calls, and run fast. Set
`PE_SKILLS_LIVE_API=1` to also check `test_dataset_naming.py`'s metadata snapshots
and the economy routes' HTTP 400 answers against api.policyengine.org. The
snapshot check skips each dataset's release, which moves with every certified
build, and checks that the live release agrees with its URI.

## The gotchas covered

| Test | Gotcha |
|---|---|
| `test_per_year_baseline.py` | Single-row reform-dict silently no-ops for years 2027+ when baseline has per-year rows (surfaced 2026-07-01 by std-ded +$1K). |
| `test_dataset_naming.py` | policyengine-api rejects a `dataset` query parameter, so no agent or skill may send one. The test executes the runner's dataset helpers and API recording example. The gateway bundle names the app default; regional runs leave their selected file unknown and keep the worker's release. National results prefer the worker's release, and budget-window results leave all provenance unknown. A separate helper checks the URI the local path resolves. |
| `test_budget_window_polling.py` | microsim-runner's `run_horizon` returns a budget-window result, raises the API's reason when a batch fails, keeps polling through a timed-out or garbled poll, raises ValueError on an HTTP 400 or 404, and gives up once a batch keeps computing past its deadline, so the runner can fall back to single-year calls. On 2026-11-08 a two-year US window sat at "0 of 2 complete" for over half an hour. |
| `test_verdict_enum.py` | Every verdict named in the pipeline must appear in the comparator's Output enum. `PASS-WITH-CORROBORATION` and `BLOCKED` were missing at one point. |
| `test_country_routing.py` | Auto-routed data issues go to the repo that builds the run's dataset: `us` and `uk` → `microcosm`, a `uk` run on a named Enhanced FRS or FRS file → `policyengine-uk-data`, and `ca` → no issue, since PolicyEngine has no Canada microdata. The issue carries only the labels its repo has, since `gh` stops on a missing one. It also runs report-logger's issue-filing bash, under bash and zsh, with a stand-in `gh`: the block must match the same rules in Python, hand `gh` the issue's title and body as written, and name any country it can't route. |
| `test_analyses_frontmatter.py` | Every archived analysis's frontmatter must have the required fields documented in `analyses/README.md`. Prevents drift as the schema evolves. |

## Adding a test

When you discover a new silent-failure mode, add a test here BEFORE fixing it. Every gotcha we've surfaced (Microcosm SSN gap, budget-window fallback, `.inf` on int-typed params, per-year baseline rows) should have a corresponding test that would have failed pre-fix.
