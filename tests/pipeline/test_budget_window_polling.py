"""Polling contract for microsim-runner's budget-window helper.

policyengine-api's budget-window route answers `status: "computing"` until its
batch finishes, then `"ok"` with the result, or `"error"` with the reason in
`error` (`policyengine_api/services/economy_budget_window_results.py` and
`economy_impact_types.py` at fe2d09da0). A batch can also stall: on 2026-11-08
a two-year US window for policy 97853 still read "Scoring 2026, 2027 (0 of 2
complete)..." after more than half an hour. These tests run `run_horizon`
straight from microsim-runner.md against scripted answers and a fake clock, so
the agent's code and the tests can't drift apart.

Invariants, for any sequence of answers and any deadline:
- `run_horizon` returns the result of the first "ok" answer, never None;
- any status other than "computing" or "ok" raises RuntimeError carrying the
  API's reason;
- a batch that keeps computing raises TimeoutError at the first poll at or
  after the deadline, never earlier, and a terminal answer that arrives before
  that poll gets handled;
- it sends no request after a terminal answer;
- every request carries the region, start year and window it was given and a
  timeout, and no `dataset`.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from hypothesis import given
from hypothesis import strategies as st

REPO_ROOT = Path(__file__).resolve().parents[2]
MICROSIM_RUNNER = REPO_ROOT / "targets" / "claude" / "agents" / "microsim-runner.md"
PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)

RESULT = {"kind": "budgetWindow", "startYear": "2026", "endYear": "2035", "windowSize": 10}
COMPUTING = {
    "status": "computing",
    "message": "Scoring 2029 (3 of 10 complete)...",
    "result": None,
    "progress": 30,
    "error": None,
}
# The live answer that never moved on 2026-11-08 (19:26Z to past 19:59Z).
STALLED = {
    "status": "computing",
    "message": "Scoring 2026, 2027 (0 of 2 complete)...",
    "result": None,
    "progress": 0,
    "completed_years": [],
    "computing_years": ["2026", "2027"],
    "queued_years": [],
    "error": None,
}
OK = {"status": "ok", "message": None, "result": RESULT, "progress": 100, "error": None}
FAILED = {
    "status": "error",
    "message": "Budget-window batch failed",
    "result": None,
    "error": "Budget-window batch failed",
}


@lru_cache(maxsize=1)
def run_horizon_source() -> str:
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    blocks = [block for block in PYTHON_BLOCK.findall(text) if "def run_horizon(" in block]
    assert len(blocks) == 1, f"expected one run_horizon block in microsim-runner.md, found {len(blocks)}"
    return blocks[0]


class FakeClock:
    """Stands in for the `time` module: `sleep` moves `monotonic` forward."""

    def __init__(self, start: float = 1_000.0):
        self.start = start
        self.now = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds > 0
        self.sleeps.append(seconds)
        self.now += seconds

    @property
    def elapsed(self) -> float:
        return self.now - self.start

    @property
    def longest_sleep(self) -> float:
        return max(self.sleeps, default=0.0)


class FakeResponse:
    def __init__(self, body: dict):
        self.body = body

    def json(self) -> dict:
        return self.body


class ScriptedAPI:
    """Stands in for `requests`: each GET returns the next scripted answer."""

    def __init__(self, bodies: list[dict]):
        self.bodies = bodies
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        if len(self.calls) == len(self.bodies):
            raise AssertionError("run_horizon polled past the end of the script")
        self.calls.append((url, kwargs))
        return FakeResponse(self.bodies[len(self.calls) - 1])


def poll(bodies: list[dict], **overrides):
    """Run the runner's `run_horizon` on scripted answers; return (outcome, api, clock)."""
    api, clock = ScriptedAPI(bodies), FakeClock()
    namespace = {"requests": api, "time": clock}
    exec(compile(run_horizon_source(), str(MICROSIM_RUNNER), "exec"), namespace)  # noqa: S102
    args = {
        "country": "us",
        "region": "us",
        "policy_id": 97853,
        "baseline_id": 2,
        "start_year": 2026,
        "window_size": 10,
        **overrides,
    }
    try:
        outcome = namespace["run_horizon"](**args)
    except (RuntimeError, TimeoutError) as error:
        outcome = error
    return outcome, api, clock


