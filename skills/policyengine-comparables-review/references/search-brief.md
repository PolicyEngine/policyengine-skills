# Comparables search brief

Fill every `{placeholder}`, delete the sections for the search kinds you are not running, and
pass the result as the job's prompt. The brief works for any agent with web search, a shell and
`gh` authenticated to push a branch and open a draft PR in PolicyEngine/policyengine-scorecard.
The job writes files, downloads primaries and opens a PR, so it needs a writable workspace and
network access.

---

You are running the comparables review for one PolicyEngine analysis. Read
`docs/COMPARABLES.md` in this repository (PolicyEngine/policyengine-scorecard) first; it is the
contract, and `python -m scorecard_db.comparables check` enforces it. The worked example to copy
is `sources/analysis-uk-childcare-100k-threshold/`.

## The analysis

- Title: {title}
- Page: {url} (registry: {apps.json or posts.json}, slug `{slug}`, country `{country}`)
- What it estimates: {one or two sentences: the reform and the quantities it publishes}
- Its results file: `{repo}` at commit `{commit}`, path `{results path}`. Pin every estimate to
  this file and its SHA-256. (A household calculator with no fixed estimate: say so here.)
- Published: {YYYY-MM-DD, or "not yet"}
- Owner (app-v2 author key): {author}
- Scope: {uk_wide | great_britain | england | scotland | wales | northern_ireland | local |
  federal | state}
- Search terms to start from: {terms}
- Search date: {YYYY-MM-DD}. Search kind: {prepublish | backfill | reharvest | prepromotion}
- Push date (prepromotion only): {YYYY-MM-DD}

## Do this

Work in a branch `comparables/{country}-{slug}` off `origin/main` of this repository. Run every
command as `PYTHONPATH=. uv run python -m ...`.

### For a first search (prepublish or backfill)

1. `scorecard_db.comparables scaffold --country {country} --kind {app|post} --slug {slug} --today {date}`.
   Set the search's `kind` to `{kind}` and `by` to this job's id. A prepublish search is dated
   on or before publication; a backfill on or after it, with `published` set in
   `analysis.json`.
2. Fill `analysis.json`: title, url, owner, scope, subject, search terms, the policy worlds (each
   with a `policy` slug and a `description`), and one `pe_estimates` entry per figure the page
   publishes that a producer could also estimate, read from the results file (never from the
   page). Leave none out. Each has the identity fields (`metric`, `unit_concept`, `period`,
   `time_basis`, `conditions.basis`, `conditions.program`, and `conditions.fy` for a fiscal
   year), `value_raw` as the file prints it, a `normalization`, and `provenance`. State each in
   PolicyEngine's orientation for its metric (`scorecard_db/signs.py` `ORIENTATION`), with
   `sign: -1` and `sign_basis` if the file prints it the other way. A household calculator
   declares `"calculator": {"reason": "..."}`, pins no estimates, and records
   `results_pins: []`.
