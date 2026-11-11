"""Polling contract for microsim-runner's budget-window helper.

policyengine-api's budget-window route answers `status: "computing"` until its
batch finishes, then `"ok"` with the result, or `"error"` with the reason in
`error` (`policyengine_api/services/economy_budget_window_results.py` and
`economy_impact_types.py` at fe2d09da0). A failed batch answers HTTP 200. The
route answers HTTP 502 with only a `message` when it can't reach the
simulation service, and HTTP 400 or 404 when it refuses the request
(`policyengine_api/routes/economy_routes.py`). A batch can also stall: on
2026-11-08 a two-year US window for policy 97853 still read "Scoring 2026,
2027 (0 of 2 complete)..." after more than half an hour. These tests run
`run_horizon` straight from microsim-runner.md against scripted answers and a
fake clock, so the agent's code and the tests can't drift apart.

Invariants, for any sequence of answers and any deadline:
- `run_horizon` returns the result of the first "ok" answer;
- any other status but "computing" raises RuntimeError carrying the API's
  reason, from `error` or else `message`;
- HTTP 400 or 404 raises ValueError carrying the API's message;
- a poll that times out, fails to connect or answers with something other than
  JSON doesn't end the wait;
- a batch that keeps computing raises TimeoutError at the first poll at or
  after the deadline, never earlier, and a terminal answer on that poll still
  wins;
- it sends no request after a terminal answer, and waits 30 to 60 seconds
  between polls;
- every request goes to the country's route and carries the region, start year
  and window it got, a timeout of at most 120 seconds, and no `dataset`.
"""
from __future__ import annotations

import builtins
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from hypothesis import given, settings
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
# The live answer from 19:27Z to past 19:59Z on 2026-11-08.
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


class FakeRequestException(OSError):
    """Stands in for `requests.RequestException`."""


class ReadTimeout(FakeRequestException):
    """Stands in for `requests.ReadTimeout`, which no TimeoutError handler catches."""


class Answer:
    """One scripted HTTP answer: a JSON body and its status code, or a body that isn't JSON."""

    def __init__(self, body=None, status_code: int = 200, json_ok: bool = True):
        self.body = body
        self.status_code = status_code
        self.json_ok = json_ok

    def json(self) -> dict:
        if not self.json_ok:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self.body


# The API's answers when it can't reach the simulation service (whose error text
# varies; this one stands in for it) or refuses the request. The 400 and 404
# messages copy `dataset_year_unavailable_message` and `_policy_not_found_response`.
UNREACHABLE = Answer(
    {
        "status": "error",
        "message": "Simulation service unreachable",
        "result": None,
        "retry_after_seconds": None,
    },
    status_code=502,
)
BAD_REQUEST = Answer(
    {
        "status": "error",
        "message": "US results are available for 2024 to 2035. "
        "2040 is outside the years the current US model and data cover.",
    },
    status_code=400,
)
NOT_FOUND = Answer({"status": "error", "message": "Policy #99999999 not found."}, status_code=404)
# Polls that fail while the batch keeps running.
TIMED_OUT = ReadTimeout("Read timed out. (read timeout=120)")
NOT_JSON = Answer(json_ok=False, status_code=503)


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


class ScriptedAPI:
    """Stands in for `requests`: each GET gives the next scripted answer.

    A dict answers as an HTTP 200 JSON body and an `Answer` as itself. For an
    exception, `get` raises it, as `requests` does on a timeout or a broken
    connection.
    """

    RequestException = FakeRequestException

    def __init__(self, script: list):
        self.script = script
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs) -> Answer:
        if len(self.calls) == len(self.script):
            raise AssertionError("run_horizon polled past the end of the script")
        self.calls.append((url, kwargs))
        step = self.script[len(self.calls) - 1]
        if isinstance(step, BaseException):
            raise step
        return step if isinstance(step, Answer) else Answer(step)


@lru_cache(maxsize=1)
def run_horizon_source() -> str:
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    blocks = [block for block in PYTHON_BLOCK.findall(text) if "def run_horizon(" in block]
    assert len(blocks) == 1, f"expected one run_horizon block in microsim-runner.md, found {len(blocks)}"
    return blocks[0]


def poll(script: list, **overrides):
    """Run the runner's `run_horizon` on scripted answers; return (outcome, api, clock).

    The block's own `import time` and `import requests` get the fake clock and API.
    """
    api, clock = ScriptedAPI(script), FakeClock()
    fakes = {"time": clock, "requests": api}

    def fake_import(name, *args, **kwargs):
        return fakes[name] if name in fakes else builtins.__import__(name, *args, **kwargs)

    namespace = {"__builtins__": {**vars(builtins), "__import__": fake_import}}
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
    except (RuntimeError, TimeoutError, ValueError) as error:
        outcome = error
    return outcome, api, clock


def default_wait_minutes() -> int:
    match = re.search(r"max_wait_minutes=(\d+)", run_horizon_source())
    assert match, "run_horizon no longer takes max_wait_minutes"
    return int(match.group(1))


def is_waiting(step) -> bool:
    """True for an answer that keeps the wait going: computing, or a failed poll."""
    if isinstance(step, BaseException):
        return True
    if isinstance(step, Answer):
        return not step.json_ok
    return step["status"] == "computing"


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


