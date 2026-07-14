# When to use what

The PolicyEngine plugin ships 19 slash commands, 46 agents, and 53 skills. Most days you'll only use 3-5 of them. This guide maps common work to the right entry point.

## Quick decision matrix

| I want to... | Reach for | Then usually |
|---|---|---|
| Run the whole chain for a topic: find a reform in the news → score → verify → publish | `/reform-pipeline` | Merge the bill-review PR or `/deploy-dashboard` |
| Score a proposed reform (revenue, poverty, distribution) | `/analyze-policy` | Verdict routes to archive + optional issue/PR |
| Calculate benefits/taxes for a single household | `/household-calc` | Adjust household, run again |
| Convert a bill / URL / description into a reform-dict | `/text-to-reform` | Submit to PE API or pass to `/analyze-policy` |
| Check whether we already analyzed this reform | `/prior-analysis` | Read the archived analysis or run fresh |
| Consult external scorekeepers (JCT/CBO/OBR/IFS/CRFB/TPC/etc.) | `/prior-scores` | Cite in your writeup |
| Implement a NEW state benefit program | `/encode-policy-v2` | `/review-program` → `/fix-pr` → `/create-pr` |
| Change parameters on an EXISTING program | `/encode-reform` | `/review-program` → `/create-pr` |
| Backdate parameters to earlier years | `/backdate-program` | `/create-pr` |
| Review a PR (code + PDF-cited values) | `/review-program` | `/fix-pr` if findings; else `/create-pr` |
| Apply reviewer fixes to a PR | `/fix-pr` | `/create-pr` |
| Turn a working branch into a PR | `/create-pr` | CI + review |
| Verify state tax parameter values against official PDFs | `/audit-state-tax` | `/fix-pr` if drift found |
| Create a multi-page policy analysis dashboard | `/create-dashboard` | `/deploy-dashboard` |
| Deploy a completed dashboard | `/deploy-dashboard` | Live at Vercel |
| Scaffold a single-purpose interactive tool | `/new-tool` | dev + `/deploy-dashboard` |
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

- **Impact — aggregate** (revenue, poverty, distribution across the population): `/analyze-policy`
- **Impact — one household** (what does this specific family get?): `/household-calc`
- **Just want the reform-dict, not the impact numbers**: `/text-to-reform`
- **Check what OTHER organizations have scored** (JCT / CBO / IFS / CRFB): `/prior-scores`
- **Check what PE has already analyzed**: `/prior-analysis`
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
| 13 | Analyst wants to check what a single family gets on SNAP | `/household-calc` | ✅ |
| 14 | Researcher wants to translate HR 1234 into a reform-dict without scoring it yet | `/text-to-reform` | ✅ |
| 15 | Analyst wonders "have we already analyzed the OBBBA SALT bump?" | `/prior-analysis` | ✅ |
| 16 | Researcher writing UK income-tax reform post; wants IFS + OBR + Resolution Foundation views | `/prior-scores --country uk` | ✅ |

## Gaps identified while writing this guide

Most gaps identified in the initial pass were filled in a follow-up PR. Remaining:

**1. `/setup-verbs` doesn't fit the workflow model.** It's a one-time config tweak (installs themed spinner verbs), not a workflow. Kept as-is because moving it would break existing users.

**2. `/audit-multizone` is niche.** Useful only when working on `policyengine-app-v2` (multi-zone Next.js app). Kept because it's cheap and the alternative would be inlining into `/audit-seo` which would confuse both.

**3. `/dashboard-overview` overlaps with this guide's role.** It lists the dashboard-builder toolkit; this guide covers the whole catalog. Both have distinct purposes — `/dashboard-overview` is a discovery listing, this guide is a decision matrix.

### Filled by follow-up commits (this PR)

- `/household-calc` — single-household calculation entry point
- `/text-to-reform` — Stage 1+2 of `/analyze-policy` as a standalone
- `/prior-analysis` — wraps `scripts/analyses_kb.py` search
- `/prior-scores` — wraps `prior-scores-finder` agent + scorekeepers registry
- `/encode-policy-v2` vs `/encode-reform` boundary clarified with pre-flight check
- `/create-dashboard` vs `/new-tool` boundary clarified in each command's description
