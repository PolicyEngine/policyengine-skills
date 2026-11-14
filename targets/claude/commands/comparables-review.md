---
description: Run the pre-publish comparables review for a dashboard, research post or tracker score and record it in the scorecard
---

# Comparables review: $ARGUMENTS

Required before a dashboard or research post is published or listed in `apps.json` or
`posts.json`, before a tracker score is dispatched through `/reform-pipeline`, and before a
newsletter, social campaign, webinar or press push features an analysis already published.
Calculators with no fixed estimates are included. app-v2 checks registry entries subject to
its gate; newsletter CI checks recognized analysis links. Route and redirect discovery has
gaps documented in the skill, so green CI does not replace resolving the analysis yourself.

Load the `policyengine-comparables-review` skill and follow it. In short:

1. Identify the analysis from `$ARGUMENTS`: its slug, country, registry kind (`app`, `post` or
   `tracker`), page URL, other serving URLs, the repository and commit its page builds from,
   and the results file. Resolve deployment URLs, redirects and local files to that identity;
   ask for the identity if a local source does not provide it. Only a post
   that is plainly not an analysis (an event, an announcement) may skip the review by declaring
   `{"status": "no_estimate", "reason": "..."}`; an app never may. A household calculator is
   searched, and declares `calculator` in its record instead of pinning estimates.
2. In a PolicyEngine/policyengine-scorecard worktree off `origin/main`, scaffold
   `sources/analysis-<country>-<slug>/` (or append a search to it), pin every figure the page
   publishes, and search every producer the skeleton lists, logging each result. For trackers,
   scaffold with `--kind app --slug <state>-<bill>`, then set `registry.kind: tracker` and the
   actual tracker URL: `scaffold` only accepts app/post. Keep `published: null` until public.
3. Stage each estimate found, compare it with the figure it matches or set it beside the
   nearest one with a stated mismatch, and run `python -m scorecard_db.comparables check`.
   Explain every gap over the threshold with a cited cause. Never hide a gap by leaving a
   figure out or relabelling a claim.
4. If `check` fails, commit the source record, gap table and diagnostics in a draft scorecard
   PR, preserving unexplained annotations. Defer index/database/feed builds, merge and
   publication until the errors are resolved. When it passes, build, commit everything the
   build rewrites and open the scorecard PR; have it reviewed with the skill's checklist;
   the validator cannot establish source truth. For apps/posts,
   once it merges, print the block with
   `python -m scorecard_db.comparables record analysis-<country>-<slug>` and add it to the
   app-v2 entry. For trackers, link the record and gap table in the bill-review PR instead.
5. Follow the skill's "Complete publication metadata" step: once deployed, land the serving
   URLs in `deployments` and the actual first-publication date in `published`, rebuild the
   index and feeds, merge the follow-up and verify each direct URL resolves to this record.
   For trackers, assign the date update to the bill-review publication owner before dispatch
   and complete it when the bill-review merge publishes the score, then verify `due` finds it.

To run the search as a background job instead, fill the skill's `references/search-brief.md`
and dispatch it to an agent with web search, a writable workspace and `gh` push access. Review
its PR before merging.

## Arguments

`$ARGUMENTS`: the dashboard, post, calculator or tracker score (its URL, slug, repository or
local source plus analysis identity), plus `--kind
prepublish|backfill|reharvest|prepromotion` (default `prepublish`). Use `prepromotion`
before a newsletter, social campaign, webinar or press push features an analysis that is
already published: the push needs a search on the push date or in the scorecard's promotion
window before it, against the results the page reads now, with no gap pending
(`python -m scorecard_db.comparables fresh <source> --on <push date>`).

## Related

- `/prior-scores`: benchmarking while the analysis is being built.
- `/deploy-dashboard`: Step 5c runs this review before the apps.json entry.
