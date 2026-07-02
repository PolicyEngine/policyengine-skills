# When to use what

The PolicyEngine plugin ships 18 slash commands, 46 agents, and 53 skills. Most days you'll only use 3-5 of them. This guide maps common work to the right entry point.

## Quick decision matrix

| I want to... | Reach for | Then usually |
|---|---|---|
| Score a proposed reform (revenue, poverty, distribution) | `/analyze-policy` | Verdict routes to archive + optional issue/PR |
| Implement a new state benefit program | `/encode-policy-v2` | `/review-program` → `/fix-pr` → `/create-pr` |
| Add a new policy reform to an existing program | `/encode-reform` | `/review-program` → `/create-pr` |
| Backdate parameters to earlier years | `/backdate-program` | `/create-pr` |
| Review a PR (code + PDF-cited values) | `/review-program` | `/fix-pr` if findings; else `/create-pr` |
| Apply reviewer fixes to a PR | `/fix-pr` | `/create-pr` |
| Turn a working branch into a PR | `/create-pr` | CI + review |
| Verify state tax parameter values against official PDFs | `/audit-state-tax` | `/fix-pr` if drift found |
| Create a policy dashboard (React tool) | `/create-dashboard` | `/deploy-dashboard` |
| Deploy a completed dashboard | `/deploy-dashboard` | Live at Vercel |
| Scaffold a new interactive tool | `/new-tool` | dev + `/deploy-dashboard` |
| Add a UI component to `@policyengine/ui-kit` | `/create-new-component` | `/create-pr` |
| Audit an SEO story on a web property | `/audit-seo` | Fix + `/create-pr` |
| Audit a multi-zone Next.js app | `/audit-multizone` | Fix + `/create-pr` |
| Write unit tests for source files | `/write-tests` | `/create-pr` |
| Generate a social image / social copy from a blog post | `/generate-content` | Post to socials |
| See what's in the dashboard-builder toolkit | `/dashboard-overview` | Use one of the dashboard commands |
| Add a themed spinner verb to your Claude session | `/setup-verbs` | Ambient |

## Decision tree (not sure where to start)

**Q1: Is this about a POLICY change (parameters, formulas) or a PROJECT (dashboard, tool, UI)?**

- **Policy** → Q2
- **Project** → Q4

**Q2: Do you want to know the IMPACT of the change, or IMPLEMENT it in the model?**

- **Impact** (revenue, poverty, distribution): `/analyze-policy`
- **Implement** → Q3

**Q3: Are you adding a NEW program or a REFORM to an existing program?**

- **New program** (state TANF variant, new state credit, new federal benefit): `/encode-policy-v2`
- **Reform to existing** (raise a cap, add a phase-out): `/encode-reform`
- **Backdate parameters** (fill in historical years): `/backdate-program`

**Q4: Dashboard, standalone tool, or UI component?**

- **Dashboard** (multi-page policy analysis app): `/create-dashboard` → `/deploy-dashboard`
- **Standalone tool** (interactive calculator, embedded widget): `/new-tool`
- **UI component** in the shared kit: `/create-new-component`

**Q5: PR/review adjacent?**

- **Review someone else's PR**: `/review-program`
- **Fix reviewer feedback on your PR**: `/fix-pr`
- **Ship a branch as a PR**: `/create-pr`

## Skills to almost always load

These get pulled in automatically by their trigger keywords, but useful to know exists:

- **`policyengine-{us,uk,canada}`** — country model knowledge, loaded whenever the user's question mentions a country's tax/benefit specifics
- **`policyengine-writing`** — style for any blog post, PR description, or research report
- **`policyengine-standards`** — CI, formatters, PR standards (uv, ruff, prettier, pre-commit)
- **`policyengine-code-style`** — formula-writing patterns (direct returns, eliminate intermediate variables, no hardcoding)

## Skills for specific work

**Microsimulation / population analysis** (cost, poverty, distributional):
- `policyengine-microsimulation` — always the first skill for population-level questions
- `policyengine-simulation-mechanics` — deeper API patterns
- `policyengine-district-analysis` — congressional district impacts
- `microdf` — weighted survey dataframe utilities

**Implementing programs** (adding new variables, parameters, formulas):
- `policyengine-variable-patterns` — variable creation, naming, no-hardcoding
- `policyengine-parameter-patterns` — YAML structure, federal/state separation
- `policyengine-vectorization` — NumPy `where`/`select` patterns
- `policyengine-aggregation` — summing across entities (person → tax unit → household)
- `policyengine-period-patterns` — YEAR vs MONTH definition periods
- `policyengine-testing-patterns` — YAML integration tests
- `policyengine-reform-patterns` — reform-dict syntax

**Data pipeline / calibration**:
- `microimpute` — imputation for survey data (used in policyengine-us-data)
- `microcalibrate` — weight calibration to hit population targets
- `l0` — sparsity regularization

**Frontend / dashboards**:
- `policyengine-design` — design tokens, typography, chart standards
- `policyengine-tailwind-shadcn` — component patterns
- `policyengine-recharts` — chart primitives
- `policyengine-interactive-tools` — embed-friendly tool patterns
- `policyengine-ui-kit-consumer` — using `@policyengine/ui-kit`

**API integration**:
- `policyengine-python-client` — installing + calling the API from Python
- `policyengine-api-v2` — API internals (only when working on the API itself)

## Common workflows (recipes)

### "I want to score a reform and publish it as a blog post"

