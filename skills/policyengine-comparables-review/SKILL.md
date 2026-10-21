---
name: policyengine-comparables-review
description: |
  The pre-publish comparables review every PolicyEngine analysis passes before its dashboard or
  research post is registered on policyengine.org: search every producer on the scorecard's list
  for external estimates of what the analysis estimates, stage each one under the harvest rules in
  PolicyEngine/policyengine-scorecard, compare it with the analysis's own figures, and explain
  every gap over the threshold. policyengine-app-v2 CI enforces it for research entries dated on
  or after its cutover. Includes the brief for running the search as a Subfleet research job.
  Triggers: "comparables", "comparables review", "pre-publish review", "before publishing",
  "publish a dashboard", "add to apps.json", "add to posts.json", "comparables block",
  "scorecard record", "external estimates", "how do we compare", "comparables gate",
  "analysis-uk-", "analysis-us-", "re-harvest".
  NOT for: benchmarking a reform mid-analysis without publishing (policyengine-prior-scores,
  /prior-scores).
metadata:
  category: process
---

# Pre-publish comparables review

Before PolicyEngine publishes an analysis, every external estimate of what it estimates is
found, recorded in PolicyEngine/policyengine-scorecard, compared with the analysis's own
figures, and every large gap is explained. Max set the rule on 2026-10-21 after the £100,000
childcare dashboard went live at £0.43bn for the 30 hours in 2027-28 while CenTax had published
£0.80bn from HMRC data a month earlier. A data bug (microcosm#1126) caused the gap. The search
this skill runs would have found CenTax before launch, and the gate would have required the
gap to be explained.

The contract lives in the scorecard: `docs/COMPARABLES.md`. Read it before your first review.
This skill is the operating procedure.

## What enforces it

| Where | What fails |
|---|---|
| policyengine-scorecard CI | Any `sources/analysis-*` directory that skips a listed producer, stages a value that does not parse back from what was printed, or leaves a gap over the threshold unexplained; a stale `data/comparables/index.json` |
| policyengine-app-v2 CI | A research entry dated on or after the cutover (`website/src/data/comparables.ts`) whose `comparables` block is missing, malformed, or names a search the scorecard index on main does not list |

So the order is: scorecard PR merged first, then the apps.json or posts.json entry.

An entry that publishes no estimate (an event write-up, an announcement) declares
`"comparables": {"status": "no_estimate", "reason": "..."}`. An entry tagged `policy` cannot.

## The review, step by step

All commands run from a scorecard worktree off `origin/main`, with `PYTHONPATH=.`.

### 1. Scaffold

```bash
python -m scorecard_db.comparables scaffold --country uk --kind app --slug <slug>
```

`<slug>` is the analysis's policyengine.org slug: the apps.json `slug`, or the post's filename
without `.md`. The skeleton's `search_log.json` already lists every producer the search must
log, from `data/comparables/producers.json`.

### 2. Pin the analysis's own figures (`analysis.json`)

Every number the analysis publishes that a producer might also estimate goes in
`pe_estimates`, read from the results file the page builds from, never retyped from the page:

- `provenance`: the analysis repo, the commit the live page builds from, the results file's
  path and `shasum -a 256`, the field path, `computed_at`, the engine versions and the dataset
  release.
- State the value in PolicyEngine's orientation for its metric (`scorecard_db/signs.py`
  `ORIENTATION`): `revenue_change` is positive = yield to the Exchequer, `benefit_cost_change`
  positive = more spending, household income changes positive = gain. A results file that prints
  a cost as a positive number gets `"sign": -1` and a `sign_basis`.
- `worlds`: one entry per policy world the analysis or a producer scores, keyed by a short name,
  with a `policy` slug. Reuse a slug the scorecard already uses for the same world, so worlds
  share reform keys across sources.

### 3. Search every producer

For each producer in the skeleton, run its `search_hints` with the analysis's `search_terms`,
check the places its `where_to_look` names, and log what happened:

| Result | When |
|---|---|
| `found` | You staged its estimates; list the claim keys |
| `none_found` | Nothing; list the queries run and pages checked |
| `found_not_staged` | An estimate exists, but its primary cannot be read: a figure seen only in press, or released under FOI with no published response. The note says what it is and `checked` lists where it was seen |
| `not_applicable` | Only when the producer's `applies_to` excludes the analysis's `scope` |