3. Set the search's `results_pins` to what `scorecard_db.comparables pins
   analysis-{country}-{slug}` prints.

### For a re-harvest or a search before a push (reharvest or prepromotion)

1. Append a search to `sources/analysis-{country}-{slug}/search_log.json`: `kind: {kind}`,
   today's date (after publication and after the first search), `results_pins` from
   `scorecard_db.comparables pins`, and one entry for every producer on
   `data/comparables/producers.json` for {country} added on or before today.
2. If the analysis's results file has changed since the last search, move the old estimates to
   `superseded_estimates` with `superseded_on`, and pin the new ones.
3. Stage only what earlier searches did not find (check `claims_staged.jsonl` and the earlier
   searches' notes first).

### Every search

4. Search every producer in the search entry, in list order. Run its `search_hints` combined
   with the search terms, and check the places `where_to_look` names as well as search results.
   Log `found`, `none_found`, `found_not_staged` or `not_applicable` with the queries run and
   pages checked. `not_applicable` only when the producer's `applies_to` excludes the scope.
   Never skip `open_search` or `academic`. A listed producer's estimate is logged under its own
   entry, never under `open_search`.
5. Trace every figure to its producer's own publication. Download each primary into a new empty
   directory outside this repository, `shasum -a 256` it, and add a `manifest.jsonl` line. A
   figure whose primary you cannot read (press-only, FOI with no published response) is
   `found_not_staged` with a note saying what it is and where it was seen, never a claim.
6. Stage each number as one line of `claims_staged.jsonl`, with the fields the worked example
   uses. Of the harvest rules (`sources/harvest-uk-ab2025-2026-09-24/README.md`), verbatim
   values (1), registered vocabulary, named baselines (7) and unreadable primaries (8) apply;
   `measure_key` and `fiscal_event` do not.
   - `value_raw` as printed, a registered `normalization` whose scale matches the printed one,
     and a `quote` that prints the value as a whole number with its sign. A printed range is two
     claims (`range_low`, `range_high`) sharing a `conditions.range_group`.
   - The sign convention in `conditions.sign_convention`, starting `positive =` and saying one
     thing, in words `signs.py` reads (the skill lists them, with US phrasings).
   - The identity fields, the world it scores, attribution, benchmark class, and the
     publication's locator.
7. Link each claim to the PolicyEngine estimate it matches (`compare_to`: the same quantity,
   identity and baseline; `across_worlds` with a reason and basis if the worlds differ). A claim
   near an estimate that is a different quantity (net beside static, a fiscal year beside a
   calendar year) names it in `nearest_estimate`, gives `pe_missing`, and gets a
   `concept_mismatch` annotation with a basis. Any other claim gives `pe_missing`.

   **Never** do these to keep a gap from being compared: leave a published figure out of
   `pe_estimates`; set a metric or unit to null when an estimate covers the quantity; stage a
   printed figure as `approx_chart_reading`; choose a period, time basis, basis or programme to
   avoid a match; label an explained miss `concept_mismatch`.
8. Run `scorecard_db.comparables check sources/analysis-{country}-{slug}` until it passes, apart
   from unexplained gaps, and `scorecard_db.comparables report analysis-{country}-{slug} --since
   {date}`. For every gap over the threshold, find the cause: read the analysis's code and data,
   the producer's method, and open issues (microcosm, policyengine-{country}, the analysis repo).
   Write an annotation that cites a basis you read. If you cannot find one:
   - prepublish: leave the gap unexplained. Do not invent a cause. CI stays red, which is
     correct: the analysis is not ready to publish.
   - backfill, reharvest or prepromotion: add a `pending` annotation, open an issue for the owner
     on the analysis's repository with the producer, the figures, the gap and what you checked,
     put it in `tracking_issue`, and write the cause as "Unexplained; tracked in <issue>" with the
     issue as the basis. For prepromotion, the push stays blocked until the cause is written.
9. Land it:

   ```bash
   PYTHONPATH=. uv run python -m scorecard_db.comparables index
   rm -f data/scorecard.db && PYTHONPATH=. uv run python -m scorecard_db.build_db data/scorecard.db
   PYTHONPATH=. uv run python -m scorecard_db.export_populations data/scorecard.db
   for f in lanes.json populations.json comparison.json exhibits.json; do cp data/$f app/public/data/$f; done
   PYTHONPATH=. uv run --with pytest --with hypothesis --with pypdf --with pyyaml --with numpy --with psutil --with rfc8785==0.1.4 --with jsonschema pytest tests/test_comparables.py tests/test_export_populations.py tests/test_harvest_ingest.py -q
   ```

   Commit everything the build rewrites (`git status` clean), push, and open a draft PR titled
   "Comparables for {title}", even when a gap is unexplained; its body states every gap and its
   status.

## Report

Write to the output file:

- the PR URL and head commit;
- one line per producer: result, claims staged, and for `found_not_staged` what and why;
- every compared claim: producer, value, the PolicyEngine estimate, the gap, and the annotation
  (or "unexplained");
- every claim set beside a nearest estimate, and why;
- the issues opened;
- for prepromotion, what `scorecard_db.comparables fresh analysis-{country}-{slug} --on {push
  date}` prints;
- anything you could not check, stated plainly.

Do not merge. Do not edit policyengine-app-v2. A person reviews the PR with the skill's reviewer
checklist first: every published figure pinned, each `pe_missing` true, each basis supporting
its cause, `none_found` spot-checked, hashes recomputed.
