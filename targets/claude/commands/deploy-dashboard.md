---
description: Deploys a PolicyEngine dashboard to Vercel (and optionally Modal) and registers it in the app
---

# Deploying dashboard: $ARGUMENTS

Deploy a completed PolicyEngine dashboard to production. Run this AFTER merging your feature branch into `main`.

**Precondition:** The user should be on the `main` branch with a clean working tree and the dashboard code merged.

## Skills Used

- **policyengine-tools** — Vercel frontend deployment (all dashboards) and Modal backend deployment (only if `custom-modal` pattern)

## Step 1: Verify Prerequisites

```bash
# Check we're on main
git branch --show-current

# Check for clean working tree
git status

# Verify build passes
bun install --frozen-lockfile && bun run build && bunx vitest run
```

**If not on main:** Tell the user to merge their feature branch first:
> You're currently on branch `{branch}`. Please merge into `main` first:
> ```bash
> git checkout main
> git merge {branch}
> git push
> ```
> Then run `/deploy-dashboard` again.

**If build fails:** Report the error and STOP. Do not deploy broken code.

## Step 2: Read the Plan

```bash
cat plan.yaml
```

Extract:
- `dashboard.name` — for Vercel project and Modal app names
- `dashboard.zone_path` — for multi-zone host rewrite verification
- `data_pattern` — determines if Modal deploy is needed (`custom-modal` needs it; `precomputed`, `precomputed-csv`, and `policyengine-api` do not)
- `tech_stack.framework` — should be `react-nextjs` (env var prefix: `NEXT_PUBLIC_*`)
- `embedding.register_in_apps_json` — whether the dashboard is listed with research (`displayWithResearch`); its apps.json entry is needed either way
- `embedding.slug` — the URL slug for policyengine.org

### 2a. Pre-flight: check for existing host rewrites (informational)

If this dashboard has deployed before, the host may already route to it (`policyengine-app-v2/website/src/data/appZoneRoutes.ts`, which `website/next.config.ts` turns into rewrites). Check so we know whether Step 5 needs to add the route or it is already in place.

```bash
# Clone or pull the host repo
if [ ! -d /tmp/policyengine-app-v2 ]; then
  gh repo clone PolicyEngine/policyengine-app-v2 /tmp/policyengine-app-v2
fi
(cd /tmp/policyengine-app-v2 && git checkout main && git pull)

# Invoke the multi-zone validator in host-only mode to check all rewrite structure at once
# (beforeFiles placement, route + asset rewrite counts, destination format)
```

Spawn the `multizone-validator` agent with `TARGET_PATH=.` (current dashboard repo) and `HOST_CONFIG_PATH=/tmp/policyengine-app-v2/website/next.config.ts`. Record which host-check items PASS / FAIL — these feed into Step 5 below.

**Do NOT stop if host rewrites are missing.** For a brand-new dashboard, the host can't have rewrites yet because Vercel hasn't assigned a production URL. Step 5 handles adding them **after** the first deploy captures the URL.

## Step 3: Deploy Backend (if custom-modal)

**Only if `data_pattern: custom-modal`.** For every other pattern, skip to Step 4.

See the `policyengine-tools` skill (Pattern C: Modal gateway + worker + polling) for the full Modal deployment reference.

### 3a. Authentication check (human gate)

```bash
modal token info
modal profile list
```

Present the output to the user. Verify:
- Active profile is `policyengine`
- Workspace is `policyengine`

**If authentication fails or shows wrong workspace:** Stop and display instructions:

> **Modal authentication required.** Your CLI is not configured for the `policyengine` workspace.
>
> Please run:
> ```bash
> modal token new --profile policyengine
> modal profile activate policyengine
> ```
>
> If you don't have access, ask a PolicyEngine workspace owner for an invite.

**Do NOT proceed until `modal token info` shows `Workspace: policyengine`.**

**If authentication succeeds**, use `AskUserQuestion` to confirm before proceeding:

```
question: "Modal is authenticated to the policyengine workspace. Proceed with deployment?"
header: "Modal auth"
options:
  - label: "Proceed"
    description: "Continue to environment selection and deploy"
  - label: "Cancel"
    description: "Stop deployment"
```

### 3b. Environment selection (human gate)

Use `AskUserQuestion` to select the Modal environment:

```
question: "Which Modal environment should this deploy to?"
header: "Environment"
options:
  - label: "main (Recommended)"
    description: "Production — policyengine--app-func.modal.run"
  - label: "staging"
    description: "Pre-production testing — policyengine-staging--app-func.modal.run"
  - label: "testing"
    description: "Development/CI — policyengine-testing--app-func.modal.run"
```

### 3c. Deploy

```bash
# Guard against env var override
unset MODAL_TOKEN_ID MODAL_TOKEN_SECRET

# Deploy to the selected environment
modal deploy modal_app.py --env SELECTED_ENV
```

