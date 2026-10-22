---
description: Run the pre-publish comparables review for a dashboard or research post and record it in the scorecard
---

# Comparables review: $ARGUMENTS

Required before a dashboard or research post that publishes an estimate is added to
`apps.json` or `posts.json` in policyengine-app-v2, and before a newsletter, social campaign,
webinar or press push features an analysis already published. app-v2's CI checks every
research entry not on its list of entries live before the gate; the newsletters repo's CI
checks every analysis an edition links.

Load the `policyengine-comparables-review` skill and follow it. In short:

1. Identify the analysis from `$ARGUMENTS`: its policyengine.org slug, country, kind (`app` or
   `post`), the repository and commit its page builds from, and the results file. Only a post
   that is plainly not an analysis (an event, an announcement) may skip the review by declaring
   `{"status": "no_estimate", "reason": "..."}`; an app never may. A household calculator is
   searched, and declares `calculator` in its record instead of pinning estimates.
2. In a PolicyEngine/policyengine-scorecard worktree off `origin/main`, scaffold
   `sources/analysis-<country>-<slug>/` (or append a search to it), pin every figure the page
   publishes, and search every producer the skeleton lists, logging each result.
3. Stage each estimate found, compare it with the figure it matches or set it beside the
   nearest one with a stated mismatch, and run `python -m scorecard_db.comparables check`.
   Explain every gap over the threshold with a cited cause. Never hide a gap by leaving a
   figure out or relabelling a claim.
4. Build, commit everything the build rewrites, and open the scorecard PR; have it reviewed
   with the skill's checklist. Once it merges, print the block with
   `python -m scorecard_db.comparables record analysis-<country>-<slug>` and add it to the
   app-v2 entry.

To run the search as a background job instead, fill the skill's `references/search-brief.md`
and dispatch it to an agent with web search, a writable workspace and `gh` push access. Review
its PR before merging.

## Arguments

`$ARGUMENTS`: the dashboard or post (its URL, slug, or repository), plus `--kind
prepublish|backfill|reharvest|prepromotion` (default `prepublish`). Use `prepromotion`
before a newsletter, social campaign, webinar or press push features an analysis that is
already published: the push needs a search on the push date or in the scorecard's promotion
window before it, against the results the page reads now, with no gap pending
(`python -m scorecard_db.comparables fresh <source> --on <push date>`).

## Related

- `/prior-scores`: benchmarking while the analysis is being built.
- `/deploy-dashboard`: Step 5c runs this review before the apps.json entry.
