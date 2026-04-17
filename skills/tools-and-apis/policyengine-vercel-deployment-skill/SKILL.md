---
name: policyengine-vercel-deployment
description: Deploying PolicyEngine frontend apps to Vercel - naming, scope, team settings
---

# PolicyEngine Vercel Deployment

Standard patterns for deploying frontend apps (interactive tools, dashboards, static sites) to Vercel under the PolicyEngine team.

## Deployment

### Team and scope

All PE apps deploy under the `policy-engine` Vercel team:

```bash
vercel link --scope policy-engine
vercel --prod --yes --scope policy-engine
```

### Naming convention

Projects use the pattern `policyengine--{repo-name}`:

```
policyengine--marriage.vercel.app
policyengine--aca-calc.vercel.app
policyengine--state-legislative-tracker.vercel.app
```

Vercel auto-assigns a random production URL (e.g., `marriage-zeta-beryl.vercel.app`). Use that in apps.json as the source URL since custom aliases may have deployment protection issues.

### First deploy

```bash
cd my-project

# Link to team (creates .vercel/)
vercel link --scope policy-engine

# Deploy
vercel --prod --yes
```

### Subsequent deploys

```bash
vercel --prod --yes --scope policy-engine
```

### Environment variables

For apps with API backends (e.g., Modal):

```bash
# Set env var (Next.js uses NEXT_PUBLIC_* prefix)
vercel env add NEXT_PUBLIC_API_URL production

# Must force-redeploy after changing env vars
vercel --prod --force --yes --scope policy-engine
```

Next.js apps access env vars via `process.env.NEXT_PUBLIC_API_URL`.

### Verify deployment

```bash
curl -s -o /dev/null -w "%{http_code}" https://your-app.vercel.app/
# Should return 200
```

### Common issues

**Deployed to personal account:** If `vercel --prod` goes to your personal account, delete `.vercel/` and re-link:
```bash
rm -rf .vercel
vercel link --scope policy-engine
vercel --prod --yes
```

**Deployment protection (401):** Team deployment protection may block unauthenticated access to alias URLs. Use the auto-assigned production URL instead, or configure in Vercel dashboard > Settings > Deployment Protection.

**Generic project names:** Never use generic names like `app` or `site` — they can steal domains from other projects. Always use descriptive names.

### vercel.json

Must be at repo root. For Next.js static exports, configure rewrites as needed:
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

## Multi-zone deployments

PolicyEngine tools deploy as **Next.js multi-zones** mounted behind `policyengine.org`. The host (`policyengine-app-v2/website/`) proxies specific paths to each zone's Vercel deployment via `rewrites` in `beforeFiles`.

Before deploying a new tool, make sure you've read `policyengine-interactive-tools-skill` → "Multi-zone integration (preferred)". The Vercel-facing implications:

- **Project naming is mandatory**: `policyengine--<repo-name>`. The host rewrite destination is built from this.
- **Static-export zones need a `vercel.json` self-rewrite** so the zone's own preview can serve prefixed assets:
  ```json
  {
    "framework": "nextjs",
    "rewrites": [
      { "source": "/_zones/<repo-name>/_next/:path*", "destination": "/_next/:path*" }
    ]
  }
  ```
- **Host rewrites must land before deploy** — add to `policyengine-app-v2/website/next.config.ts` in `rewrites().beforeFiles`. `/deploy-dashboard` has a pre-flight check for this; `new-tool` prompts for it in the host-wiring step.
- **Env vars for rewrite destinations** — the host reads each zone's URL from `process.env.<NAME>_URL` (plain server-side env var, NOT `NEXT_PUBLIC_*`). Set these in the `policyengine-website` Vercel project.
- **Run `/multizone-validator` before announcing a zone as live** — validates `basePath`, phase-gated `assetPrefix`, `vercel.json` self-rewrite, host rewrites, and project naming in one pass.
