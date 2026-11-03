"""Tests for skills/policyengine-cloud-costs/scripts/check_deployed_app.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills/policyengine-cloud-costs/scripts/check_deployed_app.py"
)
SPEC = importlib.util.spec_from_file_location("check_deployed_app", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["check_deployed_app"] = MODULE
SPEC.loader.exec_module(MODULE)


def service(traffic: list[dict], service_minimum: int = 0, maximum: str | None = "10") -> dict:
    annotations = {"run.googleapis.com/minScale": str(service_minimum)} if service_minimum else {}
    template_annotations = {"autoscaling.knative.dev/maxScale": maximum} if maximum else {}
    return {
        "metadata": {"name": "tool", "annotations": annotations},
        "spec": {"template": {
            "metadata": {"annotations": template_annotations},
            "spec": {"containers": [{"resources": {"limits": {"cpu": "8", "memory": "8Gi"}}}]},
        }},
        "status": {"traffic": traffic},
    }


def revision(name: str, minimum: int) -> dict:
    return {
        "metadata": {"name": name, "annotations": {"autoscaling.knative.dev/minScale": str(minimum)}},
        "spec": {"containers": [{"resources": {"limits": {"cpu": "8", "memory": "8Gi"}}}]},
    }


def test_scaled_to_zero_service_matches():
    _, problems = MODULE.cloud_run_problems(
        service([{"revisionName": "tool-2", "percent": 100}]), [revision("tool-2", 0)], declared_minimum=0)
    assert problems == []


def test_tagged_revision_with_minimum_is_a_problem_even_when_declared():
    traffic = [{"revisionName": "tool-2", "percent": 100}, {"revisionName": "tool-1", "tag": "b123"}]
    report, problems = MODULE.cloud_run_problems(
        service(traffic), [revision("tool-1", 1), revision("tool-2", 1)], declared_minimum=2)
    assert any("tool-1 has no traffic but a tag" in problem for problem in problems)
    assert "instances running while idle: 2 (about $6.91/day)" in report


def test_declared_service_minimum_matches_and_is_counted_once():
    traffic = [{"revisionName": "tool-2", "percent": 100}]
    report, problems = MODULE.cloud_run_problems(
        service(traffic, service_minimum=1), [revision("tool-2", 1)], declared_minimum=1)
    assert problems == []
    assert "instances running while idle: 1 (about $3.46/day)" in report

    _, undeclared = MODULE.cloud_run_problems(
        service(traffic, service_minimum=1), [revision("tool-2", 1)], declared_minimum=0)
    assert any("but 0 declared" in problem for problem in undeclared)


def test_default_maximum_is_a_problem():
    _, problems = MODULE.cloud_run_problems(
        service([{"revisionName": "tool-2", "percent": 100}], maximum=None), [revision("tool-2", 0)], 0)
    assert any("maximum is 100" in problem for problem in problems)


def test_modal_running_containers_against_declaration():
    apps = [{"description": "tool", "state": "deployed", "tasks": 2},
            {"description": "tool", "state": "stopped", "tasks": 0}]
    assert MODULE.modal_problems(apps, "tool", declared_warm=2)[1] == []
    assert MODULE.modal_problems(apps, "tool", declared_warm=0)[1]
    assert MODULE.modal_problems(apps, "missing", declared_warm=0)[1] == ["no deployed Modal app named missing"]


def test_failed_command_raises_instead_of_returning_nothing():
    try:
        MODULE.run_json([sys.executable, "-c", "import sys; sys.exit(3)"])
    except MODULE.CommandFailed as error:
        assert "exit 3" in str(error)
    else:
        raise AssertionError("a failed command must not look like an empty result")
