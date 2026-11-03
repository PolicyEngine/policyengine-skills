"""Tests for skills/policyengine-cloud-costs/scripts/check_deploy_config.py."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills/policyengine-cloud-costs/scripts/check_deploy_config.py"
)
SPEC = importlib.util.spec_from_file_location("check_deploy_config", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["check_deploy_config"] = MODULE
SPEC.loader.exec_module(MODULE)

TODAY = date(2026, 11, 3)


def rules_found(path: str, text: str, **options) -> list[tuple[str, str]]:
    findings, _ = MODULE.check_file(Path(path), text, TODAY, **options)
    return [(finding.rule, finding.severity) for finding in findings]


def declared_rules(path: str, text: str) -> list[str]:
    _, declarations = MODULE.check_file(Path(path), text, TODAY)
    return [declaration.rule for declaration in declarations]


MODAL_WORKER = """import modal
app = modal.App("tool-workers")

@app.function(
    cpu=1.0,
    memory=2048,
    max_containers=10,
)
def compute(params):
    return params
"""


def test_default_modal_worker_passes():
    assert rules_found("backend/app.py", MODAL_WORKER) == []


def test_warm_modal_container_is_an_error_until_declared():
    warm = MODAL_WORKER.replace("max_containers=10,", "max_containers=10,\n    min_containers=2,")
    assert rules_found("backend/app.py", warm) == [("MO1", "error")]

    declared = warm.replace(
        "min_containers=2,", "min_containers=2,  # cost-ok: MO1 launch-day traffic; until 2026-11-30"
    )
    assert rules_found("backend/app.py", declared) == []
    assert declared_rules("backend/app.py", declared) == ["MO1"]


def test_declaration_without_reason_is_rejected():
    text = MODAL_WORKER.replace("max_containers=10,", "max_containers=10,\n    min_containers=1,  # cost-ok: MO1")
    assert rules_found("backend/app.py", text) == [("MO1", "error")]
    todo = text.replace("# cost-ok: MO1", "# cost-ok: MO1 TODO")
    assert rules_found("backend/app.py", todo) == [("MO1", "error")]


def test_expired_declaration_is_an_error():
    text = MODAL_WORKER.replace(
        "max_containers=10,",
        "max_containers=10,\n    min_containers=1,  # cost-ok: MO1 budget day; until 2026-10-31",
    )
    findings, declarations = MODULE.check_file(Path("backend/app.py"), text, TODAY)
    assert [(finding.rule, finding.severity) for finding in findings] == [("MO1", "error")]
    assert "ended on 2026-10-31" in findings[0].message
    assert declarations == []


def test_large_modal_reservation_warns_until_declared():
    large = MODAL_WORKER.replace("cpu=1.0,", "cpu=8.0,").replace("memory=2048,", "memory=32 * 1024,")
    assert rules_found("backend/app.py", large) == [("RS1", "warning"), ("RS1", "warning")]

    declared = large.replace("cpu=8.0,", "cpu=8.0,  # cost-ok: RS1 national run peaked at 17 GB on 8 cores").replace(
        "memory=32 * 1024,", "memory=32 * 1024,  # cost-ok: RS1 measured peak 17 GB, about a quarter headroom"
    )
    assert rules_found("backend/app.py", declared) == []


def test_modal_function_without_maximum_warns_but_cron_does_not():
    no_maximum = MODAL_WORKER.replace("    max_containers=10,\n", "")
    assert rules_found("backend/app.py", no_maximum) == [("MO2", "warning")]

    cron = 'import modal\napp = modal.App("tool")\n\n@app.function(schedule=modal.Cron("*/10 * * * *"))\ndef tick():\n    pass\n'
    assert rules_found("backend/app.py", cron) == []


def test_cloud_run_minimum_is_an_error_until_declared():
    deploy = "gcloud run deploy tool --min 1 --min-instances 0 --max 5 --cpu 1 --memory 1Gi\n"
    assert rules_found("deploy.sh", deploy) == [("CR3", "error")]

    declared = "# cost-ok: CR3 Slack calls this endpoint and needs an answer within 3 s\n" + deploy
    assert rules_found("deploy.sh", declared) == []


def test_cloud_run_millicpu_is_not_large():
    deploy = "gcloud run deploy tool --min 0 --max 5 --cpu 2000m --memory 512Mi\n"
    assert rules_found("deploy.sh", deploy) == []
    large = "gcloud run deploy tool --min 0 --max 5 --cpu 8 --memory 32Gi\n"
    assert rules_found("deploy.sh", large) == [("RS1", "warning"), ("RS1", "warning")]


def test_revision_minimum_with_tags_reports_only_the_tag_rule():
    cloudbuild = (
        "args: ['run', 'deploy', 'api', '--min-instances', '1', '--max', '5']\n"
        "gcloud run deploy api --min-instances 1 --tag b123 --max 5\n"
    )
    assert ("CR1", "error") in rules_found("cloudbuild.yaml", cloudbuild)
    assert ("CR3", "error") not in rules_found("cloudbuild.yaml", cloudbuild)


def test_json_key_with_commit_all_is_an_error_unless_gitignored():
    workflow = """on:
  push:
