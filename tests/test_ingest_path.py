"""Integration-style tests for ingest path (extract → link → write) with mock state."""
import pytest
from app.graph.state import AgentState
from app.graph.workers import linker_node, writer_node
from app.kg.knowledge_base import generate_id


@pytest.fixture
def sample_extracted():
    """Minimal valid extracted output (as from extractor_node)."""
    c1 = generate_id("Concept")
    c2 = generate_id("Concept")
    return {
        "entities": [
            {"id": c1, "label": "Concept", "properties": {"name": "Photosynthesis", "domain": "biology"}},
            {"id": c2, "label": "Concept", "properties": {"name": "Chlorophyll", "domain": "biology"}},
        ],
        "relations": [
            {"from": c1, "to": c2, "type": "RELATED_TO", "properties": {}},
        ],
        "claims": [],
    }


@pytest.fixture
def state_with_extracted(sample_extracted):
    """AgentState with working_notes.extracted set."""
    return {
        "user_input": "topic=photosynthesis",
        "chat_id": "123",
        "intent": "ingest",
        "task_queue": [],
        "working_notes": {"extracted": sample_extracted},
        "proposed_diff": None,
        "diff_id": None,
        "approval_required": False,
        "approval_decision": None,
        "final_response": None,
        "error": None,
    }


@pytest.mark.asyncio
async def test_linker_node_produces_linked(state_with_extracted):
    """Linker consumes extracted and produces linked entities/relations/canonical_ids."""
    out = await linker_node(state_with_extracted)
    assert "working_notes" in out
    linked = out["working_notes"].get("linked")
    assert linked is not None
    assert "entities" in linked
    assert "relations" in linked
    assert "canonical_ids" in linked
    assert len(linked["entities"]) == 2
    assert len(linked["relations"]) == 1
    assert len(linked["canonical_ids"]) >= 1


@pytest.mark.asyncio
async def test_writer_node_produces_proposed_diff(state_with_extracted):
    """Writer consumes linked and produces proposed_diff."""
    link_out = await linker_node(state_with_extracted)
    state_with_linked = {**state_with_extracted, "working_notes": link_out["working_notes"]}
    
    out = writer_node(state_with_linked)
    assert "proposed_diff" in out
    assert out.get("approval_required") is True
    diff = out["proposed_diff"]
    assert diff is not None
    assert "nodes" in diff
    assert "edges" in diff
    assert "add" in diff["nodes"]
    assert len(diff["nodes"]["add"]) >= 2
    assert "add" in diff["edges"]
    assert out.get("diff_id") is not None
