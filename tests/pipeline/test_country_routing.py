"""Regression test for country-hardcoded issue routing.

Pre-2026-07-02, report-logger hardcoded `policyengine-us-data` for
INVESTIGATE-verdict issue routing and `policyengine-us` for structural.
UK/CA reforms would route to the wrong repo.

The fix: select issue destinations by the reform's jurisdiction.country,
including the US data repo's move to `PolicyEngine/microcosm`.
"""
from __future__ import annotations


def resolve_issue_repo(verdict: str, country: str) -> str | None:
    """Given verdict + country, return the target repo for auto-routed issues.

    Reference implementation of the rule documented in report-logger.md.
    """
    country_repo_map = {"us": "policyengine-us", "uk": "policyengine-uk", "ca": "policyengine-canada"}
    country_data_repo_map = {
        "us": "microcosm",
        "uk": "policyengine-uk-data",
        "ca": "policyengine-canada-data",
    }
    if verdict == "INVESTIGATE":
        return f"PolicyEngine/{country_data_repo_map[country]}"
    if verdict == "structural":
        return f"PolicyEngine/{country_repo_map[country]}"
    return None


def test_us_investigate_routes_correctly():
    assert resolve_issue_repo("INVESTIGATE", "us") == "PolicyEngine/microcosm"


def test_us_structural_routes_correctly():
    assert resolve_issue_repo("structural", "us") == "PolicyEngine/policyengine-us"


def test_uk_investigate_does_not_route_to_us_data():
    result = resolve_issue_repo("INVESTIGATE", "uk")
    assert result == "PolicyEngine/policyengine-uk-data"
    assert "us-data" not in result


def test_uk_structural_does_not_route_to_us():
    result = resolve_issue_repo("structural", "uk")
    assert result == "PolicyEngine/policyengine-uk"
    assert result != "PolicyEngine/policyengine-us"


def test_canada_investigate_routes_correctly():
    assert resolve_issue_repo("INVESTIGATE", "ca") == "PolicyEngine/policyengine-canada-data"


def test_pass_verdicts_dont_route_to_issues():
    for verdict in ("PASS", "PASS-WITH-NOTES", "PASS-WITH-CORROBORATION"):
        for country in ("us", "uk", "ca"):
            assert resolve_issue_repo(verdict, country) is None
