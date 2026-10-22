---
name: policyengine-comparables-review
description: |
  The comparables review every PolicyEngine analysis passes before its dashboard or research post
  is listed on policyengine.org, and again before a newsletter, social campaign or press push
  features it: search every producer on the scorecard's list for external estimates, stage each
  in PolicyEngine/policyengine-scorecard, compare it with the analysis's own figures, and explain
  every gap over the threshold. CI in the scorecard, policyengine-app-v2 and the newsletters repo
  checks it. Includes a brief for running the search as a background job.
  Triggers: "comparables", "comparables review", "pre-publish review", "before publishing",
  "add to apps.json", "add to posts.json", "scorecard record", "external estimates",
  "comparables gate", "analysis-uk-", "analysis-us-", "re-harvest", "newsletter",
  "before a push", "promote an analysis".
  NOT for: benchmarking a reform mid-analysis without publishing (policyengine-prior-scores,
  /prior-scores).
metadata:
  category: process
---

# Pre-publish comparables review

Before PolicyEngine publishes an analysis, every external estimate of what it estimates is
found, recorded in PolicyEngine/policyengine-scorecard, compared with the analysis's own
figures, and every large gap is explained. The rule dates from October 2026. The £100,000
childcare dashboard went live at £0.43bn for the 30 hours in 2027-28, while CenTax had published
£0.80bn from HMRC data a month earlier. The cause, a Microcosm hours draw (microcosm#1126), had
already been filed. A search before launch would have put the two figures side by side, and the
gate would have required the gap to be explained.

The contract lives in the scorecard: `docs/COMPARABLES.md`. Read it before your first review.
This skill is the operating procedure.

## What checks it

| Where | What its CI fails |
|---|---|
| policyengine-scorecard | A `sources/analysis-*` record that skips a listed producer, stages a value that does not parse back from what was printed, compares unlike quantities, leaves a gap over the threshold unexplained, or whose latest search did not compare the results files its estimates are read from; a stale `data/comparables/index.json`; feeds the build rewrites that are not committed |
| policyengine-app-v2 | A research entry (an apps.json app shown with research or tagged `policy`, or any post) that is not on the list of entries live before the gate (`website/src/data/comparablesGrandfathered.json`) and has no `comparables` block naming a search the scorecard index on main lists. The search must be dated on or before the entry's date, no more than 30 days before it, and not be a backfill. On the day a change lists or re-lists an entry, the search must also be no more than 30 days old that day, have compared the results the analysis reads now, and leave no gap pending. A card a change adds to the featured banner needs a fresh search (see "Before a push"). Every page the site proxies to another deployment must be a research app's, a page live before the gate, or on the list of pages that publish no analysis |
| PolicyEngine/newsletters | A changed edition that links an analysis whose search is not fresh (see "Before a push"), found through app-v2's route map (every path, redirect and deployment host that leads to an analysis) and the scorecard records' pages and `deployments`; `upload-newsletter` refuses the same before it touches Mailchimp |

The order is: scorecard PR merged first, then the apps.json or posts.json entry. A post that is
plainly not an analysis (tagged `org`, `event`, `giving`, `conferences`, `year-in-review` or
`april-fools`, and no analysis tag) may declare
`"comparables": {"status": "no_estimate", "reason": "..."}` instead. An app never may: a
household calculator is searched like any other analysis (step 2).

These are CI checks. Until the repositories make them required status checks, a red check is
what stops a merge, so never merge past one.

## The review, step by step

Work in a worktree of the scorecard off `origin/main`. Run commands with `uv run` and
`PYTHONPATH=.`. The worked example to copy is `sources/analysis-uk-childcare-100k-threshold/`.

### 1. Scaffold

```bash
PYTHONPATH=. uv run python -m scorecard_db.comparables scaffold --country uk --kind app --slug <slug>
```

`<slug>` is the analysis's policyengine.org slug: the apps.json `slug`, or the post's file name
up to its first dot, lowercased, with underscores as hyphens (`UK_Two_Child_Limit.md` →
`uk-two-child-limit`). `--today` defaults to your local date. Only the UK and US have producer
lists so far; for another country, add its list to `data/comparables/producers.json` first. The
skeleton's `search_log.json` lists every producer the search must log.

### 2. Pin the analysis's own figures (`analysis.json`)

Every figure the page publishes that a producer might also estimate goes in `pe_estimates`,
read from the results file the page builds from, never retyped from the page. Leaving a
published figure out is how a miss hides, so list them all. Each estimate has:

- `key`, `label`, `world`, `metric`, `unit_concept`, `period`, `time_basis`, `value`,
  `value_raw` (as the file prints it), `normalization`;
- `conditions.basis`: one word, `static` (no behavioural response), `post_behavioural`,
  `forecast` (a projected level, such as current-law revenue) or `outturn`; a fuller account goes
  in `conditions.basis_note`;
- `conditions.program`: a slug for what is costed, the programmes or taxes whose change the
  figure counts (`thirty_hours`, `both_schemes`, `state_pension_with_income_tax`); a longer
  description goes in `conditions.program_note`;
- `conditions.prices: real` for a money figure in a base year's prices (absent means cash);
- for a fiscal year, `conditions.fy` ("2027-28"), with `period` its end year and `time_basis`
  `fiscal_year`; anything more about the year goes in `conditions.fy_note`;
- `provenance`: the analysis repo, the commit the live page builds from, the results file's
  path and SHA-256, the field path, `computed_at`, the engine versions and the dataset release;
- the value in PolicyEngine's orientation for its metric (`scorecard_db/signs.py`
  `ORIENTATION`): `revenue_change` is positive = yield, `benefit_cost_change` positive = more
  spending, household income changes positive = gain. A file that prints a cost as a positive
  number gets `"sign": -1` and a `sign_basis`.

