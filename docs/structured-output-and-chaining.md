# Structured output + native chaining for `/analyze-policy`

> **Status: design spec, mostly unimplemented.** Phase A (publishing this
> schema) is done; phases B–D (wiring report-logger, the queue, and
> run_manifest.json) are not built. Nothing here describes live behavior —
> treat it as the reviewed plan for future wiring.

This spec captures the machine-first output shape and the composition rules
for chaining `/analyze-policy` with adjacent commands. It lays out the
schema without wiring implementation into the agents yet — that lands as
follow-up work once the schema is reviewed.

## Motivation

Today every stage emits markdown. Downstream agents that want to
programmatically consume the pipeline's output (chain into
`/generate-content`, file structured Notion pages, feed a supervisor agent)
have to re-parse. This is fragile — markdown drifts, prose changes, section
headings get renamed.

The runtime destination prompt, horizon prompt, and destination-shortlist
context detection are all designed for an analyst at a terminal. In a
headless / CI / multi-agent orchestration, we need:

- Predictable structured output alongside the markdown archive.
- A stable `run_manifest.json` sidecar with wall-clock, agent-invocation, and
  budget tracking so a supervisor agent can decide "retry", "escalate", or
  "abort".
- A `--next-step` flag (and a runtime prompt) that lets the pipeline hand
  off to the natural follow-up command based on verdict.

## Structured envelope

Every archived analysis gains a JSON sidecar at the same path as the
markdown, with the `.json` extension:

```
analyses/2026-07-01-us-standard-deduction-plus-1k.md
analyses/2026-07-01-us-standard-deduction-plus-1k.json      # NEW
```

### Sidecar schema

```json
{
  "schema_version": 1,
  "analysis_id": "2026-07-01-us-standard-deduction-plus-1k",
  "policy_id": 97853,
  "run_id": 97853,
  "date": "2026-07-01T09:58:00Z",
  "verdict": "PASS-WITH-NOTES",
  "jurisdiction": { "country": "us", "state": null },
  "reform": {
    "title": "Federal standard deduction +$1,000 all statuses (2026-2035)",
    "preset": null,
    "reform_dict": { "...": "..." },
    "provisions": [ /* mechanical provisions from reform-describer */ ],
    "tags": ["standard-deduction", "federal", "progressive-incidence"]
  },
  "microsim": {
    "horizon": 10,
    "years_run": [2026, 2027, ..., 2035],
    "per_year_budget_billion": {
      "2026": -17.86, "2027": -17.86, "...": "..."
    },
    "ten_year_actual_federal_billion": -196.10,
    "ten_year_actual_state_billion": -2.36,
    "gini_pct_change_per_year": { "2026": -0.026, "...": "..." },
    "poverty_pct_change_per_year": { "...": "..." },
    "dataset_backing": "populace-us-2024",
    "model_version": "1.745.0"
  },
  "comparison": {
    "external_sources_in_agreement": 1,
    "external_sources_in_disagreement": 0,
    "benchmark_verdict": "PASS-WITH-NOTES",
    "auto_widening_applied": 1.0,
    "auto_widening_triggers": []
  },
  "corroboration": {
    "ran": false,
    "overall_verdict": "NO-CORROBORATION-POSSIBLE",
    "candidates_run": []
  },
  "destinations": {
    "archive": {
      "type": "archive",
      "path": "analyses/2026-07-01-us-standard-deduction-plus-1k.md"
    },
    "github_issues": [
      { "repo": "PolicyEngine/policyengine-skills", "number": 26, "url": "..." }
    ],
    "draft_prs": []
  },
  "run_manifest": {
    "wall_clock_seconds": 1247,
    "agents_invoked": [
      "policy-text-researcher",
      "parameter-locator",
      "reform-classifier",
      "prior-scores-finder",
      "microsim-runner",
      "reform-comparator",
      "reform-describer",
      "report-logger"
    ],
    "api_calls": 11,
    "budget_window_endpoint_used": true
  }
}
```

### Emission rule

`report-logger` writes the JSON sidecar alongside the markdown archive in
Phase 8. Every stage produces a partial dict that report-logger merges into
the final envelope. Stages MUST NOT rewrite the markdown after this — the
sidecar is a snapshot of the run, not a live document.

## Native chaining: `--next-step`

Add a `--next-step` flag that maps verdict → follow-up command. When the
analyst omits the flag, the runtime destination prompt (already present in
report-logger) gains an extra "Also queue…?" line:

```
Where should this analysis go?

[x] Local archive
[ ] GitHub issue: PolicyEngine/policyengine-us-data
[ ] Also queue: /encode-policy-v2 (this reform's structural provisions)
[ ] Also queue: /generate-content (blog draft from the analysis)
[ ] Also queue: /review-program on the parameter files this reform touches
```

Verdict → follow-up mapping:

| Verdict | Natural next step |
|---|---|
| `PASS` | `/generate-content` → blog post draft |
| `PASS-WITH-NOTES` / `PASS-WITH-CORROBORATION` | `/generate-content` → blog post draft (with notes/caveats section) |
| `INVESTIGATE` | already handled: GH issue in `policyengine-{country}-data` |
| `structural` | `/encode-policy-v2` → scaffold the required model extension |
| `not-possible` | none |
| `deployed-model-lag` | re-run scheduled for next release (cron-style: after the next `uv pip install -U policyengine-{country}`) |

When the analyst picks a "Also queue" option, the pipeline emits a stub
task to a local queue (`~/.policyengine/queue/` or `.policyengine/queue/`
in-repo) with the sidecar JSON as the payload. A supervisor agent (or a
manual `/dequeue` command) can then pick it up and run the follow-up.

## Run manifest for headless orchestration

Every run also writes `analyses/YYYY-MM-DD-slug.run.json`:

```json
{
  "run_id": 97853,
  "started_at": "2026-07-01T09:37:12Z",
  "ended_at": "2026-07-01T09:57:59Z",
  "wall_clock_seconds": 1247,
  "verdict": "PASS-WITH-NOTES",
  "agents_invoked": [ /* per-agent name + wall-clock + tool-calls */ ],
  "api_calls": { "budget_window": 1, "single_year": 0, "policy_create": 1 },
  "warnings": [],
  "errors": []
}
```

A supervisor agent reading this file can decide:

- **retry** if `errors` non-empty with a transient class
- **escalate** if `wall_clock_seconds > threshold` or the verdict is
  INVESTIGATE with no auto-investigate path
- **abort** if `errors` non-empty with a permanent class

## Implementation phases

1. **Phase A (this PR):** publish the schema (this doc). No agent changes.
2. **Phase B:** wire `report-logger` to emit the JSON sidecar in addition
   to the markdown. All existing archives get regenerated in a follow-up
   sweep.
3. **Phase C:** add `--next-step` flag + runtime "Also queue" prompt line
   to the destination shortlist. Local queue directory.
4. **Phase D:** `run_manifest.json` emission from every run. Supervisor
   agent (out of scope for this repo — lives wherever the orchestrator
   does).

## Compatibility with existing archives

The existing 6 archived analyses do NOT have JSON sidecars. A one-off
backfill script `scripts/backfill_sidecars.py` can generate them from the
markdown frontmatter + the source manifest data.
