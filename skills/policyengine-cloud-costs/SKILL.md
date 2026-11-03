---
name: policyengine-cloud-costs
description: |
  Load when building or deploying your own PolicyEngine tool, dashboard backend, calculator
  or API on Modal, Cloud Run, App Engine or Supabase: scaffolding a backend, writing or
  changing deploy scripts, cloudbuild files, GitHub workflows or Modal decorators, before
  the first deploy, before a launch or busy period, and when replacing or retiring a tool.
  Sets the defaults (nothing running while idle, a set maximum, CPU and memory from a
  measured run, secrets out of the repo, an end for every copy) and shows how to declare a
  deliberate exception, such as warm containers, minimum instances or large workers. Has a
  README cost plan, copyable workflows, a pre-merge config checker and a post-deploy check
  for one app, plus the incidents behind each rule. Triggers: "min_containers",
  "max_containers", "min instances", "--min-instances", "keep warm", "cold start", "scale
  to zero", "memory=", "modal deploy", "gcloud run deploy", "cloudbuild", "preview app",
  "launch day", "retire", "what will this cost".
metadata:
  category: apps
---

# Cloud costs for your own tool

For anyone building a standalone tool (a dashboard backend, a calculator API, a data job)
and deploying it themselves. The defaults below cost nothing while nobody uses the tool.
Each rule comes from a PolicyEngine bill; the incidents are listed at the end.

The defaults are not bans. Warm containers for a launch, a minimum instance for an endpoint
that must answer quickly, or 20 GiB workers for a national run are all fine **when you
declare them** where they are set (section 2). A declaration is how the reviewer, the
checker and the next maintainer know the setting is deliberate and what it costs.

Load this when:
- scaffolding a tool with a backend (the dashboard-builder agents and `/new-tool` link here);
- a PR changes deploy scripts, Modal decorators, `cloudbuild.yaml` or GitHub workflows;
- before the first deploy, before a launch or busy period, and when a tool is replaced or
  retired.

## 1. Write the cost plan before the first deploy

Copy `templates/running-costs.md` into the tool's README and answer five questions:
1. **What runs while nobody uses it?** The default answer is "nothing".
2. **What is the most it can cost in an hour?** Maximum containers or instances × the
   hourly rate (prices at the end).
3. **What makes extra copies, and what ends each one?** Traffic tags, versions, PR preview
   apps, test and drill deploys.
4. **Where do the secrets live?** A secret store, never the repo.
5. **Who owns it, and when is it reviewed or retired?**

## 2. Defaults, and how to declare something else

| Setting | Default | Rule to declare |
|---|---|---|
| Modal `min_containers`, `buffer_containers`, `keep_warm` | 0 or unset | MO1 |
| Cloud Run `--min`, `--min-instances` | 0 | CR3 |
| Modal `max_containers` | Set, from the expected peak | MO2 (to leave it unset) |
| Cloud Run `--max` | Set, from the observed peak | CR2 (to leave it unset) |
| CPU and memory | From a measured run; 4 or more cores, or 16 GiB or more, needs a reason | RS1 |
| A revision-level minimum together with a traffic tag per deploy | Never | CR1 |

To choose something else, put a `cost-ok` comment on the setting's line, the line above, or
in the comment block directly above the command:

```python
@app.function(
    image=image,
    cpu=2.0,
    memory=20480,  # cost-ok: RS1 UK national reform run peaked at 14-17 GB, plus a fifth
    max_containers=4,
)
def run_national(reform: dict) -> dict: ...


@app.cls(
    image=image,
    cpu=1.0,
    memory=1024,
    max_containers=40,
    min_containers=2,  # cost-ok: MO1 Budget day: first visitors skip a cold start; until 2026-11-27
)
class Household: ...
```

```bash
# cost-ok: CR3 Slack calls this endpoint and needs an answer within 3 s
gcloud run deploy TOOL_NAME --min 1 --min-instances 0 --max 5 --cpu 1 --memory 1Gi
```

A declaration:
- names the rule, then says why: what was measured, or what needs the setting;
- for anything temporary, ends with `until YYYY-MM-DD`. After that date the declaration
  stops counting, so the rule reports again until the setting is removed or declared again;
