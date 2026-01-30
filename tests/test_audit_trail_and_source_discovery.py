"""
Sample tests for audit trail (claim tiers, P(error)) and secondary→primary source discovery.

Run: pytest tests/test_audit_trail_and_source_discovery.py -v
"""
import pytest
from app.kg.audit_trail import (
    CLAIM_TIERS,
    compute_p_error,
    assign_confidence_tier,
    enrich_claim_with_audit,
)
from app.kg.source_discovery import (
    canonicalize_primary_identifiers,
    enrich_source_with_primary_identifiers,
)


class TestAuditTrail:
    """Audit trail: claim tiers and P(error)."""

    def test_claim_tiers_constant(self):
        assert CLAIM_TIERS == ("Provisional", "Supported", "Audited")

    def test_compute_p_error(self):
        assert compute_p_error(1.0) == 0.0
        assert compute_p_error(0.0) == 1.0
        assert compute_p_error(0.7) == pytest.approx(0.3, abs=1e-6)
        assert compute_p_error(0.5) == 0.5

    def test_assign_confidence_tier_low_confidence(self):
        assert assign_confidence_tier(0.4) == "Provisional"
        assert assign_confidence_tier(0.5) == "Provisional"
        assert assign_confidence_tier(0.6) == "Provisional"

    def test_assign_confidence_tier_high_confidence(self):
        assert assign_confidence_tier(0.8) == "Supported"
        assert assign_confidence_tier(0.9) == "Supported"
        assert assign_confidence_tier(1.0) == "Supported"

    def test_assign_confidence_tier_capped_by_effective_primary(self):
        # With effective_primary below tau_p, confidence is capped → stays Provisional
        tier = assign_confidence_tier(0.85, effective_primary=0.3)
        assert tier == "Provisional"
        # With effective_primary above tau_p, can be Supported
        tier = assign_confidence_tier(0.85, effective_primary=0.7)
        assert tier == "Supported"

    def test_enrich_claim_with_audit(self):
        claim = {"id": "CL:test-1", "label": "Claim", "properties": {"text": "Sample claim", "claimType": "empirical"}}
        out = enrich_claim_with_audit(claim, confidence_score=0.82, evidence_summary="Two papers support this.")
        assert out["properties"]["confidence_tier"] == "Supported"
        assert out["properties"]["p_error"] == pytest.approx(0.18, abs=0.001)
        assert out["properties"]["confidence"] == 0.82
        assert out["properties"]["evidence_summary"] == "Two papers support this."


class TestSecondaryToPrimary:
    """Secondary→primary: canonicalize primary identifiers from discovered sources."""

    def test_canonicalize_doi_from_property(self):
        source = {"id": "SRC:foo", "properties": {"title": "A Paper", "doi": "10.1234/example.2021"}}
        ids = canonicalize_primary_identifiers(source)
        assert ids == {"doi": "10.1234/example.2021"}

    def test_canonicalize_arxiv_from_id(self):
        source = {"id": "SRC:arxiv_2101.12345", "label": "Source", "properties": {"title": "Preprint"}}
        ids = canonicalize_primary_identifiers(source)
        assert "arxiv" in ids
        assert "2101.12345" in ids["arxiv"]

    def test_canonicalize_doi_from_url(self):
        source = {"id": "SRC:x", "properties": {"url": "https://doi.org/10.5678/something"}}
        ids = canonicalize_primary_identifiers(source)
        assert ids.get("doi") is not None
        assert "10.5678" in ids["doi"]

    def test_canonicalize_empty_when_no_ids(self):
        source = {"id": "SRC:x", "properties": {"title": "No IDs", "url": "https://example.com/page"}}
        ids = canonicalize_primary_identifiers(source)
        assert ids == {}

    def test_enrich_source_with_primary_identifiers(self):
        source = {"id": "SRC:s2_abc", "properties": {"title": "Paper", "doi": "10.1000/xyz"}}
        enrich_source_with_primary_identifiers(source)
        assert source["properties"]["identifiers"] == {"doi": "10.1000/xyz"}