`open_search` (any producer not on the list: other think tanks, consultancies, parties, select
committees, the Commons Library) and `academic` are never skipped. A comparable from an
unlisted producer is logged there and keeps its producer's own slug. If an open search keeps
finding one producer, add it to `producers.json` with a `why`. The first search added DfE that
way.

Search engines often answer from secondary coverage. Trace each figure to the producer's own
publication before staging it.

### 4. Stage each estimate (`claims_staged.jsonl`, `manifest.jsonl`)

Download each primary into a new empty directory, hash it, and add one `manifest.jsonl` line.
Then one claim per published number, under the harvest rules
(`sources/harvest-uk-ab2025-2026-09-24/README.md` in the scorecard):

- `value_raw` exactly as printed (`"-800m"`, `"£0.80bn"`, `"13,360"`), `value` normalised to the
  unit under a normalisation the validator knows (`NORMALIZATIONS` in
  `scorecard_db/comparables.py`), and a `quote` that contains the printed value. One number per
  claim: a range is two claims.
- Never re-sign a value. Put its convention in `conditions.sign_convention`, in words
  `signs.py` recognises: `positive = yield to the Exchequer`, `positive = cost to the
  Exchequer`, `positive = gain to households`. It does not read `negative = cost to the
  Exchequer`. A producer that prints costs as negatives is stated as `positive = yield to the
  Exchequer`, with the printed note quoted after it.
- `period` is the financial-year end year (2027-28 → 2028), with `conditions.fy`. Check each
  producer's year label: CenTax labels tax years by their later year.
- `attribution`: `own` when the producer computed it, `restated` when it repeats another's
  figure. Only `own` estimates are compared.
- `compare_to` names the estimate it matches: same metric, unit, period and time basis. If the
  worlds differ, `compare_to.across_worlds` gives the reason the quantities still match and its
  basis, and the comparison is recorded as `constructed`. If nothing matches, `pe_missing` says
  why ("net of behavioural responses; the dashboard is static").

### 5. Explain every gap over the threshold (`annotations.json`)

```bash
python -m scorecard_db.comparables check sources/analysis-<country>-<slug>
```

It lists each compared claim whose gap exceeds `gap_threshold` (`data/comparables/policy.json`,
±25% by default). Each one needs an annotation with `explains_gap: true`, a `cause`, and a
`basis`: a GitHub issue or PR, engine metadata pinned to a commit, a document, or a measured
diagnostic. Without a citable basis, the gap is not explained yet. Find the cause first (most
often our data or rules: file the issue), or hold the analysis. A number in the cause must
come from a real run: never scale or interpolate other runs to argue the gap away.

### 6. Land it

```bash
python -m scorecard_db.comparables index        # regenerate data/comparables/index.json
rm -f data/scorecard.db && python -m scorecard_db.build_db data/scorecard.db
pytest tests/ -q
```

Open the scorecard PR and merge it on its gates. Then print the registry block and paste it
into the apps.json or posts.json entry:

```bash
python -m scorecard_db.comparables record analysis-<country>-<slug>
```

## Running the search as a Subfleet job

`references/subfleet-brief.md` is a self-contained research brief with the placeholders to
fill. The job needs web search, so give it a lane with network access:

```bash
subfleet run --task research --tier standard -C <scorecard worktree> -p brief.md -o out.md
```

The brief has the job open a draft scorecard PR and report the producer table and every gap.
Review the staged claims against their primaries before merging. A job's report is a claim,
not proof.

## After publishing

For six months after an analysis is published, a weekly job searches again (`kind:
reharvest`). A new comparable becomes a row in the analysis's directory. A new gap over the
threshold gets a `pending` annotation and an issue for the owner (the app-v2 author). Close the
issue by replacing `pending` with the cause.

## Related

- `policyengine-prior-scores`: benchmarks while an analysis is being built. Its scorekeepers
  registry is the wider pool, but the producers this review must log are the scorecard's
  `data/comparables/producers.json`.
- `policyengine-writing`: the publishing checklist this review is part of.
- `policyengine-tools`: registering a dashboard in apps.json.
