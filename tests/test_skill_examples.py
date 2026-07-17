"""Execute the skills' marked code examples against the live policyengine stack.

A fenced ```python block whose preceding non-empty line is exactly
``<!-- verify -->`` is a *fast* example: self-contained, household-tier, and
asserted. This test runs each one in a subprocess.

``<!-- verify: slow -->`` marks population-scale examples (multi-GB datasets,
tens of GB of RAM). Those only run when ``PE_SKILLS_RUN_SLOW=1`` is set —
they are executed at authoring time and on demand, not in PR CI.

Both tiers require the ``policyengine`` package; the whole module skips when
it is not installed (CI installs it in a dedicated job).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

try:  # pragma: no cover - environment probe
    import policyengine  # noqa: F401

    HAS_POLICYENGINE = True
except Exception:  # pragma: no cover
    HAS_POLICYENGINE = False

BLOCK_RE = re.compile(
    r"<!--\s*verify(?P<slow>:\s*slow)?\s*-->\s*\n```python\n(?P<code>.*?)```",
    re.DOTALL,
)


def collect_examples() -> list[tuple[str, str, bool]]:
    examples: list[tuple[str, str, bool]] = []
    for skill_md in sorted((REPO_ROOT / "skills").glob("**/*.md")):
        text = skill_md.read_text()
        for index, match in enumerate(BLOCK_RE.finditer(text)):
            rel = skill_md.relative_to(REPO_ROOT)
            examples.append(
                (f"{rel}#{index}", match.group("code"), bool(match.group("slow")))
            )
    return examples


EXAMPLES = collect_examples()


def test_examples_were_collected() -> None:
    """The harness itself must not silently go blind."""
    assert any(not slow for _, _, slow in EXAMPLES), (
        "no fast <!-- verify --> examples found under skills/"
    )


@pytest.mark.skipif(not HAS_POLICYENGINE, reason="policyengine not installed")
@pytest.mark.parametrize(
    "example_id,code,slow",
    EXAMPLES,
    ids=[example_id for example_id, _, _ in EXAMPLES],
)
def test_skill_example_runs(example_id: str, code: str, slow: bool) -> None:
    if slow and os.environ.get("PE_SKILLS_RUN_SLOW") != "1":
        pytest.skip("slow example; set PE_SKILLS_RUN_SLOW=1 to run")
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=1800 if slow else 300,
    )
    assert result.returncode == 0, (
        f"{example_id} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
