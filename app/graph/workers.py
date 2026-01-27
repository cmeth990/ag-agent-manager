"""Worker nodes for LangGraph processing pipeline."""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from app.kg.diff import create_diff_id, create_empty_diff, format_diff_summary


logger = logging.getLogger(__name__)


def extractor_node(state: AgentState) -> Dict[str, Any]:
    """
    Extract entities, relations, and claims from user input.
    
    Input: user_input
    Output: Extracted entities/relations in structured format
    
    This is a stub that creates placeholder extraction results.
    Replace with actual NLP/LLM extraction logic.
    """
    user_input = state.get("user_input", "")
    logger.info(f"Extracting from input: {user_input[:100]}...")
    
    # Stub: Create placeholder extraction
    # TODO: Replace with actual extraction (e.g., using LLM, NER, etc.)
    extracted = {
        "entities": [
            {"id": "entity_1", "label": "Topic", "properties": {"name": user_input.split("=")[-1].strip() if "=" in user_input else user_input}}
        ],
        "relations": [],
        "claims": []
    }
    
    return {
        "working_notes": {
            **state.get("working_notes", {}),
            "extracted": extracted
        }
    }


def linker_node(state: AgentState) -> Dict[str, Any]:
    """
    Deduplicate and link entities to canonical IDs.
    
    Input: working_notes.extracted
    Output: Linked entities with canonical IDs
    
    This is a stub that passes through entities.
    Replace with actual entity linking/deduplication logic.
    """
    working_notes = state.get("working_notes", {})
    extracted = working_notes.get("extracted", {})
    logger.info(f"Linking {len(extracted.get('entities', []))} entities")
    
    # Stub: Pass through (no actual linking)
    # TODO: Replace with actual entity linking (fuzzy matching, KG lookup, etc.)
    linked = {
        "entities": extracted.get("entities", []),
        "relations": extracted.get("relations", []),
        "canonical_ids": {}  # Would map entity IDs to canonical IDs
    }
    
    return {
        "working_notes": {
            **working_notes,
            "linked": linked
        }
    }


def writer_node(state: AgentState) -> Dict[str, Any]:
    """
    Produce proposed_diff from linked entities.
    
    Input: working_notes.linked
    Output: proposed_diff, approval_required=True
    
    This creates a diff structure but does NOT commit it.
    """
    working_notes = state.get("working_notes", {})
    linked = working_notes.get("linked", {})
    logger.info("Generating proposed diff")
    
    # Create diff structure
    diff = create_empty_diff()
    diff_id = create_diff_id()
    
    # Convert linked entities to diff format
    # This is a stub - actual implementation would convert entities to KG format
    entities = linked.get("entities", [])
    for entity in entities:
        diff["nodes"]["add"].append({
            "id": entity.get("id", "unknown"),
            "label": entity.get("label", "Entity"),
            "properties": entity.get("properties", {})
        })
    
    relations = linked.get("relations", [])
    for rel in relations:
        diff["edges"]["add"].append({
            "from": rel.get("from"),
            "to": rel.get("to"),
            "type": rel.get("type", "RELATED_TO"),
            "properties": rel.get("properties", {})
        })
    
    diff["metadata"]["source"] = state.get("user_input")
    diff["metadata"]["reason"] = f"User requested: {state.get('intent', 'unknown')}"
    
    logger.info(f"Generated diff {diff_id}: {format_diff_summary(diff)}")
    
    return {
        "proposed_diff": diff,
        "diff_id": diff_id,
        "approval_required": True,
        "final_response": f"📝 Proposed KG changes:\n\n{format_diff_summary(diff)}\n\nPlease review and approve or reject."
    }


async def commit_node(state: AgentState) -> Dict[str, Any]:
    """
    Commit diff to KG if approved, or handle rejection.
    
    Input: proposed_diff, approval_decision
    Output: final_response with commit results
    """
    approval_decision = state.get("approval_decision")
    proposed_diff = state.get("proposed_diff")
    
    if approval_decision == "reject":
        logger.info("Diff rejected by user")
        return {
            "proposed_diff": None,
            "approval_required": False,
            "final_response": "❌ Changes rejected. Please provide clarification or a new command."
        }
    
    if approval_decision != "approve":
        logger.warning(f"Unexpected approval_decision: {approval_decision}")
        return {
            "error": f"Invalid approval decision: {approval_decision}"
        }
    
    if not proposed_diff:
        return {
            "error": "No proposed diff to commit"
        }
    
    # Import here to avoid circular dependency
    from app.kg.client import apply_diff
    
    logger.info("Committing diff to KG")
    result = await apply_diff(proposed_diff)
    
    if result.get("success"):
        summary = format_diff_summary(proposed_diff)
        response = f"✅ Committed to KG:\n\n{summary}\n\n"
        response += f"Nodes: +{result['nodes']['added']} ~{result['nodes']['updated']} -{result['nodes']['deleted']}\n"
        response += f"Edges: +{result['edges']['added']} ~{result['edges']['updated']} -{result['edges']['deleted']}"
        return {
            "proposed_diff": None,
            "approval_required": False,
            "final_response": response
        }
    else:
        return {
            "error": "Failed to commit diff",
            "final_response": "❌ Error committing changes. Please try again."
        }


def handle_reject_node(state: AgentState) -> Dict[str, Any]:
    """Handle rejection - clear diff and request clarification."""
    logger.info("Handling rejection")
    return {
        "proposed_diff": None,
        "approval_required": False,
        "final_response": "❌ Changes rejected. What would you like to do instead?"
    }