def test_unreachable_service_raises_its_message():
    outcome, api, _ = poll([COMPUTING, UNREACHABLE])
    assert isinstance(outcome, RuntimeError)
    assert str(outcome) == "Simulation service unreachable"
    assert len(api.calls) == 2


@pytest.mark.parametrize("refusal", [BAD_REQUEST, NOT_FOUND])
def test_refused_request_raises_value_error_and_stops(refusal):
    outcome, api, _ = poll([refusal, COMPUTING, OK])
    assert isinstance(outcome, ValueError)
    assert str(outcome) == refusal.body["message"]
    assert len(api.calls) == 1


def test_a_failed_poll_does_not_end_the_wait():
    outcome, api, clock = poll([COMPUTING, TIMED_OUT, NOT_JSON, COMPUTING, OK])
    assert outcome is RESULT
    assert len(api.calls) == 5
    assert len(clock.sleeps) == 4


def test_stalled_batch_times_out_so_the_runner_can_fall_back():
    minutes = default_wait_minutes()
    outcome, api, clock = poll([STALLED] * (60 * minutes + 2))
    assert isinstance(outcome, TimeoutError)
    assert "0 of 2 complete" in str(outcome)
    assert 60 * minutes <= clock.elapsed < 60 * minutes + clock.longest_sleep


def test_timeout_after_a_failed_poll_names_the_failure():
    minutes = default_wait_minutes()
    outcome, _, _ = poll([STALLED] * (minutes - 1) + [TIMED_OUT] * (60 * minutes))
    assert isinstance(outcome, TimeoutError)
    assert "Read timed out" in str(outcome)


def test_prose_states_the_default_deadline():
    text = MICROSIM_RUNNER.read_text(encoding="utf-8")
    assert f"keeps computing past {default_wait_minutes()} minutes" in text


# --- Properties -------------------------------------------------------------

countries = st.sampled_from(["us", "uk"])
regions = st.sampled_from(["us", "state/ca", "ca", "congressional_district/CA-01", "uk", "country/scotland"])
waiting = st.sampled_from([COMPUTING, STALLED, TIMED_OUT, NOT_JSON])
endings = st.sampled_from(
    [OK, FAILED, {"status": "failed", "error": "batch lost"}, UNREACHABLE, BAD_REQUEST, NOT_FOUND, None]
)


@settings(deadline=None)
@given(
    prefix=st.lists(waiting, max_size=150),
    ending=endings,
    max_wait=st.integers(min_value=1, max_value=120),
    country=countries,
    region=regions,
    start_year=st.integers(min_value=2024, max_value=2035),
    window_size=st.integers(min_value=1, max_value=10),
)
def test_run_horizon_contract(prefix, ending, max_wait, country, region, start_year, window_size):
    # A batch that never finishes keeps answering "computing" past any deadline.
    script = prefix + ([ending] if ending is not None else [COMPUTING] * (max_wait * 60 + 2))
    outcome, api, clock = poll(
        script,
        country=country,
        region=region,
        start_year=start_year,
        window_size=window_size,
        max_wait_minutes=max_wait,
    )
    deadline = 60 * max_wait
    answered = api.script[: len(api.calls)]

    assert outcome is not None
    assert all(30 <= seconds <= 60 for seconds in clock.sleeps), clock.sleeps
    assert len(clock.sleeps) == len(api.calls) - 1, "a poll ended without a wait, or waited twice"
    if isinstance(outcome, TimeoutError):
        assert all(is_waiting(step) for step in answered)
        assert deadline <= clock.elapsed < deadline + clock.longest_sleep
    else:
        assert answered[-1] is ending, "returned or raised before the terminal answer"
        assert all(is_waiting(step) for step in answered[:-1])
        assert clock.elapsed < deadline + clock.longest_sleep, "kept polling past the deadline"
        if ending is OK:
            assert outcome is RESULT
        elif ending in (BAD_REQUEST, NOT_FOUND):
            assert isinstance(outcome, ValueError)
            assert str(outcome) == ending.body["message"]
        else:
            body = ending.body if isinstance(ending, Answer) else ending
            assert isinstance(outcome, RuntimeError)
            assert str(outcome) == (body.get("error") or body["message"])

    for url, kwargs in api.calls:
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.path == f"/{country}/economy/97853/over/2/budget-window"
        assert query == {
            "region": [region],
            "start_year": [str(start_year)],
            "window_size": [str(window_size)],
        }
        assert 0 < kwargs.get("timeout", 0) <= 120


@settings(deadline=None)
@given(n_before=st.integers(min_value=0, max_value=40))
def test_answer_well_before_the_deadline_never_times_out(n_before):
    outcome, _, _ = poll([COMPUTING] * n_before + [OK], max_wait_minutes=24 * 60)
    assert outcome is RESULT


@pytest.mark.parametrize("ending", [OK, FAILED, UNREACHABLE, BAD_REQUEST])
def test_no_request_after_a_terminal_answer(ending):
    _, api, _ = poll([COMPUTING, ending, COMPUTING, OK])
    assert len(api.calls) == 2


def test_terminal_answer_on_the_timeout_poll_wins():
    _, stalled_api, _ = poll([STALLED] * (60 * default_wait_minutes() + 2))
    timeout_poll = len(stalled_api.calls) - 1
    outcome, api, _ = poll([COMPUTING] * timeout_poll + [OK])
    assert outcome is RESULT
    assert len(api.calls) == timeout_poll + 1