### 3d. Verify endpoint

Construct the URL from the app name and function name in `modal_app.py`:

- Pattern: `https://policyengine--APP_NAME-FUNCTION_NAME.modal.run`
- With non-main environment: `https://policyengine-ENV--APP_NAME-FUNCTION_NAME.modal.run`

```bash
# Health check (if endpoint exists)
curl -s -w "\n%{http_code}" https://policyengine--DASHBOARD_NAME-health.modal.run

# Test the calculation endpoint
curl -s -X POST https://policyengine--DASHBOARD_NAME-calculate.modal.run \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

**If deploy fails:** Report error and STOP. See the `policyengine-tools` skill's Modal deployment guidance.

### 3e. Set API URL in Vercel

After successful Modal deploy, set the API URL as a Vercel environment variable.

```bash
vercel env add NEXT_PUBLIC_API_URL production
# Enter: https://policyengine--DASHBOARD_NAME-calculate.modal.run
```

## Before Step 4: comparables review

Run `/comparables-review` now, before the frontend deploy and the host wiring, whatever `embedding.register_in_apps_json` says. Step 5b makes the dashboard public at `policyengine.org/<zone_path>`, and app-v2's CI requires every app route to belong to a research entry that carries a `comparables` block naming a complete record in PolicyEngine/policyengine-scorecard. The review searches every producer for external estimates of the dashboard's figures, records them in the scorecard and explains any gap over the threshold (`policyengine-comparables-review` skill). Merge the scorecard PR before opening the app-v2 PR in Step 5.

## Step 4: Deploy Frontend to Vercel

See the `policyengine-tools` skill ("Deployment gotchas") for the full Vercel deployment reference.

```bash
# Link to Vercel under PolicyEngine team (if not already linked)
vercel link --scope policy-engine

# Deploy to production
vercel --prod --yes --scope policy-engine
```

If a Modal backend was deployed in Step 3, force-rebuild to pick up the new env var:
```bash
vercel --prod --force --yes --scope policy-engine
```

Capture the production URL from the output.

Verify the deployment:
```bash
curl -s -o /dev/null -w "%{http_code}" https://VERCEL_PRODUCTION_URL/
```

**IMPORTANT:** Use the auto-assigned Vercel production URL, not a custom alias. Custom aliases may have deployment protection issues.

## Step 5: Wire the zone into the host (policyengine-app-v2)

After the Vercel deploy in Step 4, we have a production URL. Now wire the zone into `policyengine-app-v2` so it's reachable at `policyengine.org/<zone_path>`. This is a PR to `PolicyEngine/policyengine-app-v2`.

Two parts, both required, in the same PR:

1. **The zone route** in `website/src/data/appZoneRoutes.ts`, which makes the zone reachable at `policyengine.org/<zone_path>`.
2. **The apps.json entry** with its `comparables` block. app-v2's tests fail any page the site proxies to another deployment that is not a research app's page (they read the evaluated rewrites, so a route added straight to `next.config.ts` is caught too), so the entry is not optional.

### 5a. Create the PR branch

```bash
# Clone app-v2 if not already available
if [ ! -d /tmp/policyengine-app-v2 ]; then
  gh repo clone PolicyEngine/policyengine-app-v2 /tmp/policyengine-app-v2
fi

cd /tmp/policyengine-app-v2
git checkout main
git pull
git checkout -b wire-DASHBOARD_NAME-zone
```

### 5b. Add the zone route to `website/src/data/appZoneRoutes.ts`

Add one entry to `appZoneRoutes` (use `VERCEL_PRODUCTION_URL` captured from Step 4, e.g. `my-dashboard-policy-engine.vercel.app`). `next.config.ts` turns it into the page rewrite and the `/:path*` rewrite for deeper pages:

```ts
{
  source: "<zone_path>",
  destination: "https://<VERCEL_PRODUCTION_URL><zone_path>",
},
```

For a root-served zone (no `basePath`), map the destination to the zone root: `"https://<VERCEL_PRODUCTION_URL>"`. If the zone sets `assetPrefix: '/_zones/<dashboard.name>'`, also add its asset rewrite (`/_zones/<dashboard.name>/:path*` to the same path on the deployment) where the file's other asset routes are. See the `policyengine-tools` skill for the two valid patterns: path-mounted and root-served.

### 5c. Add the apps.json entry

Add to `app/src/data/apps/apps.json`, with the block that `python -m scorecard_db.comparables record analysis-<country>-<slug>` printed in the comparables review before Step 4:

```json
{
  "type": "iframe",
  "slug": "SLUG",
  "title": "TITLE",
  "description": "DESCRIPTION",
  "source": "https://<VERCEL_PRODUCTION_URL><zone_path>",
  "tags": ["COUNTRY", "policy", "interactives"],
  "countryId": "COUNTRY",
  "displayWithResearch": true,
  "image": "SLUG-cover.png",
  "date": "CURRENT_DATE 12:00:00",
  "authors": ["AUTHOR_SLUG"],
  "comparables": { "...": "the block /comparables-review printed" }
}
```

`source` is the deployment the zone route proxies to, as the existing zone dashboards record it. With `embedding.register_in_apps_json: false`, keep the entry but set `"displayWithResearch": false`: it leaves the research listing, but the `policy` tag still makes it a research entry, so it still needs the block. Then run `bun run scripts/build-analysis-routes.ts` in `website/` and commit the regenerated `website/src/data/analysisRoutes.json` (a test fails while it is stale).

Use `AskUserQuestion` to gather required metadata:

```
question: "What is the author slug for the apps.json entry? (Check existing entries in apps.json for format, e.g., 'max-ghenis')"
header: "Author"
options: [] (free text — let the user type via "Other")
```

If `displayWithResearch: true`, also ask:

```
question: "Do you have a cover image for the apps.json listing?"
header: "Cover image"
options:
  - label: "I'll provide one"
    description: "You'll give me the image file or path"
  - label: "Skip for now"
    description: "Use a placeholder — you can add a cover image later"
