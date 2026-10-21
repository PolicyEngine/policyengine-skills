---
description: Run the pre-publish comparables review for a dashboard or research post and record it in the scorecard
---

# Comparables review: $ARGUMENTS

Required before a dashboard or research post that publishes an estimate is added to
`apps.json` or `posts.json` in policyengine-app-v2. The app's CI checks the entry's
`comparables` block against the scorecard index for entries dated on or after its cutover.

Load the `policyengine-comparables-review` skill and follow it. In short:

1. Identify the analysis from `$ARGUMENTS`: its policyengine.org slug, country, kind (`app` or
   `post`), the repository and commit its page builds from, and the results file. If the
   analysis publishes no estimate, stop: its entry declares
   `{"status": "no_estimate", "reason": "..."}` instead (not allowed for a `policy`-tagged
   entry).
2. In a PolicyEngine/policyengine-scorecard worktree off `origin/main`, scaffold
   `sources/analysis-<country>-<slug>/`, pin the analysis's figures, and search every producer
   the skeleton lists, logging each result.
3. Stage each estimate found under the harvest rules, link it to the figure it matches, and
   run `python -m scorecard_db.comparables check`. Explain every gap over the threshold with a
   cited cause, or stop and report it.
4. Regenerate the index, build and test, and open the scorecard PR. Once it merges, print the
   block with `python -m scorecard_db.comparables record analysis-<country>-<slug>` and add it
   to the app-v2 entry.

To run the search as a background job instead, fill the skill's
`references/subfleet-brief.md` and dispatch it as a research task. Review the staged claims
against their primaries before merging the scorecard PR.

## Arguments

`$ARGUMENTS`: the dashboard or post (its URL, slug, or repository), plus `--kind
prepublish|backfill|reharvest|prepromotion` (default `prepublish`). Use `prepromotion`
before a newsletter, social campaign, webinar or press push features an analysis that is
already published: the push needs a search within the scorecard's promotion window
(`python -m scorecard_db.comparables fresh <source> --on <push date>`).

## Related

- `/prior-scores`: benchmarking while the analysis is being built.
- `/deploy-dashboard`: Step 5c runs this review before the apps.json entry.
