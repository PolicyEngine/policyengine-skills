# PolicyEngine Ecosystem Dashboard

A React dashboard that maps every skill, agent, command, and bundle in this
repo — surfacing duplication, dependencies, and coverage gaps so the
ecosystem stays coherent as it grows.

## Why it exists

`policyengine-skills` is the source of truth for ~50 skills, ~40 agents,
~20 commands, and 9 bundles. They overlap, depend on each other in opaque
ways, and a single skill can ship in multiple bundles. The dashboard makes
all of that legible in one place.

## Views

- **Overview** — counts, top-referenced skills/agents, bundle composition.
- **Find** — task-based internal registry for "what should I use?" decisions,
  prioritizing recommended commands and flagging direct agent use.
- **Catalog** — searchable, filterable table of every artifact. Click any
  row to see registry status, owner, description, triggers, dependencies,
  and overlap candidates.
- **Duplicates** — TF-IDF cosine similarity over name + description +
  triggers + body for every artifact pair. Filter by kind, threshold, and
  same-kind vs. cross-kind to find merge candidates.
- **Workflows** — topic-organized workflow cards showing commands, agent
  chains, and reference skills.
- **Repos** — every active PolicyEngine org repo, classified and linked to
  skills, agents, and commands inferred to cover it.
- **Gaps** — orphaned skills, uncalled agents, broken bundle refs, missing
  descriptions/triggers, and a bundle coverage matrix.
- **Cleanup** — deprecated, use-with-care, experimental, and internal-only
  artifacts so maintainers can decide what to remove, merge, or document.

## How the data is built

`scripts/build_manifest.py` (at the repo root) walks:

- `skills/**/SKILL.md`
- `targets/claude/agents/**/*.md`
- `targets/claude/commands/*.md`
- `bundles/*.json`

It parses YAML frontmatter, extracts trigger phrases, infers references
(commands → agents/skills, agents → skills) from body text, derives internal
registry metadata (status, owner, recommended use, replacements), computes
overlap pairs via TF-IDF cosine, and emits
`dashboard/src/data/manifest.json` — the single file the React app reads.

The script has **zero third-party dependencies** so it runs on plain
`python3`. It is automatically invoked as a `predev` / `prebuild` hook in
`package.json`, so the manifest is always fresh when you start the app.

## Running locally

```bash
cd dashboard
npm install
npm run dev      # http://localhost:5180
```

Build for static hosting:

```bash
npm run build
```

The output in `dist/` is a fully static site — drop it behind any web host.

## Updating the manifest manually

```bash
python3 scripts/build_manifest.py
```

Run that whenever you add or rename artifacts and you want to refresh the
dashboard without restarting the dev server.

## Refreshing the GitHub org inventory

`scripts/policyengine_repos.json` caches the list of every active repo in
the PolicyEngine GitHub org. The dashboard uses this to surface coverage
gaps (repos with no skill/agent/command supporting them). Refresh it when
the org gains new repos:

```bash
gh repo list PolicyEngine --limit 300 \
  --json name,description,isArchived,visibility,pushedAt \
  | python3 -c "import json,sys; d=[{'name':r['name'],'description':r['description'] or '','visibility':r['visibility'],'pushed_at':r['pushedAt']} for r in json.load(sys.stdin) if not r['isArchived']]; print(json.dumps(d, indent=2))" \
  > scripts/policyengine_repos.json
python3 scripts/build_manifest.py
```

Each repo is auto-classified (country-model, platform, library,
long-lived-tool, interactive-instance, etc.). Add an override to
`REPO_KIND_OVERRIDES` in `scripts/build_manifest.py` if the heuristic
misclassifies something.

## What to read first

Open **Find** first when deciding what to use for a task. Use **Cleanup**
before creating a new artifact or wiring an agent directly. Open
**Duplicates** when consolidating overlapping skills, agents, or commands.