```

### 5d. Commit and open the PR

```bash
git add website/src/data/appZoneRoutes.ts app/src/data/apps/apps.json website/src/data/analysisRoutes.json
git commit -m "Wire DASHBOARD_NAME zone"
git push -u origin wire-DASHBOARD_NAME-zone

gh pr create --repo PolicyEngine/policyengine-app-v2 \
  --title "Wire DASHBOARD_NAME zone" \
  --body "Adds the zone route and apps.json entry so DASHBOARD_NAME is reachable at policyengine.org/COUNTRY/SLUG.

Zone URL: VERCEL_PRODUCTION_URL
Public path: /COUNTRY/SLUG
Comparables: the scorecard record named in the entry's block"
```

The app-v2 PR's comparables gate checks, on the day it runs, that the block's search is no more than 30 days old, compared the results the dashboard reads now, and has no gap pending. If the PR waits longer than that, run a new search and update the block.

## Step 6: Smoke Test

Direct-URL checks can run immediately. Public-path checks require the Step 5 PR to merge first.

Immediate (after Step 4):

1. **Direct zone URL:** Visit `https://VERCEL_PRODUCTION_URL/<zone_path>`, verify the dashboard loads
2. **Hash sync:** Test that URL parameters work (add `#income=50000` etc.) and survive refresh
3. **Country detection (if supported):** Test with `#country=uk`

After Step 5 PR merges:

4. **Public path via host:** Verify the dashboard loads at `policyengine.org/COUNTRY/SLUG` (served through host rewrites, not an iframe)
5. **Assets load:** Open DevTools → Network, refresh, confirm all `_next/static/*` assets return 200. For static-export zones, verify `/_zones/<dashboard.name>/*` requests reach the zone.
6. **Shared chrome (if using ui-kit):** Verify Header/Footer render consistently with the rest of `policyengine.org`

## Step 7: Report

Present deployment summary to the user:

> ## Dashboard deployed
>
> - **Zone URL:** VERCEL_PRODUCTION_URL
> - **Public path (after host PR merges):** policyengine.org/COUNTRY/SLUG
> - **Vercel project:** DASHBOARD_NAME
> [If custom backend:]
> - **API endpoint:** https://policyengine--DASHBOARD_NAME-calculate.modal.run
> - **Modal environment:** SELECTED_ENV
> - **Host-wiring PR:** PR_URL (adds rewrites, and apps.json entry if applicable)
>
> ### Verify
> - [ ] Dashboard loads at the zone URL
> - [ ] Calculations work (or stubs respond correctly)
> - [ ] Hash parameters are preserved on refresh
> - [ ] After host-wiring PR merges, dashboard loads at policyengine.org/COUNTRY/SLUG
> - [ ] After host-wiring PR merges, assets (`_next/static/*`) load with 200 status

## Error Recovery

| Issue | Fix | Reference |
|-------|-----|-----------|
| Vercel deploy fails | Check `vercel.json` config, ensure project builds | `policyengine-tools` |
| Modal deploy fails | Check Python deps, Modal auth, function timeouts | `policyengine-tools` |
| Wrong Modal workspace | `modal profile activate policyengine` | `policyengine-tools` |
| 404 on Vercel URL | Wait 30s for propagation, check Vercel dashboard | `policyengine-tools` |
| API returns errors | Check Modal logs: `modal app logs DASHBOARD_NAME` | `policyengine-tools` |
| Hash sync broken | Check postMessage calls in embedding.ts | `policyengine-tools` |
