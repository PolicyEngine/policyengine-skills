# Comparables search brief

Fill every `{placeholder}`, delete the section for the search kind you are not running, and pass
the result as the job's prompt. The brief works for any agent with web search and a shell. With
Subfleet: `subfleet run --task research --tier standard -C <scorecard worktree> -p brief.md -o
out.md`.

---

You are running the pre-publish comparables review for one PolicyEngine analysis. Read
`docs/COMPARABLES.md` in this repository (PolicyEngine/policyengine-scorecard) first; it is the
contract, and `python -m scorecard_db.comparables check` enforces it.

## The analysis

- Title: {title}
- Page: {url} (registry: {apps.json or posts.json}, slug `{slug}`, country `{country}`)
- What it estimates: {one or two sentences: the reform and the quantities it publishes}
- Its results file: `{repo}` at commit `{commit}`, path `{results path}`. Pin every estimate to
  this file and its SHA-256.
- Owner (app-v2 author key): {author}
- Scope: {uk_wide | england | scotland | wales | northern_ireland | federal | state | local}
- Search terms to start from: {terms}
- Search date: {YYYY-MM-DD}. Search kind: {prepublish | backfill | reharvest}

## Do this

Work in a branch `comparables/{country}-{slug}` off `origin/main` of this repository, with
`PYTHONPATH=.`.

### For a first search (prepublish or backfill)

1. `python -m scorecard_db.comparables scaffold --country {country} --kind {app|post} --slug {slug} --today {date}`.
   Set the search's `kind` to `{kind}` and `by` to this job's id.
2. Fill `analysis.json`: title, url, owner, scope, subject, search terms, the policy worlds, and
   one `pe_estimates` entry per published figure a producer could also estimate, read from the
   results file (never from the page). State each in PolicyEngine's orientation for its metric
   (`scorecard_db/signs.py` `ORIENTATION`), with `sign: -1` and `sign_basis` if the file prints
   it the other way.

### For a re-harvest

1. Append a search to the existing `sources/analysis-{country}-{slug}/search_log.json`:
   `kind: reharvest`, today's date, one entry for every producer on
   `data/comparables/producers.json` for {country} added on or before today.
2. Stage only what earlier searches did not find (check `claims_staged.jsonl` and the earlier
   searches' notes first).

### Every search

3. Search every producer in the search entry, in list order. Run its `search_hints` combined
   with the search terms. Check the places `where_to_look` names, as well as search results. Log
   `found`, `none_found`, `found_not_staged` or `not_applicable` with the queries run and pages
   checked. `not_applicable` only when the producer's `applies_to` excludes the scope. Never
   skip `open_search` or `academic`.
4. Trace every figure to its producer's own publication. Download each primary into a new empty
   directory outside this repository, `shasum -a 256` it, and add a `manifest.jsonl` line. A
   figure whose primary you cannot read (press-only, FOI with no published response) is
   `found_not_staged` with a note, never a claim.
5. Stage each number as one line of `claims_staged.jsonl` under the harvest rules
   (`sources/harvest-uk-ab2025-2026-09-24/README.md`): `value_raw` as printed, a registered
   `normalization`, a `quote` containing the printed value, a registered metric and unit (or
   null plus a proposal), the sign convention in words `signs.py` reads (it reads `positive =
   yield to the Exchequer`, not `negative = cost to the Exchequer`), the financial-year end year
   as `period`, the world it scores, attribution, benchmark class and the publication's locator.
6. Link each claim to the PolicyEngine estimate it matches (`compare_to`; same metric, unit,
   period and time basis; `across_worlds` with a reason and basis if the worlds differ), or give
   `pe_missing`. A claim that shares metric, unit, period and time basis with an estimate but is
   a different concept (net vs static) names it in `nearest_estimate` and gets a
   `concept_mismatch` annotation with a basis.
7. Run `python -m scorecard_db.comparables check sources/analysis-{country}-{slug}`. For every
   gap it reports over the threshold, find the cause. Read the analysis's code and data, the
   producer's method, and open issues (microcosm, policyengine-{country}, the analysis repo).
   Write an annotation that cites a basis you read. If you cannot find one:
   - first search: stop and report the gap as unexplained. Do not invent a cause.
   - re-harvest: add a `pending` annotation and open an issue for the owner on the analysis's
     repository with the producer, the figures, the gap and what you checked. Put the issue in
     `tracking_issue`.
8. `python -m scorecard_db.comparables index`, then `rm -f data/scorecard.db && python -m
   scorecard_db.build_db data/scorecard.db` and `pytest tests/test_comparables.py -q`. Commit,
   push, and open a draft PR titled "Comparables for {title}".

## Report

Write to the output file:

- the PR URL and head commit;
- one line per producer: result, claims staged, and for `found_not_staged` what and why;
- every compared claim: producer, value, the PolicyEngine estimate, the gap, and the annotation
  (or "unexplained");
- for a re-harvest, the issues opened;
- anything you could not check, stated plainly.

Do not merge. Do not edit policyengine-app-v2. A person reviews the staged claims against their
primaries first.