def default_wait_minutes() -> int:
    match = re.search(r"max_wait_minutes=(\d+)", run_horizon_source())
    assert match, "run_horizon no longer takes max_wait_minutes"
    return int(match.group(1))


# --- Examples ---------------------------------------------------------------


def test_returns_the_result_when_the_batch_finishes():
    outcome, api, _ = poll([COMPUTING, COMPUTING, OK])
    assert outcome is RESULT
    assert len(api.calls) == 3


def test_raises_the_api_reason_on_error():
    outcome, api, _ = poll([COMPUTING, FAILED])
    assert isinstance(outcome, RuntimeError)
    assert str(outcome) == "Budget-window batch failed"
    assert len(api.calls) == 2


def test_stalled_batch_times_out_so_the_runner_can_fall_back():
    minutes = default_wait_minutes()
    outcome, api, clock = poll([STALLED] * (60 * minutes + 2))
    assert isinstance(outcome, TimeoutError)
    assert "0 of 2 complete" in str(outcome)
    assert 60 * minutes <= clock.elapsed < 60 * minutes + clock.longest_sleep


def test_prose_states_the_default_deadline():
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    assert f"keeps computing past {default_wait_minutes()} minutes" in text


# --- Properties -------------------------------------------------------------

regions = st.sampled_from(["us", "state/ca", "ca", "congressional_district/CA-01"])
endings = st.sampled_from([OK, FAILED, {"status": "failed", "error": "batch lost"}, None])


@given(
    n_computing=st.integers(min_value=0, max_value=150),
    ending=endings,
    max_wait=st.integers(min_value=1, max_value=120),
    region=regions,
    start_year=st.integers(min_value=2024, max_value=2035),
    window_size=st.integers(min_value=1, max_value=10),
)
def test_run_horizon_contract(n_computing, ending, max_wait, region, start_year, window_size):
    bodies = [COMPUTING] * n_computing
    # A batch that never finishes keeps answering "computing" past any deadline.
    bodies += [ending] if ending is not None else [COMPUTING] * (max_wait * 60 + 2)
    outcome, api, clock = poll(
        bodies,
        region=region,
        start_year=start_year,
        window_size=window_size,
        max_wait_minutes=max_wait,
    )
    deadline = 60 * max_wait
    answered = api.bodies[: len(api.calls)]

    assert outcome is not None
    if isinstance(outcome, TimeoutError):
        assert all(body["status"] == "computing" for body in answered)
        assert deadline <= clock.elapsed < deadline + clock.longest_sleep
    else:
        assert answered[-1] is ending, "returned or raised before the terminal answer"
        assert all(body["status"] == "computing" for body in answered[:-1])
        assert clock.elapsed < deadline + clock.longest_sleep, "kept polling past the deadline"
        if ending is OK:
            assert outcome is RESULT
        else:
            assert isinstance(outcome, RuntimeError)
            assert str(outcome) == ending["error"]

    for url, kwargs in api.calls:
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.path == "/us/economy/97853/over/2/budget-window"
        assert query == {
            "region": [region],
            "start_year": [str(start_year)],
            "window_size": [str(window_size)],
        }
        assert kwargs.get("timeout", 0) > 0


@given(n_before=st.integers(min_value=0, max_value=40))
def test_answer_well_before_the_deadline_never_times_out(n_before):
    outcome, _, _ = poll([COMPUTING] * n_before + [OK], max_wait_minutes=24 * 60)
    assert outcome is RESULT


@pytest.mark.parametrize("ending", [OK, FAILED])
def test_no_request_after_a_terminal_answer(ending):
    _, api, _ = poll([COMPUTING, ending, COMPUTING, OK])
    assert len(api.calls) == 2


def test_terminal_answer_on_the_timeout_poll_wins():
    _, stalled_api, _ = poll([STALLED] * (60 * default_wait_minutes() + 2))
    timeout_poll = len(stalled_api.calls) - 1
    outcome, api, _ = poll([COMPUTING] * timeout_poll + [OK])
    assert outcome is RESULT
    assert len(api.calls) == timeout_poll + 1