jobs:
  version:
    steps:
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: EndBug/add-and-commit@v10
        with:
          add: "."
"""
    path = ".github/workflows/versioning.yml"
    assert rules_found(path, workflow) == [("SE3", "error")]
    assert rules_found(path, workflow, ignores_gha_creds=True) == []
    with_flag = workflow.replace("credentials_json:", "create_credentials_file: false\n          credentials_json:")
    assert rules_found(path, with_flag) == []


def test_commit_amend_is_not_commit_all():
    workflow = (
        "on:\n  push:\njobs:\n  x:\n    steps:\n"
        "      - uses: google-github-actions/auth@v2\n        with:\n          credentials_json: x\n"
        "      - run: git commit --amend --no-edit\n"
    )
    assert rules_found(".github/workflows/x.yml", workflow) == []


def test_comment_mentioning_a_minimum_is_not_a_setting():
    text = "# --min 1 keeps one instance warm during Budget week\ngcloud run deploy tool --min 0 --max 5\n"
    assert rules_found("deploy.sh", text) == []


def test_declaration_with_unknown_rule_warns():
    text = "gcloud run deploy tool --min 0 --max 5  # cost-ok: launch week\n"
    assert rules_found("deploy.sh", text) == [("??", "warning")]


def test_past_incidents_still_fail():
    uk_budget_cloudbuild = (
        "      - '--min-instances'\n      - '1'\n      - '--tag'\n      - 'b$BUILD_ID'\n"
        "gcloud run deploy uk-budget-api-2026 --min-instances 1 --tag b123 --max 10\n"
    )
    assert ("CR1", "error") in rules_found("cloudbuild.yaml", uk_budget_cloudbuild)
    hidden_cleanup = 'gcloud artifacts docker images delete "$IMAGE" --quiet 2>/dev/null || true\n'
    assert rules_found("cleanup.sh", hidden_cleanup) == [("CL1", "error")]


def test_comment_block_above_a_command_can_declare_several_rules():
    deploy = (
        "# cost-ok: CR3 Budget week: one warm instance avoids a 30 s cold start; until 2026-11-17\n"
        "# cost-ok: RS1 eight workers run a full answer's 11 simulations; each peaks near 0.4 GB\n"
        "gcloud run deploy uk-budget-api-2026 --min 1 --min-instances 0 --max 10 --cpu 8 --memory 8Gi\n"
    )
    assert rules_found("deploy.sh", deploy) == []
    assert sorted(declared_rules("deploy.sh", deploy)) == ["CR3", "RS1"]

    separated = (
        "# cost-ok: CR3 Budget week: one warm instance avoids a 30 s cold start; until 2026-11-17\n"
        "echo deploying\n"
        "gcloud run deploy uk-budget-api-2026 --min 1 --min-instances 0 --max 10\n"
    )
    assert rules_found("deploy.sh", separated) == [("CR3", "error")]


def test_todo_declaration_keeps_the_rule_at_its_own_severity():
    text = MODAL_WORKER.replace("memory=2048,", "memory=32768,  # cost-ok: RS1 TODO measured peak memory plus a fifth")
    findings, declarations = MODULE.check_file(Path("backend/app.py"), text, TODAY)
    assert [(finding.rule, finding.severity) for finding in findings] == [("RS1", "warning")]
    assert "not accepted" in findings[0].message
    assert declarations == []