```
1. /analyze-policy "reform description" --horizon 10
2. Read verdict + archive at analyses/YYYY-MM-DD-slug.md
3. If PASS or PASS-WITH-CORROBORATION:
   /generate-content --source analyses/YYYY-MM-DD-slug.md
   → produces social image + copy
4. Manually drop the analysis body into policyengine-app/src/posts/articles/<slug>.md
5. /create-pr
```

### "I want to add a new state benefit program"

```
1. Load context: mention the state and program in your first message so
   policyengine-us + policyengine-variable-patterns + policyengine-parameter-patterns
   get auto-triggered
2. /encode-policy-v2 "state XX, program YY"
3. /review-program to catch validator issues
4. /fix-pr for the review comments
5. /create-pr — waits for CI, marks ready
```

### "I want to build a dashboard for a specific reform question"

```
1. /create-dashboard "A dashboard showing X impacts of Y reform by Z"
2. Dashboard scaffolds Next.js + Tailwind + PE design tokens
3. Iterate the frontend / backend agents produce
4. /deploy-dashboard when ready
```

### "I want to backdate a parameter for accurate historical analysis"

```
1. /backdate-program "state XX program YY, years 2015-2020"
2. Agent pulls historical values from official sources
3. /create-pr
```

### "I want to know what's in the dashboard toolkit"

```
1. /dashboard-overview  (this is a listing command, not a workflow)
```

## Tests — realistic scenarios that this guide should answer

| # | Scenario | Guide answer | Match? |
|---|---|---|---|
| 1 | Analyst wants to score raising the CTC by $500 | `/analyze-policy` | ✅ |
| 2 | Engineer wants to add Colorado's new EITC match | `/encode-policy-v2` | ✅ |
| 3 | Engineer got PR review comments to address | `/fix-pr` | ✅ |
| 4 | User wants a dashboard showing SNAP eligibility by county | `/create-dashboard` | ✅ |
| 5 | Researcher wrote a blog post and wants social assets | `/generate-content` | ✅ |
| 6 | Reviewer wants to check a state-tax PR's values vs the source PDF | `/audit-state-tax` | ✅ |
| 7 | Frontend engineer wants a new button variant in the ui-kit | `/create-new-component` | ✅ |
| 8 | Someone finished a working branch and needs to open a PR | `/create-pr` | ✅ |
| 9 | Dev wants to make sure a web property has good SEO | `/audit-seo` | ✅ |
| 10 | Analyst wants historical values for a program that only has 2024 data | `/backdate-program` | ✅ |
| 11 | User wants to know how the tools relate | `/dashboard-overview` (listing) or read this guide | ✅ |
| 12 | Dev wants to write pytest tests for a Python file | `/write-tests` | ✅ |

## Gaps identified while writing this guide

**1. No entry point for "explore the model" or "run a household calculation."**
Users who want to check "what would this specific household get under this reform" don't have a slash command. Today they'd have to load `policyengine-us` skill and write ad-hoc Python. Candidate follow-up: `/household-calc` command that wraps the household calculation flow.

**2. `/encode-policy-v2` vs `/encode-reform` boundary is fuzzy.**
Both orchestrate multi-agent workflows for adding parametric change. The distinction is "new program" vs "reform to existing program" — but the boundary is judgment. Candidate follow-up: `/encode-policy-v2` should detect and delegate to `/encode-reform` when the target program already exists, so users don't have to pick.

**3. `/create-dashboard` and `/new-tool` scope overlap.**
Both build a React app. `/new-tool` is more of a scaffold (blank canvas + design tokens); `/create-dashboard` is a full multi-agent workflow with plan/scaffold/implement/validate phases. Users may pick the wrong one. Candidate follow-up: clarify in the descriptions that `/new-tool` is a bootstrapper for a specific interactive calculator, `/create-dashboard` is for multi-page dashboards.

**4. No entry point for "translate this bill into a reform-dict."**
The `policy-text-researcher` agent does this internally in `/analyze-policy`, but there's no standalone command. Users doing exploratory reform-dict building have to run `/analyze-policy --skip-microsim` as a workaround. Candidate follow-up: expose `/text-to-reform` as a standalone command that stops after Stage 2.

**5. No command for "consult PE's prior research on this topic."**
`prior-scores-finder` (an agent) already searches PE's research catalog + Tier 2/3 externals. It's only invoked inside `/analyze-policy`. Users who want to "just find prior work" have no direct entry. Candidate follow-up: `/prior-scores <topic>` command.

**6. `/deploy-dashboard` is dashboard-specific; there's no generic `/deploy` for tools.**
`/new-tool` bootstraps a Next.js tool, but deploying it requires manual Vercel steps. Candidate follow-up: extend `/deploy-dashboard` to auto-detect tool vs dashboard.

**7. `/setup-verbs` is a one-time-per-session utility that doesn't fit the workflow model.**
It's a config tweak (installs themed spinner verbs). Not really a workflow. Fine to keep but its home is unusual. Candidate follow-up: none — probably fine as-is.

**8. No entry point for "consult the archive" or "did we already analyze this?"**
`scripts/analyses_kb.py` exists and duplicate detection works from CLI, but there's no `/prior-analysis` slash command. Candidate follow-up: `/prior-analysis` that wraps `scripts/analyses_kb.py` search.

**9. `/audit-multizone` is very specific (multi-zone Next.js apps).**
Useful when working on `policyengine-app-v2` (which uses multi-zone), essentially never useful elsewhere. Not a gap, but flagging it's a niche entry point.

**10. `/dashboard-overview` is a discovery/listing command — this guide is the general-purpose version of that.**
Consider whether to build a `/overview` slash command that displays this file, or leave it as a doc.
