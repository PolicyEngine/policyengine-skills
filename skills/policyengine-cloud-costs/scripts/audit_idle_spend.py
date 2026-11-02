#!/usr/bin/env python3
"""List compute that PolicyEngine pays for while idle: warm Cloud Run instances, Cloud
Functions minimums, App Engine flexible versions left serving, and running Modal containers.

Read-only: it runs `gcloud ... list/describe` and `modal ... list` and changes nothing.

    python3 audit_idle_spend.py [--projects p1,p2] [--skip-modal] [--json]

Costs are rough idle estimates at Cloud Run's request-based idle rate
($0.0000025 per vCPU-second and per GiB-second); services with CPU always allocated
(instance-based billing) cost more. Check real spend in the billing export.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

IDLE_RATE_PER_SECOND = 0.0000025
SECONDS_PER_DAY = 86_400


def run_json(command: list[str]) -> list | dict | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


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
    number, unit = float(match.group(1)), (match.group(2) or "")
    factors = {"Ki": 1 / 1024**2, "Mi": 1 / 1024, "Gi": 1, "Ti": 1024, "K": 1e3 / 1024**3,
               "M": 1e6 / 1024**3, "G": 1e9 / 1024**3, "T": 1e12 / 1024**3, "": 1 / 1024**3}
    return number * factors[unit]


def idle_cost_per_day(cpu: float, memory: float, instances: int) -> float:
    return (cpu + memory) * IDLE_RATE_PER_SECOND * SECONDS_PER_DAY * instances


def cloud_run_findings(project: str) -> list[dict]:
    services = run_json(["gcloud", "run", "services", "list", "--project", project, "--format=json"]) or []
    if not services:
        return []
    # Revisions can only be listed one region at a time.
    regions = {service["metadata"].get("labels", {}).get("cloud.googleapis.com/location") for service in services}
    by_name = {}
    for region in sorted(region for region in regions if region):
        revisions = run_json(["gcloud", "run", "revisions", "list", "--project", project,
                              "--region", region, "--format=json"]) or []
        by_name.update({revision["metadata"]["name"]: revision for revision in revisions})
    findings = []
    for service in services:
        name = service["metadata"]["name"]
        region = service["metadata"].get("labels", {}).get("cloud.googleapis.com/location", "")
        service_minimum = int(service["metadata"].get("annotations", {}).get("run.googleapis.com/minScale", "0") or 0)
        traffic = service.get("spec", {}).get("traffic", [])
        referenced: dict[str, list[str]] = {}
        for entry in traffic:
            revision_name = entry.get("revisionName")
            if not revision_name and entry.get("latestRevision"):
                revision_name = service.get("status", {}).get("latestReadyRevisionName")
            if revision_name and (entry.get("percent") or entry.get("tag")):
                reasons = referenced.setdefault(revision_name, [])
                reasons.append(f"tag {entry['tag']}" if entry.get("tag") else f"{entry.get('percent')}% traffic")
        container = service["spec"]["template"]["spec"]["containers"][0]
        limits = container.get("resources", {}).get("limits", {})
        if service_minimum:
            findings.append({
                "provider": "Cloud Run", "project": project, "resource": f"{name} ({region})",
                "what": f"service-level minimum {service_minimum}",
                "instances": service_minimum,
                "usd_per_day": idle_cost_per_day(cpu_count(limits.get("cpu")), memory_gib(limits.get("memory")), service_minimum),
            })
        for revision_name, reasons in referenced.items():
            revision = by_name.get(revision_name)
            if not revision:
                continue
            minimum = int(revision["metadata"].get("annotations", {}).get("autoscaling.knative.dev/minScale", "0") or 0)
            if not minimum:
                continue
            revision_limits = revision["spec"]["containers"][0].get("resources", {}).get("limits", {})
            # A revision receiving traffic counts towards the service-level minimum, so the
            # larger of the two applies; only a tagged revision without traffic adds instances.
            overlaps = service_minimum > 0 and any(reason.endswith("traffic") for reason in reasons)
            findings.append({
                "provider": "Cloud Run", "project": project, "resource": f"{revision_name} ({region})",
                "what": f"revision-level minimum {minimum}, kept started by {', '.join(reasons)}"
                        + ("; overlaps the service-level minimum" if overlaps else ""),
                "instances": minimum,
                "usd_per_day": None if overlaps else idle_cost_per_day(
                    cpu_count(revision_limits.get("cpu")), memory_gib(revision_limits.get("memory")), minimum),
            })
    return findings


def cloud_functions_findings(project: str) -> list[dict]:
    functions = run_json(["gcloud", "functions", "list", "--project", project, "--format=json"]) or []
    findings = []
    for function in functions:
        minimum = int(function.get("minInstances") or function.get("serviceConfig", {}).get("minInstanceCount") or 0)
        if minimum and function.get("environment", "GEN_1") != "GEN_2":
            findings.append({
                "provider": "Cloud Functions", "project": project, "resource": function.get("name", "").split("/")[-1],
                "what": f"1st-gen function minimum {minimum}", "instances": minimum, "usd_per_day": None,
            })
    return findings


def app_engine_findings(project: str) -> list[dict]:
    versions = run_json(["gcloud", "app", "versions", "list", "--project", project,
                         "--filter=env=flexible AND servingStatus=SERVING", "--format=json"]) or []
    return [{
        "provider": "App Engine flex", "project": project, "resource": f"{version.get('service')}/{version.get('id')}",
        "what": f"flexible version SERVING, traffic split {version.get('traffic_split', 0)}",
        "instances": 1, "usd_per_day": None,
    } for version in versions]


def modal_findings() -> list[dict]:
    containers = run_json(["modal", "container", "list", "--json"]) or []
    counts: dict[str, int] = {}
    for container in containers:
        app = container.get("app_name") or container.get("App Name") or "?"
        counts[app] = counts.get(app, 0) + 1
    return [{
        "provider": "Modal", "project": "policyengine workspace", "resource": app,
        "what": "containers running now (warm settings, open requests, or running jobs)",
        "instances": count, "usd_per_day": None,
    } for app, count in sorted(counts.items(), key=lambda item: -item[1])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", help="comma-separated GCP project IDs (default: every project gcloud lists)")
    parser.add_argument("--skip-modal", action="store_true")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    arguments = parser.parse_args()

    if arguments.projects:
        projects = [project.strip() for project in arguments.projects.split(",") if project.strip()]
    else:
        listed = run_json(["gcloud", "projects", "list", "--format=json"]) or []
        projects = [project["projectId"] for project in listed if project.get("lifecycleState") == "ACTIVE"]

    findings: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for batch in pool.map(lambda project: cloud_run_findings(project) + cloud_functions_findings(project)
                              + app_engine_findings(project), projects):
            findings.extend(batch)
    if not arguments.skip_modal:
        findings.extend(modal_findings())

    if arguments.json:
        print(json.dumps(findings, indent=1))
        return 0
    findings.sort(key=lambda finding: -(finding["usd_per_day"] or 0))
    for finding in findings:
        cost = f"~${finding['usd_per_day']:.2f}/day" if finding["usd_per_day"] is not None else "see billing"
        print(f"{finding['provider']:<16} {finding['project']:<30} {finding['resource']:<55} "
              f"{finding['instances']:>3} warm  {cost:<14} {finding['what']}")
    known = sum(finding["usd_per_day"] or 0 for finding in findings)
    print(f"{len(findings)} findings in {len(projects)} projects; Cloud Run idle estimate ~${known:.2f}/day "
          f"(~${known * 30:.0f} per 30 days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
