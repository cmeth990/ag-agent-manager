"""LangGraph supervisor definition with approval flow."""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.workers import (
    extractor_node,
    linker_node,
    writer_node,
    commit_node,
    handle_reject_node,
    query_node
)
from app.graph.source_gatherer import source_gatherer_node
from app.graph.content_fetcher import content_fetcher_node
from app.graph.domain_scout_worker import domain_scout_node
from app.graph.parallel_agents import parallel_agents_node
from app.graph.checkpoint import create_checkpointer


logger = logging.getLogger(__name__)


def route_intent(state: AgentState) -> str:
    """
    Route based on user intent and current state.
    
    Returns:
        Next node name
    """
    # If approval is required and no decision yet, wait for approval
    if state.get("approval_required") and not state.get("approval_decision"):
        return "wait_for_approval"
    
    # If approval decision exists, route to commit
    if state.get("approval_decision"):
        decision = state.get("approval_decision")
        if decision == "reject":
            return "handle_reject"
        elif decision == "approve":
            return "commit"
    
    # If there's an error, end
    if state.get("error"):
        return END
    
    # If final response exists and no approval needed, end
    if state.get("final_response") and not state.get("approval_required"):
        return END
    
    # Normal flow: extract -> link -> write
    intent = state.get("intent")
    if intent == "ingest" or state.get("user_input"):
        return "extract"
    
    return END


def detect_intent(state: AgentState) -> Dict[str, Any]:
    """
    Detect user intent from input.
    
    Simple keyword-based detection. Can be replaced with LLM classification.
    """
    user_input = state.get("user_input", "").lower().strip()
    
    if user_input.startswith("/ingest") or "ingest" in user_input:
        intent = "ingest"
    elif user_input.startswith("/query") or "query" in user_input:
        intent = "query"
    elif user_input.startswith("/gather") or "gather sources" in user_input or "find sources" in user_input:
        intent = "gather_sources"
    elif user_input.startswith("/fetch") or "fetch content" in user_input:
        intent = "fetch_content"
    elif user_input.startswith("/scout") or "scout domains" in user_input or "find new domains" in user_input:
        intent = "scout_domains"
    elif user_input.startswith("/test") or "test agents" in user_input or "parallel" in user_input:
        intent = "parallel_test"
    elif user_input.startswith("/help"):
        intent = "help"
    elif user_input.startswith("/status"):
        intent = "status"
    elif user_input.startswith("/cancel"):
        intent = "cancel"
    else:
        # Default to ingest for now
        intent = "ingest"
    
    return {"intent": intent}


def help_node(state: AgentState) -> Dict[str, Any]:
    """Handle /help command."""
    help_text = """🤖 Telegram KG Manager Bot

Commands:
/ingest <topic=...> - Ingest new knowledge
/query <question> - Query the knowledge graph
/gather sources for <domain> - Discover sources for a domain
/fetch content for <domain> - Fetch content from discovered sources
/scout domains - Discover new domains not in knowledge graph
/test agents - Run source gatherer and domain scout in parallel
/status - Check bot status
/cancel - Cancel current operation
/help - Show this help

Examples:
/ingest topic=photosynthesis
/gather sources for Algebra
/gather sources for Machine Learning
"""
    return {"final_response": help_text}


def status_node(state: AgentState) -> Dict[str, Any]:
    """Handle /status command."""
    status = "✅ Bot is running\n"
    if state.get("approval_required"):
        status += f"⏳ Waiting for approval (diff_id: {state.get('diff_id', 'unknown')})"
    else:
        status += "Ready for commands"
    return {"final_response": status}


def cancel_node(state: AgentState) -> Dict[str, Any]:
    """Handle /cancel command."""
    return {
        "proposed_diff": None,
        "approval_required": False,
        "final_response": "❌ Operation cancelled."
    }


def wait_for_approval_node(state: AgentState) -> Dict[str, Any]:
    """
    Node that waits for approval.
    
    In a real implementation with interrupts, this would pause the graph.
    For now, we return the state and let the Telegram layer handle the UI.
    """
    # The graph will stop here and return state
    # Telegram layer will show approval buttons
    return {}


