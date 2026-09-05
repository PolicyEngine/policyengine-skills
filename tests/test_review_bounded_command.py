"""Run actual subprocesses to protect deadline and exit-status propagation."""

from pathlib import Path
import subprocess
import sys
import time


SCRIPT = (
    Path(__file__).resolve().parents[1] / "skills/review-program/scripts/run_bounded.py"
)


def test_preserves_captured_stdout_and_failure_status():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--seconds",
            "5",
            sys.executable,
            "-c",
            "print('captured-sha'); raise SystemExit(7)",
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 7
    assert result.stdout == "captured-sha\n"


def test_timeout_kills_descendants_and_closes_inherited_pipes():
    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--seconds",
            "0.2",
            sys.executable,
            "-c",
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
            "time.sleep(30)",
        ],
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 124
    assert "timed out" in result.stderr
    assert time.monotonic() - started < 5
