from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parent.parent
    / "targets"
    / "claude"
    / "hooks"
    / "model-development-context.py"
)


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_adds_context_inside_a_country_model_checkout(tmp_path: Path) -> None:
    (tmp_path / "policyengine_us").mkdir()
    nested = tmp_path / "policyengine_us" / "variables"
    nested.mkdir()
    for event_name in ("SessionStart", "SubagentStart"):
        result = run_hook(
            json.dumps({"hook_event_name": event_name, "cwd": str(nested)})
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)["hookSpecificOutput"]
        assert output["hookEventName"] == event_name
        assert "policyengine-model-development" in output["additionalContext"]
        assert "SKILLS_READY" in output["additionalContext"]


def test_stays_silent_outside_country_models(tmp_path: Path) -> None:
    result = run_hook(
        json.dumps({"hook_event_name": "SessionStart", "cwd": str(tmp_path)})
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_ignores_other_events_and_bad_input(tmp_path: Path) -> None:
    (tmp_path / "policyengine_uk").mkdir()
    for stdin in (
        json.dumps({"hook_event_name": "PostToolUse", "cwd": str(tmp_path)}),
        json.dumps({"hook_event_name": "SessionStart"}),
        "not json",
        "",
        "[]",
    ):
        result = run_hook(stdin)
        assert result.returncode == 0, (stdin, result.stderr)
        assert result.stdout == ""
        assert result.stderr == ""