`worlds` has one entry per policy world the analysis or a producer scores, with a `policy` slug
and a `description`; reuse a slug the scorecard already uses for the same world.

`deployments` lists the other https URLs the analysis is served from, such as its own Vercel
deployment, so the newsletters check holds a link to any of them to this record, even after the
analysis leaves policyengine.org.

A household calculator publishes no fixed estimate. It declares
`"calculator": {"reason": "<what the page computes>"}`, pins no estimates, and its searches
record `results_pins: []`. It is still searched.

### 3. Search every producer

For each producer in the skeleton, run its `search_hints` with the analysis's `search_terms`,
check the places its `where_to_look` names, and log what happened:

| Result | When |
|---|---|
| `found` | You staged its estimates; list the claim keys |
| `none_found` | Nothing; list the queries run and pages checked |
| `found_not_staged` | An estimate exists, but its primary cannot be read: a figure seen only in press, or released under FOI with no published response. The note says what it is and `checked` lists where it was seen. It does not count in `found` |
| `not_applicable` | Only when the producer's `applies_to` excludes the analysis's `scope` |

`open_search` (any producer not on the list: other think tanks, consultancies, parties, select
committees, the Commons Library) and `academic` are never skipped. A comparable from an
unlisted producer is found under them and keeps its producer's own slug as `source`; a
comparable from a listed producer is logged under that producer's own entry. If an open search
keeps finding one producer, add it to `producers.json` with a `why` and an `added` date of the
day you add it.

Search engines often answer from secondary coverage. Trace each figure to the producer's own
publication before staging it.

Each search records `results_pins`, the results files it compared:

```bash
PYTHONPATH=. uv run python -m scorecard_db.comparables pins analysis-<country>-<slug>
```

### 4. Stage each estimate (`claims_staged.jsonl`, `manifest.jsonl`)

Download each primary into a new empty directory, hash it, and add one `manifest.jsonl` line
(url, title, date, publisher, sha256, retrieved, access). Hash the documents your annotations
cite and the pages your searches checked too; a manifest line nothing cites, links or lists as
checked fails the check. Then one claim per published number.
Copy a claim's shape from the worked example: `key`, `source`, `found_by`, `found_on`,
`source_model`, `metric`, `unit_concept`, `value`, `value_raw`, `normalization`, `value_kind`,
`period`, `time_basis`, `conditions`, `world`, `reform_hint`, `attribution`, `benchmark_class`,
`baseline_policy`, `publication` (title, url, date, publisher, primary_sha256, locator, access),
`source_table`, `source_column`, `quote`, `parse_confidence`, `status: "ok"`, and `compare_to`
or `pe_missing`.

Of the harvest rules (`sources/harvest-uk-ab2025-2026-09-24/README.md`), these apply: verbatim
values (1), registered vocabulary, named baselines (7) and unreadable primaries (8). The fields
specific to the Autumn Budget harvest (`measure_key`, `fiscal_event`) do not.

- `value_raw` exactly as printed (`"-800m"`, `"£0.80bn"`, `"(0.4)"`, `"−4.2pp"`), `value`
  normalised under a normalisation whose scale matches the printed one (`NORMALIZATIONS` in
  `scorecard_db/comparables.py`; `percent as printed` for a figure printed with `%` or `pp`),
  and a `quote` that prints the value as a whole number with its sign (a dash between two
  numbers, as in "£3-3.4bn", is a range, not a sign). One number per claim. A printed range is
  two claims, `value_kind` `range_low` and `range_high`, sharing a `conditions.range_group`; a
  one-sided figure ("over £1 billion") is `lower_bound` or `upper_bound`, and like a `cumulative`
  total it is set beside an estimate, never compared with one.
