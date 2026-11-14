---
name: generate-content
description: Generate social images and posts from a blog post or announcement
arguments:
  - name: source
    description: URL or file path to the blog post/announcement
    required: true
  - name: audiences
    description: Comma-separated list of audiences (uk, us, global)
    default: "uk,us"
  - name: outputs
    description: Comma-separated list of outputs (social-image, social-copy, all)
    default: "all"
---

# Content generation command

Generate branded PolicyEngine content from a source blog post or announcement.

## What this command does

Orchestrates the content-generation pipeline through two dedicated agents:

1. `content-orchestrator` (agent) — parses the source, generates localized variants (UK/US spelling, references, framing), and renders the outputs (social images via Chrome headless, social copy for LinkedIn/X).
2. `neutrality-reviewer` (agent) — reviews the generated copy for advocacy language, speculation, or one-sided framing before publish. See `targets/claude/agents/shared/neutrality-reviewer.md`.

Before generating assets, the orchestrator determines whether the source concerns a PolicyEngine
analysis, including household calculators with no fixed estimates. This applies to canonical URLs,
deployment URLs and local files. It resolves each analysis being promoted to its scorecard record;
if a local file or other source does not identify the analysis, it asks for that identity. An
unrecognized link or missing record does not exempt the analysis.

For each record, fetch scorecard `origin` and run `PYTHONPATH=. uv run python -m
scorecard_db.comparables fresh analysis-<country>-<slug> --on <intended push date>` in a checkout of the updated
`origin/main`. The search must be within the promotion window, compare the current results and
leave no gap pending. If the record is absent, follow `policyengine-comparables-review` to create
its first search as `prepublish` if the analysis is not yet public, or `backfill` if it is already
published. For any unpublished analysis, complete the prepublish review and publication metadata
handoff before public promotion; do not append another `prepublish` or a `prepromotion` search
while `published` is null. After actual publication, run `/comparables-review --kind prepromotion`
only if freshness needs renewal. Merge the review and metadata into scorecard main, then fetch
and rerun `fresh`. Fetch and rerun it immediately before the push using the actual push date.
Resolve the analysis explicitly; automatic link checks do not establish complete coverage.

The command is the entry point; the agents own the mechanics. Loads `content-generation` skill for templates and `policyengine-writing` skill for the tone standard.

## Usage

```bash
# Generate all content for UK and US audiences
/generate-content --source https://policyengine.org/uk/research/policyengine-10-downing-street

# Generate only social images for UK
/generate-content --source ./blog-post.md --audiences uk --outputs social-image
```

## Output structure

```
output/
├── social/
│   ├── social-uk.png
│   └── social-us.png
└── copy/
    └── social-posts.md
```

## Required information

The command will prompt for any missing information:

- **Analysis identity**: Canonical page, source repository or scorecard source directory (`analysis-<country>-<slug>`) for each
  PolicyEngine analysis being promoted, including when the input is a local file
- **Push date**: Intended date the social posts will go out, used for comparables freshness
- **Headline**: Main announcement headline
- **Quote**: Pull quote for social image
- **Quote attribution**: Name and title of person quoted
- **Headshot URL**: URL to headshot image for quote block

## Customization

Edit the template in `skills/policyengine-content/templates/`:
- `social-image.html` - Social media image template