- gets a row in the README's "Declared exceptions" table, with its cost per day or hour.

A declaration counts only when it gives a reason (not one starting `TODO`) and its date has
not passed. Otherwise the rule reports as usual, with a note saying why. The checker prints
every accepted declaration, so reviewers see each one. After deploying, `check_deployed_app.py` takes the number you declared (`--declared-min`,
`--declared-warm`) and fails if more is running.

## 3. Platform defaults

### Modal

```python
@app.function(
    image=image,
    cpu=1.0,
    memory=2048,
    timeout=600,
    max_containers=10,
    min_containers=0,
)
def compute(params: dict) -> dict: ...
```

- **Size from a measured run.** Modal charges "whichever is higher: your request or actual
  usage" for CPU and memory, so unused headroom is still paid for.
  - Measure one representative run: `/usr/bin/time -v` on Linux or `/usr/bin/time -l` on
    macOS prints the peak memory, and the app's page in the Modal dashboard charts each
    container's memory. Reserve about a fifth more than the peak.
  - Reference points: a UK household calculation peaks near 0.4 GB, and a simulation runs on
    one thread, so a second core adds cost, not speed
    (`uk-autumn-budget-dashboard-2026/src/uk_budget_data/modal_household.py`). The marriage
    calculator runs household calculations at 2 cores / 8 GiB with up to 3 requests per
    container. A UK national reform run peaked at 14–17 GB.
- **Warm windows are code with a hard stop.** Keep the decorator at `min_containers=0`, and
  copy `templates/warm_window.py`: a `modal.Cron` that calls `update_autoscaler` with the
  current window's count, and 0 after `WARM_UNTIL`. It re-applies every 10 minutes because
  "subsequent deployments of the App containing this Function will reset the autoscaler back
  to its static configuration" (Modal docs). The UK Budget household app uses this pattern
  (`uk-autumn-budget-dashboard-2026/src/uk_budget_data/household_warm.py`).
- **Memory snapshots** (`enable_memory_snapshot=True`) shorten cold starts: the marriage
  calculator's first calculation took 17 s cold with a snapshot, against 1.8 s warm. The
  first one or two cold starts after each deploy rebuild the snapshot (1–1.5 min), so send
  one request yourself after `modal deploy`.
- **Every app has an end.**
  - Test, drill and benchmark copies deploy under their own name with no warm settings, and
    are stopped when you are done.
  - PR preview apps are stopped when the PR closes: copy `templates/stop-preview-app.yml`.
  - In CI, `modal app stop -y NAME`. Without `-y` it waits for a confirmation and aborts.

### Cloud Run

```bash
gcloud run deploy TOOL_NAME --project PROJECT --region REGION \
  --min 0 --min-instances 0 --max 5 --cpu 1 --memory 1Gi \
  --set-secrets API_KEY=TOOL_NAME-api-key:latest
```

- **Pass every scaling setting on every deploy.** `gcloud run deploy` keeps what it isn't
  given, so a minimum set by hand in the console survives every later deploy.
- **Never combine a revision-level minimum with a tag per deploy.** Cloud Run keeps "all
  tagged revisions ... started and then kept active, even when there are no incoming
  requests" (Cloud Run docs, minimum instances). A declared minimum goes on the service
  (`--min N --min-instances 0`), which is "divided among all Revisions receiving a percentage
  of traffic" (`gcloud run deploy --help`).
- **Rollback needs no tag:**
  `gcloud run services update-traffic SERVICE --to-revisions REVISION=100`.
- **Probes count as traffic.** An uptime check that calls more often than the idle timeout
  keeps an instance running all the time.
- **Secrets go in `--set-secrets`, never `--set-env-vars`.** A plain value is stored in every
  revision's configuration.

App Engine flexible keeps a VM for every version left `SERVING`. `--stop-previous-version`
only works "when deploying a new version that receives all traffic"
(`gcloud app deploy --help`), and `gcloud app services set-traffic` stops nothing. Prefer Cloud
Run or Modal for a new tool.

### CI

- **Start expensive Modal jobs on purpose:** `workflow_dispatch`, a label, or a path filter,
  not every push. `cancel-in-progress` is not a cost control: a cancelled run still pays for
  the containers it started.
