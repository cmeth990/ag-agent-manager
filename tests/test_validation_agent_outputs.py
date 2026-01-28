"""Unit tests for agent output validators."""
import os
import pytest
from app.validation.agent_outputs import (
    ValidationError,
    validate_extractor_output,
    validate_source_gatherer_output,
    validate_content_fetcher_parsed,
    validate_linker_output,
    validate_commit_output,
    validate_query_output,
    validate_writer_output,
    validate_agent_state_update,
)


class TestValidateExtractorOutput:
    """Tests for validate_extractor_output."""

    def test_valid_entities_relations(self):
        out = validate_extractor_output({
            "entities": [
                {"id": "C:abc", "label": "Concept", "properties": {"name": "Foo", "domain": "math"}},
            ],
            "relations": [
                {"from": "C:abc", "to": "C:def", "type": "RELATED_TO", "properties": {}},
            ],
            "claims": [],
        })
        assert len(out["entities"]) == 1
        assert out["entities"][0]["label"] == "Concept"
        assert len(out["relations"]) == 1
        assert out["relations"][0]["type"] == "RELATED_TO"

    def test_not_dict_raises(self):
        with pytest.raises(ValidationError, match="must be dict"):
            validate_extractor_output([])

    def test_entities_not_list_raises(self):
        with pytest.raises(ValidationError, match="entities must be list"):
            validate_extractor_output({"entities": "x", "relations": [], "claims": []})

    def test_invalid_label_raises(self):
        with pytest.raises(ValidationError, match="not in allowlist"):
            validate_extractor_output({
                "entities": [{"id": "X:bad", "label": "InvalidLabel", "properties": {"name": "x"}}],
                "relations": [],
                "claims": [],
            })

    def test_invalid_edge_type_raises(self):
        with pytest.raises(ValidationError, match="not in allowlist"):
            validate_extractor_output({
                "entities": [{"id": "C:abc", "label": "Concept", "properties": {"name": "x"}}],
                "relations": [{"from": "C:abc", "to": "C:def", "type": "INVALID_EDGE", "properties": {}}],
                "claims": [],
            })

    def test_provenance_filter_when_required(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_CLAIM_PROVENANCE", "true")
        out = validate_extractor_output({
            "entities": [
                {"id": "C:abc", "label": "Concept", "properties": {"name": "Foo"}},
                {"id": "CL:claim1", "label": "Claim", "properties": {"text": "A claim", "claimType": "definition"}},
            ],
            "relations": [],
            "claims": [],
        })
        # Claim without sourceId/evidenceIds should be filtered out
        assert len(out["entities"]) == 1
        assert out["entities"][0]["label"] == "Concept"
        monkeypatch.delenv("REQUIRE_CLAIM_PROVENANCE", raising=False)


class TestValidateSourceGathererOutput:
    """Tests for validate_source_gatherer_output."""

    def test_valid_output(self):
        out = validate_source_gatherer_output({
            "discovered_sources": {
                "domains": ["Algebra"],
                "all_sources": [
                    {"id": "s1", "properties": {"title": "Source 1", "url": "https://example.com"}},
                ],
            },
        })
        assert out["discovered_sources"]["domains"] == ["Algebra"]
        assert len(out["discovered_sources"]["all_sources"]) == 1

    def test_source_without_title_or_name_raises(self):
        with pytest.raises(ValidationError, match="title or properties.name"):
            validate_source_gatherer_output({
                "discovered_sources": {
                    "domains": ["A"],
                    "all_sources": [{"id": "s1", "properties": {}}],
                },
            })


class TestValidateContentFetcherParsed:
    """Tests for validate_content_fetcher_parsed."""

    def test_valid_parsed(self):
        out = validate_content_fetcher_parsed({
            "domains": ["Algebra", "Geometry"],
            "max_sources": 15,
            "min_priority": 0.5,
        })
        assert out["domains"] == ["Algebra", "Geometry"]
        assert out["max_sources"] == 15
        assert out["min_priority"] == 0.5

    def test_clamps_max_sources(self):
        out = validate_content_fetcher_parsed({"domains": [], "max_sources": 999, "min_priority": 0})
        assert out["max_sources"] <= 50

    def test_clamps_min_priority(self):
        out = validate_content_fetcher_parsed({"domains": [], "max_sources": 10, "min_priority": 1.5})
        assert out["min_priority"] == 1.0


class TestValidateLinkerOutput:
    """Tests for validate_linker_output."""

    def test_valid_output(self):
        out = validate_linker_output({
            "entities": [{"id": "C:1", "label": "Concept", "properties": {}}],
            "relations": [],
            "canonical_ids": {"C:1": "C:1"},
        })
        assert len(out["entities"]) == 1
        assert out["canonical_ids"] == {"C:1": "C:1"}


class TestValidateCommitOutput:
    """Tests for validate_commit_output."""

    def test_valid_output(self):
        out = validate_commit_output({
            "proposed_diff": None,
            "approval_required": False,
            "final_response": "Done",
        })
        assert out["final_response"] == "Done"

    def test_unknown_key_raises(self):
        with pytest.raises(ValidationError, match="not in state allowlist"):
            validate_commit_output({"unknown_key": 1})

    def test_invalid_approval_decision_raises(self):
        with pytest.raises(ValidationError, match="approval_decision"):
            validate_commit_output({"approval_decision": "invalid"})


class TestValidateQueryOutput:
    """Tests for validate_query_output."""

    def test_valid_output(self):
        out = validate_query_output({"final_response": "Results here"})
        assert out["final_response"] == "Results here"


class TestValidateWriterOutput:
    """Tests for validate_writer_output."""

    def test_valid_output(self):
        out = validate_writer_output({
            "proposed_diff": {"nodes": {"add": [{"id": "C:1", "label": "Concept", "properties": {}}], "update": [], "delete": []}, "edges": {"add": [], "update": [], "delete": []}},
            "diff_id": "d1",
            "approval_required": True,
            "final_response": "Review",
        })
        assert out["diff_id"] == "d1"


class TestValidateAgentStateUpdate:
    """Tests for validate_agent_state_update."""

    def test_allowed_keys_passed(self):
        out = validate_agent_state_update({
            "final_response": "Hi",
            "chat_id": "123",
            "approval_required": True,
        })
        assert out["final_response"] == "Hi"
        assert out["chat_id"] == "123"
        assert out["approval_required"] is True

    def test_unknown_key_warning_logged(self):
        out = validate_agent_state_update({"final_response": "Hi", "unknown_key": 1})
        assert "unknown_key" not in out
        assert out["final_response"] == "Hi"
