"""Unit tests for validation schemas, allowlists, and thresholds."""
import pytest
from app.validation.schemas import (
    INTENT_ALLOWLIST,
    APPROVAL_DECISION_ALLOWLIST,
    STATE_UPDATE_ALLOWLIST,
    Thresholds,
    get_node_type_allowlist,
    get_edge_type_allowlist,
)


class TestAllowlists:
    """Tests for allowlists."""

    def test_intent_allowlist_contains_ingest_query(self):
        assert "ingest" in INTENT_ALLOWLIST
        assert "query" in INTENT_ALLOWLIST
        assert "gather_sources" in INTENT_ALLOWLIST

    def test_approval_decision_allowlist(self):
        assert "approve" in APPROVAL_DECISION_ALLOWLIST
        assert "reject" in APPROVAL_DECISION_ALLOWLIST
        assert "pending" not in APPROVAL_DECISION_ALLOWLIST

    def test_state_update_allowlist_contains_expected_keys(self):
        assert "final_response" in STATE_UPDATE_ALLOWLIST
        assert "proposed_diff" in STATE_UPDATE_ALLOWLIST
        assert "error" in STATE_UPDATE_ALLOWLIST
        assert "discovered_sources" in STATE_UPDATE_ALLOWLIST

    def test_node_type_allowlist_from_kg(self):
        allowlist = get_node_type_allowlist()
        assert "Concept" in allowlist
        assert "Claim" in allowlist
        assert "Evidence" in allowlist
        assert "Source" in allowlist

    def test_edge_type_allowlist_from_kg(self):
        allowlist = get_edge_type_allowlist()
        assert "DEFINES" in allowlist
        assert "SUPPORTS" in allowlist
        assert "RELATED_TO" in allowlist


class TestThresholds:
    """Tests for Thresholds constants."""

    def test_extractor_thresholds_positive(self):
        assert Thresholds.MAX_ENTITIES_PER_EXTRACTION > 0
        assert Thresholds.MAX_RELATIONS_PER_EXTRACTION > 0
        assert Thresholds.MAX_CLAIMS_PER_EXTRACTION > 0
        assert Thresholds.MAX_PROPERTY_VALUE_LENGTH > 0

    def test_writer_thresholds_positive(self):
        assert Thresholds.MAX_NODES_ADD > 0
        assert Thresholds.MAX_EDGES_ADD > 0

    def test_content_fetcher_thresholds(self):
        assert Thresholds.MAX_DOMAINS_PER_REQUEST > 0
        assert Thresholds.MAX_SOURCES_PER_DOMAIN > 0