- Never re-sign a value. Put its convention in `conditions.sign_convention`, starting
  `positive =` and saying one thing, in words `signs.py` reads: `positive = yield to the
  Exchequer`, `positive = cost to the Exchequer`, `positive = gain to households`,
  `positive = higher government revenue`, `positive = higher government expenditure`. It does
  not read `negative = ...`, a two-sided sentence, or a phrase turned around
  (`positive = yield forgone`).
- The same identity fields as an estimate: `period`, `time_basis`, `conditions.basis`,
  `conditions.program`, `conditions.prices`. A producer that does not say whether its figure
  allows for behaviour gets basis `unstated`, and one that does not say whether it is in cash or
  today's prices gets prices `unstated`: such a claim is never the same quantity as an estimate,
  so it is set beside one, not compared. Check each producer's year label: CenTax labels tax
  years by their later year.
- `attribution`: `own` when the producer computed it, `restated` when it repeats another's
  figure. Only `own` estimates are compared.

### 5. Compare

- A claim on the same quantity as an estimate (same metric, unit, period, time basis, basis and
  programme, the producer's own, not cumulative, same baseline) names it in
  `compare_to: {"pe_estimate": "<key>"}`. If the two score different policy worlds,
  `compare_to.across_worlds` gives the reason the quantities still match and its basis, and the
  comparison is recorded as `constructed`.
- A claim with an estimate near it (the same period, and the same metric and unit where the
  claim names them) that is a different quantity (net of behaviour beside static, a fiscal year
  beside a calendar year) names that estimate in `nearest_estimate`, gives `pe_missing`, and
  gets an annotation with status `concept_mismatch` (or `pe_gap`) and a basis. A claim on the
  same quantity cannot be set aside this way: the validator makes you compare it.
- Any other claim gives `pe_missing`.

**Never do these to keep a gap from being compared**, even when the validator cannot tell:

- leave a published figure out of `pe_estimates`;
- set a claim's metric or unit to null when an estimate covers the quantity;
- stage a figure as `approx_chart_reading` when the producer prints it;
- choose a period, time basis, basis or programme to avoid a match;
- label an explained miss `concept_mismatch`: a miss on the same quantity is `comparable` or
  `constructed`, with the cause.

### 6. Explain every gap over the threshold (`annotations.json`)

```bash
PYTHONPATH=. uv run python -m scorecard_db.comparables check sources/analysis-<country>-<slug>
PYTHONPATH=. uv run python -m scorecard_db.comparables report analysis-<country>-<slug> --since <first search date>
```

`check` lists every error, and the unexplained gaps once nothing else is wrong. `report` lists
every gap over the threshold; it runs on a record whose only errors are unexplained gaps
(printing those on stderr) and refuses a record with any other error. A gap over `gap_threshold` (`data/comparables/policy.json`, 25% by
default), a sign disagreement, or a nonzero estimate against a published zero needs an
annotation with an `id`, the `claims`, a `status`, `explains_gap: true`, a `cause`, and a
`basis`: a GitHub issue or pull, engine metadata pinned to a commit, or a document or
diagnostic URL (or a file in the scorecard). A range is over only when our figure lies outside
it by more than the threshold.

Without a basis you have read, the gap is not explained. Find the cause first (most often our
data or rules: file the issue), or hold the analysis. A number in the cause must come from a
real run: never scale or interpolate other runs to argue the gap away.

A gap that a search after publication finds (`backfill`, `reharvest`, `prepromotion`) may be
`pending` while the cause is found: open an issue for the analysis's owner with the producer,
the figures, the gap and what you checked, put it in `tracking_issue`, and write the cause as
"Unexplained; tracked in <issue>" with the issue as the basis. A pending gap blocks every push
of the analysis until it is replaced by the cause. Nothing found before publication can be
pending.

### 7. Land it

```bash
PYTHONPATH=. uv run python -m scorecard_db.comparables index
rm -f data/scorecard.db && PYTHONPATH=. uv run python -m scorecard_db.build_db data/scorecard.db
PYTHONPATH=. uv run python -m scorecard_db.export_populations data/scorecard.db
for f in lanes.json populations.json comparison.json exhibits.json; do cp data/$f app/public/data/$f; done
PYTHONPATH=. uv run --python 3.12 --with pytest --with hypothesis --with pypdf --with pyyaml --with numpy --with psutil --with rfc8785==0.1.4 --with jsonschema pytest tests/ -q
```

The suite runs on Python 3.12, as the scorecard's CI does (one of its tests needs a 3.12
interpreter). Commit everything the build rewrites: `git status` must be clean afterwards, or CI's drift check
fails. Open the scorecard PR, have it reviewed with the checklist below, and merge it on its
gates. Then print the registry block and paste it into the apps.json or posts.json entry:

