"""Regression tests for the scorekeepers registry.

Guarantees the registry stays extensible + filterable + non-empty for the
three supported countries.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.scorekeepers import list_scorekeepers  # noqa: E402


def test_us_has_tier_2():
    sks = list_scorekeepers(country="us", tier=2)
    assert len(sks) >= 2, "US must have at least 2 tier-2 scorekeepers"
    names = {sk["name"] for sk in sks}
    assert "JCT" in names, "JCT must be present"
    assert "CBO" in names, "CBO must be present"


def test_us_has_tier_3_beyond_the_original_five():
    """We should now have more than just CRFB/TPC/TF/CBPP/ITEP."""
    sks = list_scorekeepers(country="us", tier=3)
    names = {sk["name"] for sk in sks}
    # The originals must still be present
    for original in ("CRFB", "TPC", "Tax Foundation", "CBPP", "ITEP"):
        assert original in names, f"original tier-3 {original} missing"
    # Plus the newly-added ones
    newer_expected = {"Penn Wharton Budget Model", "Yale Budget Lab", "Brookings", "BPC"}
    assert newer_expected.issubset(names), (
        f"expected newer tier-3 sources {newer_expected - names} missing from registry"
    )


def test_uk_has_tier_2_and_tier_3():
    tier_2 = {sk["name"] for sk in list_scorekeepers(country="uk", tier=2)}
    tier_3 = {sk["name"] for sk in list_scorekeepers(country="uk", tier=3)}
    assert "OBR" in tier_2, "OBR must be in UK tier-2"
    assert "IFS" in tier_3, "IFS must be in UK tier-3"
    assert "Resolution Foundation" in tier_3, "Resolution Foundation must be in UK tier-3"


def test_ca_has_tier_2_and_tier_3():
    tier_2 = {sk["name"] for sk in list_scorekeepers(country="ca", tier=2)}
    tier_3 = {sk["name"] for sk in list_scorekeepers(country="ca", tier=3)}
    assert "PBO" in tier_2, "PBO must be in Canada tier-2"
    assert "CD Howe" in tier_3, "CD Howe must be in Canada tier-3"


def test_global_sources_appear_for_every_country():
    """OECD and IMF are marked jurisdictions: [global] and should surface for any country."""
    for country in ("us", "uk", "ca"):
        sks = list_scorekeepers(country=country, tier=3)
        names = {sk["name"] for sk in sks}
        assert "OECD" in names, f"OECD should surface for country={country}"
        assert "IMF" in names, f"IMF should surface for country={country}"


def test_no_global_flag_excludes_oecd_imf():
    sks = list_scorekeepers(country="us", tier=3, include_global=False)
    names = {sk["name"] for sk in sks}
    assert "OECD" not in names
    assert "IMF" not in names


def test_domain_filter_works():
    """Filtering by domain=healthcare should surface healthcare-relevant sources."""
    sks = list_scorekeepers(country="us", tier=3, domain="healthcare")
    names = {sk["name"] for sk in sks}
    assert "AEI" in names or "Brookings" in names, (
        "expected at least one healthcare-domain tier-3 source (AEI or Brookings)"
    )


def test_all_scorekeepers_have_required_fields():
    """Every registry entry must have the required fields, so agents can rely on them."""
    from scripts.scorekeepers import _load_registry
    for sk in _load_registry():
        for field in ("name", "full_name", "tier", "jurisdictions", "domains", "url"):
            assert field in sk, f"scorekeeper {sk.get('name', '?')} missing field {field}"
        assert sk["tier"] in (2, 3), f"{sk['name']} has invalid tier={sk['tier']}"
        assert isinstance(sk["jurisdictions"], list), f"{sk['name']} jurisdictions must be a list"
        assert isinstance(sk["domains"], list), f"{sk['name']} domains must be a list"
