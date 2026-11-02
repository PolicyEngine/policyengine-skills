---
name: policyengine-cloud-costs
description: |
  Load before writing, reviewing or deploying anything that decides what PolicyEngine pays
  for while nobody uses it: Cloud Run deploy flags and cloudbuild files (min instances, traffic
  tags, max instances), App Engine versions and set-traffic, Modal min_containers / keep_warm /
  buffer_containers / memory and CPU requests, versioned, preview, test or drill copies of apps,
  CI that starts Modal runs, uptime checks, Memorystore and Cloud SQL sizing, Secret Manager
  writes in deploys, image cleanup jobs, and retiring a service after a migration. Carries the
  org's recurring cost incidents, the rules that prevent them, a deploy-config checker and an
  idle-spend audit. Triggers: "min instances", "--min-instances", "minScale", "traffic tag",
  "keep warm", "min_containers", "cold start", "scale to zero", "cloudbuild", "modal deploy",
  "app engine version", "set-traffic", "GCP bill", "Modal bill", "cost spike",
  "old revisions", "retire service".
metadata:
  category: process
---

# PolicyEngine cloud costs

Load this before merging any change that controls what keeps running between requests. Every
rule here comes from a PolicyEngine bill. The costliest failure has happened five times: **a
deploy left the version it replaced running, and nothing stopped it.** The cleanup added after
each incident fixed one repo and one command, and the next incident came through another.

