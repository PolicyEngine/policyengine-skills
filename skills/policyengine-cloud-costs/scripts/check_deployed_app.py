#!/usr/bin/env python3
"""Check what one deployed tool keeps running while idle, against what its owner declared.

Read-only: runs `gcloud run services describe`, `gcloud run revisions list` and
`modal app list` with the access you already use to deploy. Changes nothing.

    python3 check_deployed_app.py --cloud-run SERVICE --project P --region R [--declared-min N]
    python3 check_deployed_app.py --modal-app APP [--modal-env ENV] [--declared-warm N]

Exit status: 0 when the deployed state matches the declaration, 1 when it does not,
2 when a command fails (nothing is assumed about a service it could not read).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

IDLE_RATE_PER_SECOND = 0.0000025  # Cloud Run request-based idle rate, per vCPU-second and per GiB-second
SECONDS_PER_DAY = 86_400
DEFAULT_MAXIMUM = 100


class CommandFailed(Exception):
    pass


def run_json(command: list[str]) -> list | dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CommandFailed(f"{' '.join(command)}: {error}") from error
    if result.returncode != 0:
        raise CommandFailed(f"{' '.join(command)}: {result.stderr.strip() or 'exit ' + str(result.returncode)}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CommandFailed(f"{' '.join(command)}: output is not JSON") from error


def cpu_count(value: str | None) -> float:
    if not value:
        return 1.0
    return float(value[:-1]) / 1000 if value.endswith("m") else float(value)


def memory_gib(value: str | None) -> float:
    if not value:
        return 0.5
    match = re.fullmatch(r"([0-9.]+)\s*([KMGT]i?)?", value)
    if not match:
        return 0.5
    number, unit = float(match.group(1)), match.group(2) or ""
    factors = {"Ki": 1 / 1024**2, "Mi": 1 / 1024, "Gi": 1, "Ti": 1024, "K": 1e3 / 1024**3,
               "M": 1e6 / 1024**3, "G": 1e9 / 1024**3, "T": 1e12 / 1024**3, "": 1 / 1024**3}
    return number * factors[unit]


def idle_cost_per_day(limits: dict, instances: int) -> float:
    size = cpu_count(limits.get("cpu")) + memory_gib(limits.get("memory"))
    return size * IDLE_RATE_PER_SECOND * SECONDS_PER_DAY * instances


def cloud_run_problems(service: dict, revisions: list[dict], declared_minimum: int) -> tuple[list[str], list[str]]:
    """Return (report lines, problems) for one Cloud Run service and its revisions."""
    report, problems = [], []
    annotations = service["metadata"].get("annotations", {})
    template_annotations = service["spec"]["template"]["metadata"].get("annotations", {})
    service_minimum = int(annotations.get("run.googleapis.com/minScale", "0") or 0)
    # Service-level --max and revision-level --max-instances both cap; the lower one applies.
    maximum = min([int(value) for value in (annotations.get("run.googleapis.com/maxScale"),
                                            template_annotations.get("autoscaling.knative.dev/maxScale")) if value]
                  or [DEFAULT_MAXIMUM])
    limits = service["spec"]["template"]["spec"]["containers"][0].get("resources", {}).get("limits", {})
    report.append(f"size {limits.get('cpu', '1')} vCPU / {limits.get('memory', '512Mi')}, "
                  f"service-level minimum {service_minimum}, maximum {maximum}")
    if maximum >= DEFAULT_MAXIMUM:
        problems.append(f"maximum is {maximum} (the default): set --max from the observed peak")

    by_name = {revision["metadata"]["name"]: revision for revision in revisions}
    reasons: dict[str, list[str]] = {}
    for entry in service.get("status", {}).get("traffic", []):
        name = entry.get("revisionName")
        if name and (entry.get("percent") or entry.get("tag")):
            reasons.setdefault(name, []).append(
                f"{entry['percent']}% traffic" if entry.get("percent") else f"tag {entry['tag']}")
    warm_instances, warm_cost = service_minimum, idle_cost_per_day(limits, service_minimum)
    for name, why in sorted(reasons.items()):
        revision = by_name.get(name)
        if revision is None:
            problems.append(f"{name} is referenced by traffic but was not listed")
            continue
        minimum = int(revision["metadata"].get("annotations", {}).get("autoscaling.knative.dev/minScale", "0") or 0)
        if not minimum:
            continue
        has_traffic = any(reason.endswith("traffic") for reason in why)
        revision_limits = revision["spec"]["containers"][0].get("resources", {}).get("limits", {})
        report.append(f"{name}: revision-level minimum {minimum}, kept started by {', '.join(why)}")
        if not has_traffic:
            problems.append(f"{name} has no traffic but a tag keeps its {minimum} instance(s) running: "
                            f"remove the tag, or redeploy with --min-instances 0")
        if has_traffic and service_minimum:
            continue  # counted in the service-level minimum
        warm_instances += minimum
        warm_cost += idle_cost_per_day(revision_limits, minimum)
    report.append(f"instances running while idle: {warm_instances} (about ${warm_cost:.2f}/day)")
    if warm_instances > declared_minimum:
        problems.append(f"{warm_instances} instance(s) stay running while idle, but {declared_minimum} "
                        f"declared: lower the minimum, or declare it with a reason")
    return report, problems


def modal_problems(apps: list[dict], app_name: str, declared_warm: int) -> tuple[list[str], list[str]]:
    deployed = [app for app in apps if app.get("description") == app_name and app.get("state") == "deployed"]
    if not deployed:
        return [], [f"no deployed Modal app named {app_name}"]
    running = sum(int(app.get("tasks") or 0) for app in deployed)
    report = [f"{app_name}: {running} container(s) running now"]
    problems = []
    if running > declared_warm:
        problems.append(f"{running} container(s) running, {declared_warm} declared. If no requests are in "
                        f"flight, a minimum or buffer is keeping them: re-check after the scaledown window")
    return report, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cloud-run", metavar="SERVICE")
    parser.add_argument("--project")
    parser.add_argument("--region")
    parser.add_argument("--declared-min", type=int, default=0,
                        help="instances you declared may run while idle (default 0)")
    parser.add_argument("--modal-app", metavar="APP")
    parser.add_argument("--modal-env", help="Modal environment (default: your profile's)")
    parser.add_argument("--declared-warm", type=int, default=0,
                        help="Modal containers you declared may run while idle (default 0)")
    arguments = parser.parse_args()
    if not arguments.cloud_run and not arguments.modal_app:
        parser.error("give --cloud-run SERVICE or --modal-app APP")
    if arguments.cloud_run and not (arguments.project and arguments.region):
        parser.error("--cloud-run needs --project and --region")

    report, problems = [], []
    try:
        if arguments.cloud_run:
            location = ["--project", arguments.project, "--region", arguments.region, "--format=json"]
            service = run_json(["gcloud", "run", "services", "describe", arguments.cloud_run, *location])
            revisions = run_json(["gcloud", "run", "revisions", "list", "--service", arguments.cloud_run, *location])
            lines, issues = cloud_run_problems(service, revisions, arguments.declared_min)
            report += [f"Cloud Run {arguments.cloud_run}: {line}" for line in lines]
            problems += issues
        if arguments.modal_app:
            command = ["modal", "app", "list", "--json"]
            if arguments.modal_env:
                command += ["--env", arguments.modal_env]
            lines, issues = modal_problems(run_json(command), arguments.modal_app, arguments.declared_warm)
            report += [f"Modal {line}" for line in lines]
            problems += issues
    except CommandFailed as error:
        print(f"could not read the deployed state: {error}", file=sys.stderr)
        return 2
    for line in report:
        print(line)
    for problem in problems:
        print(f"problem: {problem}")
    print("matches the declaration" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
