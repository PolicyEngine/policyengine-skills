"""Execute the workflow's actual shell blocks against isolated Git repositories.

GitHub metadata is stubbed; fetch, diff, snapshot creation, and cleanup use real Git.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


WORKFLOW = (
    Path(__file__).resolve().parents[1] / "skills/review-program/references/workflow.md"
)


def block_after(anchor: str) -> str:
    section = WORKFLOW.read_text().split(anchor, 1)[1]
    match = re.search(r"```bash\n(.*?)```", section, re.DOTALL)
    assert match, f"Missing executable block after {anchor}"
    return match.group(1)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Workflow Test",
            "-c",
            "user.email=workflow@example.invalid",
            *args,
        ],
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


@pytest.fixture
def checkout(tmp_path: Path) -> dict[str, str]:
    repo = tmp_path / "working repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "policy.py").write_text("benefit = 0\n")
    git(repo, "add", "policy.py")
    git(repo, "commit", "-m", "Base")
    git(repo, "checkout", "-b", "feature")
    (repo / "policy.py").write_text("benefit = 100\n")
    git(repo, "commit", "-am", "Remote PR")
    remote_head = git(repo, "rev-parse", "HEAD")
    (repo / "policy.py").write_text("benefit = 200\n")
    git(repo, "commit", "-am", "Unpushed local commit")
    local_head = git(repo, "rev-parse", "HEAD")

    remote = tmp_path / "upstream repo.git"
    git(repo, "clone", "--bare", str(repo), str(remote))
    git(remote, "update-ref", "refs/pull/7/head", remote_head)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  *"--json url"*) printf "%s/pull/7\\n" "$TEST_REMOTE_URL" ;;\n'
        '  *"--json baseRefName"*) printf "main\\n" ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)
    run_root = tmp_path / "run artifacts"
    run_root.mkdir()
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "WORKTREE_ROOT": str(repo),
        "RUN_ROOT": str(run_root),
        "PREFIX": "test-program",
        "PR_NUMBER": "7",
        "BASE_REPO": "PolicyEngine/test-model",
        "REVIEW_SKILL_ROOT": str(WORKFLOW.parent.parent),
        "LOCAL_DIFF": "false",
        "TEST_REMOTE_URL": str(remote),
        "TEST_REMOTE_HEAD": remote_head,
        "TEST_LOCAL_HEAD": local_head,
    }


def shell(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", code],
        env=env,
        cwd=env["RUN_ROOT"],  # Do not depend on the shell's current repository.
        capture_output=True,
        text=True,
        timeout=30,
    )


def capture_and_snapshot(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return shell(
        block_after("authoritatively:")
        + block_after("**Materialize the PR's file contents.**")
        + '\nprintf "%s\\n" "$SNAPSHOT"',
        env,
    )


def snapshot_path(result: subprocess.CompletedProcess[str]) -> Path:
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.splitlines()[-1])


@pytest.mark.parametrize("local_diff", [False, True])
def test_diff_and_snapshot_use_same_selected_commit(checkout, local_diff) -> None:
    repo = Path(checkout["WORKTREE_ROOT"])
    (repo / "policy.py").write_text("benefit = 300\n")
    git(repo, "add", "policy.py")
    (repo / "policy.py").write_text("benefit = 999\n")
    (repo / "local-only.py").write_text("untracked = True\n")
    before = git(repo, "status", "--porcelain")

    snapshot = snapshot_path(
        capture_and_snapshot(
            {
                **checkout,
                "LOCAL_DIFF": str(local_diff).lower(),
            }
        )
    )
    expected = "200" if local_diff else "100"
    expected_head = checkout["TEST_LOCAL_HEAD" if local_diff else "TEST_REMOTE_HEAD"]
    assert git(snapshot, "rev-parse", "HEAD") == expected_head
    assert (snapshot / "policy.py").read_text() == f"benefit = {expected}\n"
    assert not (snapshot / "local-only.py").exists()
    diff = (Path(checkout["RUN_ROOT"]) / "test-program-review-diff.txt").read_text()
    assert f"+benefit = {expected}\n" in diff
    assert "999" not in diff and "300" not in diff and "local-only" not in diff
    assert git(repo, "status", "--porcelain") == before
    assert git(repo, "rev-parse", "HEAD") == checkout["TEST_LOCAL_HEAD"]
    assert git(repo, "branch", "--show-current") == "feature"


@pytest.mark.parametrize("dirty", [False, True])
def test_matching_head_still_gets_an_isolated_snapshot(checkout, dirty) -> None:
    repo = Path(checkout["WORKTREE_ROOT"])
    git(repo, "checkout", "--detach", checkout["TEST_REMOTE_HEAD"])
    if dirty:
        (repo / "policy.py").write_text("benefit = 999\n")
    snapshot = snapshot_path(capture_and_snapshot(checkout))
    assert snapshot != repo
    assert (snapshot / "policy.py").read_text() == "benefit = 100\n"
    # Even a clean checkout can change after snapshot creation.
    (repo / "policy.py").write_text("benefit = 888\n")
    assert (snapshot / "policy.py").read_text() == "benefit = 100\n"


def test_local_diff_does_not_require_remote_pr_head(checkout) -> None:
    git(Path(checkout["TEST_REMOTE_URL"]), "update-ref", "-d", "refs/pull/7/head")
    snapshot = snapshot_path(capture_and_snapshot({**checkout, "LOCAL_DIFF": "true"}))
    assert git(snapshot, "rev-parse", "HEAD") == checkout["TEST_LOCAL_HEAD"]


@pytest.mark.parametrize("missing_ref", ["refs/pull/7/head", "refs/heads/main"])
def test_failed_fetch_stops_before_diff_or_snapshot(checkout, missing_ref) -> None:
    git(Path(checkout["TEST_REMOTE_URL"]), "update-ref", "-d", missing_ref)
    result = capture_and_snapshot(checkout)
    assert result.returncode != 0
    assert list(Path(checkout["RUN_ROOT"]).iterdir()) == []


def test_cleanup_removes_only_this_invocations_snapshot(checkout) -> None:
    first = snapshot_path(capture_and_snapshot(checkout))
    (first / "keep.txt").write_text("Earlier run's artifact\n")
    second = snapshot_path(capture_and_snapshot(checkout))
    assert first != second
    cleanup = block_after("Finally, on success or failure,")
    result = shell(cleanup, {**checkout, "SNAPSHOT": str(second)})
    assert result.returncode == 0, result.stderr
    assert not second.exists()
    assert (first / "keep.txt").exists()
    assert Path(checkout["WORKTREE_ROOT"]).exists()
    assert (Path(checkout["RUN_ROOT"]) / "test-program-review-diff.txt").exists()


def test_cleanup_preserves_unexpected_snapshot_changes(checkout) -> None:
    snapshot = snapshot_path(capture_and_snapshot(checkout))
    (snapshot / "keep.txt").write_text("Unexpected file\n")
    result = shell(
        block_after("Finally, on success or failure,"),
        {**checkout, "SNAPSHOT": str(snapshot)},
    )
    assert result.returncode != 0
    assert (snapshot / "keep.txt").read_text() == "Unexpected file\n"
