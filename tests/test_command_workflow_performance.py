from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / "targets" / "claude" / "commands"
SKILL_WORKFLOWS = REPO_ROOT / "skills"


def command_text(name: str) -> str:
    return (COMMANDS / f"{name}.md").read_text()


def test_long_running_commands_have_resumable_run_state() -> None:
    expected_ledgers = {
        "encode-policy-v2": "encode-run-state.md",
        "review-program": "review-run-state.md",
        "fix-pr": "fix-pr-run-state.md",
    }

    for command, ledger in expected_ledgers.items():
        text = command_text(command)
        assert "--resume" in text
        assert ledger in text


def test_encode_establishes_variable_contract_before_tests() -> None:
    text = command_text("encode-policy-v2")

    implementation_manifest = text.index("implementation-manifest.md")
    test_manifest = text.index("test-manifest.md")
    assert implementation_manifest < test_manifest
    assert "Create Variables and Tests (Parallel)" not in text
    assert "states/{ST}/... -c policyengine_us -v" not in text


def test_review_program_supports_incremental_evidence_reuse() -> None:
    text = command_text("review-program")

    assert "--incremental REPORT" in text
    assert "Reviewed head SHA" in text
    assert "Render only assigned or disputed pages" in text


def test_fix_pr_artifacts_are_worktree_scoped() -> None:
    text = command_text("fix-pr")

    assert "{RUN_ROOT}/{PREFIX}-fix-pr-diff.txt" in text
    assert "-v -d 2" in text


def test_ci_fixer_uses_bounded_targeted_funnel() -> None:
    text = (
        REPO_ROOT
        / "targets"
        / "claude"
        / "agents"
        / "country-models"
        / "ci-fixer.md"
    ).read_text()

    assert "Maximum 4 targeted fix iterations" in text
    assert "-v -d 2" in text
    assert "Maximum 8 fix iterations" not in text


def test_commands_and_skills_derive_the_same_worktree_namespace() -> None:
    texts = [command_text(name) for name in ("encode-policy-v2", "review-program", "fix-pr")]
    texts.extend(
        (
            SKILL_WORKFLOWS / name / "references" / "workflow.md"
        ).read_text()
        for name in ("encode-policy-v2", "review-program", "fix-pr")
    )

    for text in texts:
        assert "WORKTREE_ROOT=$(git rev-parse --show-toplevel)" in text
        assert "git hash-object --stdin" in text
        assert 'RUN_ROOT="/tmp/policyengine-command-runs/$WORKTREE_ID"' in text
        assert "{RUN_ROOT}/{PREFIX}-" in text


def test_mutating_workflows_protect_other_worktrees() -> None:
    for name in ("encode-policy-v2", "fix-pr"):
        command = command_text(name)
        workflow = (
            SKILL_WORKFLOWS / name / "references" / "workflow.md"
        ).read_text()
        for text in (command, workflow):
            assert "git worktree list --porcelain" in text
            assert "--ignore-other-worktrees" in text

    review_command = command_text("review-program")
    assert "read-only across the whole worktree set" in review_command
    assert "never switch or detach any" in review_command
    assert "--local-diff" in review_command
