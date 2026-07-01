"""Regression test for the un-advertised dataset name silent fallback.

Surfaced 2026-06-29 by CDCC double: the runner requested `enhanced_cps_2024`
(a name not advertised at /metadata/economy_options/datasets). The API
silently fell back to the default (raw `cps`) — a much smaller,
uncalibrated sample. Results looked plausible but weren't publication-grade.

The fix (microsim-runner): only request advertised names + validate the
returned `data_version` to confirm what actually backed the run.
"""
from __future__ import annotations


ADVERTISED_DATASETS = {"cps", "enhanced_cps"}
KNOWN_BAD_NAMES = {
    "enhanced_cps_2024",
    "enhanced_cps_2024_2026",
    "enhanced_cps_2025",
    "populace",
    "populace_us_2024",
}


def request_is_valid(requested_dataset: str) -> bool:
    """Reject un-advertised dataset names before submission."""
    return requested_dataset in ADVERTISED_DATASETS


def validate_returned_data_version(requested: str, returned: str | None) -> dict:
    """Given the requested dataset name and the `data_version` from the API
    response, decide whether the request was honored."""
    if not returned:
        return {"dataset_honored": False, "backing": None, "warning": "no data_version"}
    lower = returned.lower()
    if "populace" in lower or "enhanced" in lower:
        backing = "populace-us-2024" if "populace" in lower else "enhanced-cps-vintage"
        return {"dataset_honored": True, "backing": backing}
    if "cps" in lower:
        # Raw CPS was returned. If we requested enhanced_cps, this is a silent fallback.
        return {
            "dataset_honored": requested == "cps",
            "backing": "cps-raw",
            "warning": "raw-CPS-backed; not publication-grade" if requested != "cps" else None,
        }
    return {"dataset_honored": False, "backing": "unknown", "warning": f"unrecognized data_version: {returned}"}


def test_advertised_names_valid():
    for name in ADVERTISED_DATASETS:
        assert request_is_valid(name), f"{name} should be valid"


def test_known_bad_names_rejected():
    for name in KNOWN_BAD_NAMES:
        assert not request_is_valid(name), f"{name} should be rejected"


def test_populace_backing_recognized():
    result = validate_returned_data_version(
        "enhanced_cps",
        "populace-us-2024-cd-concept-budget-dbbdcec-...20260627T022640Z",
    )
    assert result["dataset_honored"] is True
    assert result["backing"] == "populace-us-2024"


def test_enhanced_cps_backing_recognized():
    result = validate_returned_data_version(
        "enhanced_cps",
        "enhanced_cps_2024_v1.115.5",
    )
    assert result["dataset_honored"] is True
    assert "enhanced" in result["backing"]


def test_raw_cps_fallback_flagged():
    """The silent-fallback case: requested enhanced_cps, got raw cps back."""
    result = validate_returned_data_version(
        "enhanced_cps",
        "cps_v2.0",
    )
    assert result["dataset_honored"] is False
    assert result["backing"] == "cps-raw"
    assert "not publication-grade" in (result.get("warning") or "")