| When | Where | What stayed running | Cost | Cause and fix |
|---|---|---|---|---|
| Mar–May 2025 | Public API, App Engine flexible | 7 versions, 4 vCPU / 16 GB each | Not recorded | Deploys ran at the same time and each left a version up (policyengine-api#2423). Fixed by serialising deploys (#2427). |
| Nov–Dec 2025 | Simulation API, Cloud Run | 48 tagged revisions, 8 vCPU / 32 GiB each | About $1k/month of idle revisions (estimate at the time) | Each deploy set revision-level `minScale: 1` and a tag per model version, and tags were never removed. Fixed by keeping 5 tags. |
| Apr–Jul 2026 | Public API, App Engine flexible | 41 zero-traffic versions left `SERVING` | GCP bill £2,030 (Apr), £6,561 (May), £9,470 (Jun) | Releases deployed with `--no-promote` and moved traffic with `gcloud app services set-traffic`, which stops nothing (#3719). Fixed by stopping idle versions after each deploy (#3733). |
| May–Jul 2026 | Household API, App Engine flexible | The whole App Engine app, for 54 days after the move to Modal and Cloud Run | ≈$1,550/month, 87% of the project's GCP bill | CI stopped deploying to it, but nobody stopped it (policyengine-household-api#1615). |
| Oct–Nov 2026 | UK Budget API, Cloud Run | 7 tagged revisions, 8 vCPU / 8 GiB each | ≈$26/day | `cloudbuild.yaml` ran `--min-instances 1 --tag b<build>` on every deploy (fixed in uk-autumn-budget-dashboard-2026#379). The Public API had found and tested for this exact case in July (#3741); the test was never copied. |

Smaller cases that keep recurring:
- **Minimums on low-traffic or non-production services:**
  - Cloud Run `ri-ctc-calculator-backend` cost $65/month for six months after the app moved to Modal.
  - Other Cloud Run examples: staging gateways that inherited a production default, `testing-codex-*` gateways, and three cost-analysis functions.
  - Modal `min_containers` on light apps: marriage cost $114/month, and household API `frontier` kept 3 containers for about 4% of traffic.
- **Memory reserved far above use:** 32 GiB Modal workers for jobs peaking at 14–17 GB. Modal bills the higher of reserved and used.
- **CI starting paid work on every push:**
  - 233 of 306 "Results on Modal" runs were cancelled after starting containers, and every one of them was still billed.
  - An uptime check every 30 s kept Cloud Run from scaling to zero.
- **Objects created on every deploy with no retention:**
  - Container images: about 628 GiB in July 2026.
  - Secret versions: 745 identical versions.
  - Versioned Modal apps: 119 left deployed.
  - Preview Modal apps: 99 left after their PRs closed.
- **Cleanups that fail without saying so:**
  - An image cleanup "succeeded" while deleting 0 of 108 images (missing permission, errors sent to `/dev/null`).
  - `modal app stop` waited for a confirmation in CI and `|| true` hid the abort.
- **Resources left after a migration:** the RI CTC backend (deploy files deleted, service kept), and a Supabase database left for four months after cost tracking moved into the CRM.

## Rule: nothing stays warm without a reason, an owner and an end

A PR that keeps anything running while idle must say what it is, about how much it costs per day,
and when it stops. A launch window is code with a hard stop, not a setting someone must remember
to undo.
- **Warm-window example:** the UK Budget household app.
  `uk-autumn-budget-dashboard-2026/src/uk_budget_data/household_warm.py` holds dated windows and
  `WARM_UNTIL`. `modal_household.py` runs `warm_schedule` from `modal.Cron("*/10 * * * *")`, and
  that function calls `modal.Cls.from_name(app, "Household")().update_autoscaler(min_containers=n)`.
  The decorator keeps `min_containers=0`.
- **Why it re-applies every 10 minutes:** Modal documents that "subsequent deployments of the App
  containing this Function will reset the autoscaler back to its static configuration", so a
  manual `update_autoscaler` is lost on the next deploy, and a decorator minimum comes back with
  every deploy.

## Cloud Run

- **Never combine a revision-level minimum with a tag per deploy.**
  - `--min-instances` is fixed on each revision when it's created. Cloud Run starts it for every
    revision that has traffic **or a tag**: "all tagged revisions are started and then kept active,
    even when there are no incoming requests" (Cloud Run docs, minimum instances).
  - Use `--min N --min-instances 0`. The service-level `--min` is "divided among all Revisions
    receiving a percentage of traffic" (`gcloud run deploy --help`), so superseded and tagged-only
    revisions drop to zero.
  - The Public API's `.github/scripts/deploy_cloud_run_candidate.sh` and
    `tests/unit/test_cloud_run_candidate_deploy.py` show the pattern with tests (#3741, #3768).
    Copy them.
- **Rollback needs no tag.** `gcloud run services update-traffic SERVICE --to-revisions REV=100`
  works by revision name. If tags must exist (the simulation API pins model versions), cap how
  many there are and remove the oldest in the same step that adds a new one.
- **Settings you don't pass are inherited.** `gcloud run deploy` keeps what it isn't given, so a
  minimum set by hand in the console survives every later deploy. Pass `--min`, `--min-instances`
  and `--max` (or `--max-instances`) on every deploy, so the code shows the real settings.
- **Default to `--min 0`** for staging, preview, internal and scheduled services.
  - Callers such as Cloud Scheduler (180 s attempt deadline on the cost-analysis job) and GitHub
    Actions tolerate a cold start.
  - The exception is an endpoint Slack calls directly, which must answer within 3 seconds.
  - Don't let a production default reach staging through a shared deploy script.
- **Idle minimum instances still bill.** Under request-based billing, each idle instance costs about
  (vCPU + GiB) × $0.0000025 per second: $3.46/day at 8 vCPU / 8 GiB, $2.16/day at 2 vCPU / 8 GiB.
  Instance-based billing (CPU always allocated) costs more.
- **Probes count as traffic.** An uptime check that calls a service more often than its idle
  timeout keeps an instance running all the time. Probe production only.
- **Cap the maximum.** The default allows 100 instances; a busy 8 vCPU / 8 GiB instance costs about
  $0.76/hour, so 100 of them cost about $76/hour. Set the cap from the observed peak
  (`run.googleapis.com/container/instance_count`).
- **Secrets go in `--set-secrets`, never `--set-env-vars`.** A plain value is stored in every
  revision's configuration.

## App Engine flexible

Every version left `SERVING` keeps its own VM, whether or not it receives traffic.
- **Neither stop route covers staged releases.**
  - `gcloud app deploy --stop-previous-version` stops the previous version only "when deploying a
    new version that receives all traffic" (`gcloud app deploy --help`).
  - A `--no-promote` deploy followed by `gcloud app services set-traffic` stops nothing.
- **What a deploy must do:** stop every version except the live one and a rollback pair, and fail
  if it can't. #3733 does this.
- **To check:**
  `gcloud app versions list --project P --filter="env=flexible AND servingStatus=SERVING"`.

## Modal

- **Default `min_containers=0`, and no `keep_warm` or `buffer_containers`.** See the
  policyengine-tools skill for the backend pattern.
  - A warm window uses `update_autoscaler` from a Cron with a hard stop (above).
  - With `enable_memory_snapshot=True`, a cold first calculation on the marriage calculator took
    17 s, against 1.8 s warm.
  - The first one or two cold starts after each deploy rebuild the snapshot (1–1.5 min). Send one
    request yourself after `modal deploy`.
- **Size requests from a measured run.** Modal charges "whichever is higher: your request or actual
  usage" for CPU and memory, so reserved headroom is paid for even when unused. The dashboard
  templates' `cpu=8.0, memory=32768` is a starting point for national population runs, not a
  setting for every worker.
- **Every app has a way to end:**
  - Test, drill and speedtest copies deploy under their own name with no warm settings, and are
    stopped when you're done.
  - PR preview apps are stopped by the workflow that handles the PR closing.
  - Versioned apps are stopped once routing no longer sends them traffic.
  - In CI, run `modal app stop -y <name>`; without `-y` it waits for a confirmation and aborts. Let
    a failure fail the job.
- **CI:** cancelling a GitHub run does not refund containers it already started, so
  `cancel-in-progress` is not a cost control. Start expensive Modal jobs from a label, a manual
  dispatch or a path filter.
- **Seeing spend:** `modal billing report --start YYYY-MM-DD --end YYYY-MM-DD -r d --json` gives
  cost per app per day, and `modal container list --json` shows what is running now.

## Other managed services

| Service | What is billed | Check |
|---|---|---|
| Memorystore Redis | Provisioned GB-hours. The Standard (high-availability) tier also runs a replica. | Size from the `redis.googleapis.com/stats/memory/usage` peak with headroom (the Public API's cache went from 5 GB to 2 GB). |
| Cloud SQL | `REGIONAL` (high availability) runs a standby, roughly doubling the instance cost. | `cloudsql.googleapis.com/database/cpu/utilization` before choosing a tier. |
| Secret Manager | Every stored version. | Add a version only when the value changed: compare with `gcloud secrets versions access latest` first (policyengine-api#3855, policyengine-household-api#1697). |
| Artifact Registry | Storage. Deleting needs `artifactregistry.versions.delete` and `artifactregistry.tags.delete`, which `roles/artifactregistry.writer` lacks. | Cleanup scripts report each failed deletion and fail the job (policyengine-api#4143). |
| Global load balancer | About $18/month per forwarding rule, per project. | Prefer one shared load balancer. |
| Supabase (Pro org) | Every project's compute (Micro $0.01344/hour, about $9.81/month), used or not. Paid projects cannot be paused. | Gateway request counts miss direct Postgres connections; check `pg_stat_user_tables` before calling a project unused. |

## Migrations and retirements

The PR that moves traffic off a service lists every resource the old path used: App Engine apps,
Cloud Run services, databases, secrets, scheduler jobs, images, domains and uptime checks. It
records a dated step to stop or delete each one after a short overlap. Deleting deploy files does
not stop what they deployed.

## Before merging a deploy or infrastructure change

```bash
python3 skills/policyengine-cloud-costs/scripts/check_deploy_config.py /path/to/repo
```

It reads files only. **Errors:**
- CR1: a revision-level minimum together with tags;
- MO1: a literal non-zero `min_containers`, `keep_warm` or `buffer_containers`;
- CL1: a delete, stop or untag command whose errors are hidden;
- SE1: a secret-like name passed in `--set-env-vars`.

**Warnings:**
- SE2: Secret Manager versions added without comparing to the latest;
- CI1: Modal runs started on push or pull request with `cancel-in-progress`;
- CR2: a Cloud Run deploy with no maximum.

To keep an intended setting, add `# cost-ok: <rule> <reason, until when>` on the line or the line
above it. Test files are skipped.

Against past incidents it reports:

| Repository and commit | Rule reported |
|---|---|
| uk-autumn-budget-dashboard-2026 before #379 | CR1 |
| marriage before #130 | MO1 |
| policyengine-api before #4143 | CL1 |
| policyengine-household-api before #1697 | SE2 |

Each of those commits passes once its fix is applied.

## Audit: monthly, and whenever a bill jumps

```bash
python3 skills/policyengine-cloud-costs/scripts/audit_idle_spend.py            # all GCP projects + Modal
python3 skills/policyengine-cloud-costs/scripts/audit_idle_spend.py --projects policyengine-apps --skip-modal
```

It is read-only and lists, with a rough idle cost per day:
- service-level Cloud Run minimums;
- revisions kept started by a revision-level minimum, and whether that was traffic or a tag;
- 1st-gen Cloud Functions minimums;
- App Engine flexible versions left `SERVING`;
- Modal apps with running containers.

Every item needs an owner and a reason, or a change.

**Billing data:**
- **GCP:** the detailed billing export is in BigQuery, in project `policyengine-costanalysis`,
  dataset `CostAnalysisDataset`, table `gcp_billing_export_resource_v1_*`.
  The account bills in **GBP**: divide `cost` by `currency_conversion_rate` for USD.
  Idle-minimum charges are the SKUs containing `Min Instance`, by `resource.name`.
- **CRM costs module:** ingests GCP and Modal costs and sends spike alerts. Those alerts compare
  with the previous 30 days' median, so a slow rise (April–June 2026) never triggers one. Read the
  month-on-month totals too.