- **Let cleanup fail loudly.** No `|| true` or `2>/dev/null` on a delete or stop. Count and
  report failures.
- **Keep credentials out of commits.** `.gitignore` lists `.env`, and `gha-creds-*.json` if
  a workflow uses `google-github-actions/auth` with `credentials_json`: that step writes the
  key into the workspace, and a later "commit everything" step publishes it. Workload
  identity federation avoids the key file.
- **Secret Manager bills every stored version.** Add one only when the value changed:
  compare with `gcloud secrets versions access latest` first.

### Data and storage

- **Supabase:** each project on the Pro organisation bills its compute (Micro, about
  $9.81/month) whether used or not, and a paid project cannot be paused. Prefer a schema in
  an existing project to a project per tool. A service-role key bypasses row-level
  security: keep it in a secret store, never in code.
- **Container images and other per-deploy objects need retention.** Images reached about
  628 GiB in July 2026. Deleting Artifact Registry images needs
  `artifactregistry.versions.delete` and `artifactregistry.tags.delete`, which
  `roles/artifactregistry.writer` lacks.
- **Memorystore and Cloud SQL bill what is provisioned.** High-availability tiers run a
  replica or standby. Size from measured use.

## 4. Before merging: the config checker

The scaffold adds a CI step that downloads `scripts/check_deploy_config.py` from this repo's
`main` branch and runs it (`templates/cost-checks.yml` is the same step as a workflow of its
own). To run it locally:

```bash
curl -fsSL https://raw.githubusercontent.com/PolicyEngine/policyengine-skills/main/skills/policyengine-cloud-costs/scripts/check_deploy_config.py | python3 - .
```

It reads files only, so it needs no credentials. Test files and comment-only lines are
skipped.

| Rule | Severity | Reports |
|---|---|---|
| CR1 | error | A revision-level `--min-instances` in a file that also tags revisions |
| CR3 | error | Any non-zero Cloud Run minimum (`--min`, `--min-instances`, `minScale`, `min_instance_count`) |
| MO1 | error | A literal non-zero `min_containers`, `keep_warm` or `buffer_containers` |
| CL1 | error | A delete, stop or untag command whose errors are hidden |
| SE1 | error | A secret-like name in `--set-env-vars` |
| SE3 | error | `credentials_json` with a commit-everything step and no `gha-creds` in `.gitignore` |
| RS1 | warning | Modal or Cloud Run with 4 or more cores, or 16 GiB or more |
| MO2 | warning | A Modal function or class without `max_containers` (scheduled functions excepted) |
| CR2 | warning | `gcloud run deploy` with no maximum |
| SE2 | warning | A Secret Manager version added without comparing it to the latest |
| CI1 | warning | Modal work started on push or pull request with `cancel-in-progress` |

`--strict` also fails on warnings. A value set through a variable (`min_containers=MINIMUM`)
is left to the reviewer.

On the commits before each incident's fix it reports:

| Repository and commit | Rule reported |
|---|---|
| uk-autumn-budget-dashboard-2026 before #379 | CR1 |
| marriage before #130 | MO1 |
| policyengine-api before #4143 | CL1 |
| policyengine-household-api before #1697 | SE2 |

Each rule clears once the fix is applied. After #379, uk-autumn-budget-dashboard-2026 reports
CR3 for its Budget-week `--min 1` until that minimum is declared, which is the intended result.

## 5. After deploying: check your own app

Run `check_deployed_app.py` from this skill's `scripts/` folder (`SKILL_DIR` below) with the
access you already use to deploy:

```bash
python3 SKILL_DIR/scripts/check_deployed_app.py --cloud-run TOOL_NAME --project PROJECT --region REGION --declared-min 0
python3 SKILL_DIR/scripts/check_deployed_app.py --modal-app TOOL_NAME --declared-warm 0
```

- **Cloud Run:** it reads the service and its revisions. It reports the service-level
  minimum and maximum, every revision kept started by traffic or a tag, and the instances
  running while idle with an estimated cost per day. It reports a problem for a tagged
  revision with no traffic and a minimum, a maximum left at the default 100, or more
  instances running than declared.
