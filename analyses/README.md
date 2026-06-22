# Analyses archive

Every `/analyze-policy` run lands here (by default) as a dated markdown file with frontmatter.

## Path resolution

The `report-logger` agent picks the archive directory in this order:

1. `--log-to archive:<path>` if explicitly passed
2. `$PWD/analyses/` if it exists (you're in a repo with an `analyses/` folder)
3. `$POLICYENGINE_ANALYSES_DIR` environment variable if set
4. `~/.policyengine/analyses/` (auto-created)

For users running this plugin against their own repos, set `POLICYENGINE_ANALYSES_DIR` once in your shell rc, OR create an `analyses/` folder in the repo you're working in.

## File naming

`YYYY-MM-DD-<jurisdiction>-<slug>.md`

Examples:
- `2026-06-19-us-arpa-ctc-restoration.md`
- `2026-06-12-ri-h7127-state-ctc.md`
- `2026-05-08-us-salt-cap-repeal.md`

## Frontmatter

Every archived analysis has YAML frontmatter for searchability:

```yaml
---
policy_id: 97759
date: 2026-06-19
jurisdiction:
  country: us
  state: null
title: ARPA-style federal CTC expansion (2026-2035)
verdict: PASS-WITH-NOTES
anchor_url: https://policyengine.org/us/research/restoration-of-the-american-rescue-plan-acts-expanded-child-tax-credit
tags: [ctc, federal, refundability, arpa]
issues_opened: []
---
```

Search by grep:

```bash
grep -l "verdict: INVESTIGATE" analyses/*.md
grep -l "state: ri" analyses/*.md
```

## What's NOT here

- Drafts for publication (those go in the analysis repo via `--log-to draft:...`)
- State-bill analyses being tracked in Supabase (those go via `--log-to tracker`)
- GitHub issues opened by the logger (those are referenced by issue number in the frontmatter's `issues_opened` list)