```bash
PYTHONPATH=. uv run python -m scorecard_db.comparables record analysis-<country>-<slug>
```

It cites the record's latest search (`--search-date` and `--search-kind` pick another). A
revised analysis returning to the site cites the new search its results were compared in, and
gives the entry its new listing date.

### Reviewer checklist

A reviewer opens the record and the primaries, not just the validator's output:

- every figure on the page, or in the results file the page reads, is in `pe_estimates`;
- each `pe_missing` reason is true, and each `nearest_estimate` mismatch is real;
- each annotation's basis, once opened, supports its cause;
- a sample of `none_found` results is searched again, and every `found_not_staged` note is
  checked;
- the manifest's hashes are recomputed from the URLs;
- each staged value and quote is found at its locator in the primary.

## United States

- **Sign conventions.** Use `positive = higher government revenue` for `revenue_change`
  (CBO and JCT print revenue increases as positive), `positive = increase in borrowing` or
  `positive = cost to the Exchequer` for a deficit increase stated against revenue, and
  `positive = higher government expenditure` for `benefit_cost_change`. A convention that names the opposite quantity ("positive = increase in federal revenue" for a
  spending metric) is refused. An empty convention never orients a change.
- **Fiscal and calendar years.** CBO and JCT report federal fiscal years (October to September),
  with `period` the year the fiscal year ends and `time_basis` `fiscal_year`. PolicyEngine's
  federal estimates are calendar years. The two are near but not the same quantity: name the
  calendar-year estimate in `nearest_estimate` with a `concept_mismatch` annotation, unless the
  analysis publishes a fiscal-year figure to compare.
- **Budget windows.** A ten-year total is `value_kind: cumulative`. The validator does not
  compare a cumulative figure with anything yet, a window total of the same years included: stage
  it uncompared, beside the nearest single-year estimate with a `concept_mismatch` annotation
  saying it is a window total, and never restate it as an annual figure.
- **State fiscal notes** are `state_fiscal_note` (`<state>_fiscal_note` as `source`), searched
  for state and local analyses.

## Running the search as a background job

`references/search-brief.md` is a self-contained brief with placeholders to fill. It works for
any agent with web search, a shell and `gh` authenticated to push a branch and open a draft PR
in the scorecard. The job writes, downloads primaries and opens a PR, so it needs a writable
workspace and network access. On PolicyEngine's internal Subfleet lanes:

```bash
subfleet run --task research --tier standard -s workspace-write -C <scorecard worktree> -p brief.md -o out.md
```

The brief has the job open a draft scorecard PR, even when a gap is unexplained, and report the
producer table and every gap. Review the PR with the checklist above before merging. A job's
report is a claim, not proof.

## Before a push

Before an analysis is featured in a newsletter, a social campaign, a webinar or a press push, its
search must be fresh:

- a search dated on the push date or in the `promotion_window_days` before it
  (`data/comparables/policy.json`, 7 by default, counting both ends);
- that compared the results files the analysis reads now;
- and no gap found by then still `pending`.

```bash
PYTHONPATH=. uv run python -m scorecard_db.comparables fresh analysis-<country>-<slug> --on <push date>
```

Run it in a checkout of the scorecard's `origin/main`, which is what the newsletters check
reads. If it is not fresh, append a search with `kind: prepromotion` and today's date that logs
every producer, stage what is new, and explain every gap over the threshold. An analysis with no
record gets its first search (`backfill`). A pending gap blocks the push: explain it, or leave
the analysis out. Once it is explained, the push may state the comparable beside our figure.
The same rule holds for a card added to policyengine.org's featured research banner, which
app-v2's gate checks on the day the change runs.

## After publishing

For six months after an analysis is published, a PolicyEngine scheduled job searches again each
week (`kind: reharvest`) once the scorecard tooling is on main. A new comparable becomes a row in
the analysis's directory. A new gap over the threshold gets a `pending` annotation and an issue
for the owner (the app-v2 author). Close the issue by replacing `pending` with the cause.

## Bill-tracker scores

A bill scored through `/reform-pipeline`'s tracker route is reviewed before dispatch like any
other analysis. Its record has `registry.kind: tracker` (slug `<state>-<bill>`, the tracker page
as `url`), and its bill-review PR carries the record's link and gap table. No registry lists
tracker bills, so app-v2 does not check them; the scorecard's re-harvest finds them by their
record's `published` date.

## Related

- `policyengine-prior-scores`: benchmarks while an analysis is being built. Its scorekeepers
  registry is the wider pool, but the producers this review must log are the scorecard's
  `data/comparables/producers.json`.
- `policyengine-writing`: the publishing checklist this review is part of.
- `policyengine-tools`: registering a dashboard in apps.json.