- **Modal:** it reports the containers running now for that app. Run it after the scaledown
  window with no requests in flight; anything above the declared count is a warm setting.
- If a command fails (expired login, wrong region, no permission), it stops with exit
  status 2 and the error, rather than reporting an empty service.

Then send one request with nothing warm, and check that it finishes within the frontend's
timeout: `curl -s -o /dev/null -w '%{time_total}\n' URL`.

## 6. Replacing or retiring a tool

The PR that moves traffic away lists everything the old version used: Cloud Run services,
Modal apps, App Engine apps, databases, secrets, scheduler jobs, images, domains and uptime
checks. It adds a dated step to stop or delete each one after a short overlap. Deleting the
deploy files does not stop what they deployed.

## Prices for the estimate

| What | Rate | Example |
|---|---|---|
| Modal CPU | $0.0473 per core-hour | |
| Modal memory | $0.008 per GiB-hour | 1 core / 2 GiB ≈ $0.063/hour; 8 cores / 32 GiB ≈ $0.63/hour |
| Cloud Run idle instance (request-based billing) | (vCPU + GiB) × $0.0000025 per second | 8 vCPU / 8 GiB ≈ $3.46/day; 2 vCPU / 8 GiB ≈ $2.16/day |
| Cloud Run busy instance | | 8 vCPU / 8 GiB ≈ $0.76/hour, so the default maximum of 100 ≈ $76/hour |
| Supabase project (Pro organisation, Micro compute) | $0.01344/hour | ≈ $9.81/month |
| Global load balancer | About $18/month per forwarding rule | |

Instance-based Cloud Run billing (CPU always allocated) costs more than the idle rate above.

## Why these rules exist

The costliest failure has happened five times: **a deploy left the version it replaced
running, and nothing stopped it.**

| When | Where | What stayed running | Cost | Cause and fix |
|---|---|---|---|---|
| Mar–May 2025 | Public API, App Engine flexible | 7 versions, 4 vCPU / 16 GB each | Not recorded | Deploys ran at the same time and each left a version up (policyengine-api#2423). Fixed by serialising deploys (#2427). |
| Nov–Dec 2025 | Simulation API, Cloud Run | 48 tagged revisions, 8 vCPU / 32 GiB each | About $1k/month (estimate at the time) | Each deploy set a revision-level minimum and a tag per model version, and tags were never removed. |
| Apr–Jul 2026 | Public API, App Engine flexible | 41 zero-traffic versions left `SERVING` | GCP bill £2,030 (Apr), £6,561 (May), £9,470 (Jun) | `--no-promote` deploys, then `set-traffic`, which stops nothing (#3719). Fixed by stopping idle versions after each deploy (#3733). |
| May–Jul 2026 | Household API, App Engine flexible | The whole App Engine app for 54 days after the move to Modal and Cloud Run | ≈$1,550/month | CI stopped deploying to it, but nobody stopped it (policyengine-household-api#1615). |
| Oct–Nov 2026 | UK Budget API, Cloud Run | 7 tagged revisions, 8 vCPU / 8 GiB each | ≈$26/day | `--min-instances 1 --tag b<build>` on every deploy (fixed in uk-autumn-budget-dashboard-2026#379). The Public API had tested for this case in July (#3741); the test was never copied. |

Smaller cases that keep recurring:
- **Minimums on light or retired services:** the Cloud Run `ri-ctc-calculator-backend` cost
  $65/month for six months after the app moved to Modal; `min_containers` on the marriage
  calculator cost $114/month.
- **Memory reserved far above use:** 32 GiB Modal workers for runs peaking at 14–17 GB.
- **CI starting paid work on every push:** 233 of 306 "Results on Modal" runs were cancelled
  after starting containers, and each was still billed.
- **Copies with no end:** 119 versioned Modal apps and 99 preview apps left deployed; 745
  identical Secret Manager versions.
- **Cleanups that failed silently:** an image cleanup "succeeded" while deleting 0 of 108
  images; `modal app stop` without `-y` aborted in CI behind `|| true`.
- **Credentials committed by CI:** in July 2026 a version-bump step that committed
  everything (`EndBug/add-and-commit` with `add: "."`) also committed the
  `gha-creds-*.json` key file that `google-github-actions/auth` had written.