def build_graph():
    """
    Build and compile the LangGraph supervisor graph.
    
    Returns:
        Compiled graph with checkpointer
    """
    # Create checkpointer
    checkpointer = create_checkpointer()
    
    # Build graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("detect_intent", detect_intent)
    workflow.add_node("help", help_node)
    workflow.add_node("status", status_node)
    workflow.add_node("cancel", cancel_node)
    workflow.add_node("extract", extractor_node)
    workflow.add_node("link", linker_node)
    workflow.add_node("write", writer_node)
    workflow.add_node("wait_for_approval", wait_for_approval_node)
    workflow.add_node("commit", commit_node)
    workflow.add_node("handle_reject", handle_reject_node)
    
    # Set entry point
    workflow.set_entry_point("detect_intent")
    
    # Add query node
    workflow.add_node("query", query_node)
    
    # Add source gatherer node
    workflow.add_node("gather_sources", source_gatherer_node)
    
    # Add content fetcher node
    workflow.add_node("fetch_content", content_fetcher_node)
    
    # Add domain scout node
    workflow.add_node("scout_domains", domain_scout_node)
    
    # Add parallel agents node
    workflow.add_node("parallel_test", parallel_agents_node)
    
    # Add conditional edges from detect_intent
    def route_after_intent(state: AgentState) -> str:
        intent = state.get("intent")
        if intent == "help":
            return "help"
        elif intent == "status":
            return "status"
        elif intent == "cancel":
            return "cancel"
        elif intent == "gather_sources":
            return "gather_sources"
        elif intent == "fetch_content":
            return "fetch_content"
        elif intent == "scout_domains":
            return "scout_domains"
        elif intent == "parallel_test":
            return "parallel_test"
        elif intent == "ingest":
            return "extract"
        elif intent == "query":
            return "query"
        else:
            return END
    
    workflow.add_conditional_edges("detect_intent", route_after_intent)
    
    # Linear flow: extract -> link -> write
    # Note: extract and link are async, but LangGraph handles this
    workflow.add_edge("extract", "link")
    workflow.add_edge("link", "write")
    
    # From write, check if approval needed
    workflow.add_conditional_edges("write", route_intent)
    
    # Approval flow
    workflow.add_conditional_edges("wait_for_approval", route_intent)
    workflow.add_edge("commit", END)
    workflow.add_edge("handle_reject", END)
    
    # Terminal nodes
    workflow.add_edge("help", END)
    workflow.add_edge("status", END)
    workflow.add_edge("cancel", END)
    workflow.add_edge("query", END)
    workflow.add_edge("gather_sources", END)
    workflow.add_edge("fetch_content", END)
    workflow.add_edge("scout_domains", END)
    workflow.add_edge("parallel_test", END)
    
    # Compile with checkpointer
    graph = workflow.compile(checkpointer=checkpointer)
    
    return graph


# Global graph instance (created on first import)
_graph = None


def get_graph():
    """Get or create the compiled graph."""
    global _graph
    if _graph is None:
        logger.info("Building graph from scratch...")
        _graph = build_graph()
        logger.info("Graph built successfully")
    return _graph


def reset_graph():
    """Reset the cached graph (for testing/debugging)."""
    global _graph
    _graph = None
    logger.info("Graph cache reset")


async def run_graph(
    input_state: Dict[str, Any],
    thread_id: str,
    config: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Run the graph with given input and thread_id.
    
    Args:
        input_state: Initial state dict
        thread_id: Thread ID for persistence (use chat_id)
        config: Optional additional config
    
    Returns:
        Final state dict
    """
    graph = get_graph()
    
    # Prepare config with thread_id
    run_config = {
        "configurable": {
            "thread_id": thread_id,
            **(config.get("configurable", {}) if config else {})
        }
    }
    
    # Invoke graph
    result = await graph.ainvoke(input_state, config=run_config)
    
    return result
