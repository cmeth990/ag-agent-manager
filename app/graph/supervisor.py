"""LangGraph supervisor definition with approval flow."""
import asyncio
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.mission import get_mission_summary
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
from app.graph.improvement_agent import (
    improvement_agent_node,
    apply_improvements,
    reject_improvements,
    push_changes_node
)
from app.graph.expansion import expansion_node, begin_node
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
    
    # If approval decision exists, route appropriately
    if state.get("approval_decision"):
        decision = state.get("approval_decision")
        # Check if this is for improvements or regular diff
        if state.get("proposed_changes"):
            # Improvement approval
            if decision == "reject":
                return "reject_improvements"
            elif decision == "approve":
                return "apply_improvements"
        else:
            # Regular diff approval
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
    elif user_input.startswith("/push") or "push to github" in user_input or "push changes" in user_input:
        intent = "push_changes"
    elif user_input.startswith("/graph") or "graph progress" in user_input or "knowledge graph progress" in user_input or "show graph" in user_input:
        intent = "graph_progress"
    elif user_input.startswith("/expand") or "build the kg" in user_input or "build the knowledge graph" in user_input or "autonomous expand" in user_input or (user_input.strip() == "continue" or (user_input.strip().startswith("continue") and len(user_input.split()) <= 2)):
        intent = "autonomous_expand"
    elif any(phrase in user_input for phrase in (
        "begin", "start", "go", "get started", "let's go", "start building", "make the knowledge graph",
        "iterate", "run", "get to work", "do it", "go ahead", "yes go", "lets go", "begin building",
        "start the kg", "start the knowledge graph", "build it", "get going"
    )) or user_input.strip().lower() in ("begin", "start", "go", "run"):
        intent = "autonomous_begin"
    elif user_input.startswith("/improve") or (
        ("improve" in user_input or "make it better" in user_input or "fix the" in user_input or "enhance" in user_input or
         "optimize" in user_input or "refactor" in user_input or "update the" in user_input or "modify the" in user_input)
        and ("agent" in user_input or "code" in user_input or "source gatherer" in user_input or "fetcher" in user_input or
             "scout" in user_input or "extractor" in user_input or "bot" in user_input or "system" in user_input or
             "conversation" in user_input or "we're having" in user_input or "this chat" in user_input)
    ):
        intent = "improve"
    elif "expand the knowledge graph" in user_input or "expand the kg" in user_input or "add knowledge about" in user_input or "add knowledge on" in user_input:
        intent = "ingest"  # Will parse topic from message in extractor
    elif "improve" in user_input or "fix" in user_input or "add " in user_input:
        # Broad improvement keywords without clear code context -> improve (user can clarify)
        improvement_keywords = [
            "improve", "fix", "enhance", "optimize", "refactor",
            "better", "update", "modify", "change", "implement"
        ]
        if any(k in user_input for k in improvement_keywords):
            intent = "improve"
        else:
            intent = "ingest"
    else:
        # Default to ingest for now
        intent = "ingest"
    
    return {"intent": intent}


def help_node(state: AgentState) -> Dict[str, Any]:
    """Handle /help command."""
    mission = get_mission_summary()
    help_text = f"""🤖 Telegram KG Manager Bot

**Superintendent mission:** {mission}

🚀 **Just say Begin or Start** — I'll expand the knowledge graph, iterate, and improve. I'll come to you for key decisions (e.g. committing changes). Say **continue** or **expand** for more cycles.

**Natural triggers:** "begin", "start", "go", "get started", "let's go", "build the knowledge graph", "continue"

Commands:
/ingest <topic=...> - Ingest new knowledge
/query <question> - Query the knowledge graph
/gather sources for <domain> - Discover sources for a domain
/fetch content for <domain> - Fetch content from discovered sources
/scout domains - Discover new domains
/expand or "continue" - Another expansion cycle
/status - Check bot status
/cancel - Cancel current operation
/graph - Private link to KG progress (zoom by level)
/help - Show this help

💡 **Improvement & expand:** "/improve ..." or "Improve the source gatherer to ..." — I propose code changes; you Approve/Reject. "/ingest topic=X" or "Add knowledge about X" — I extract, link, write; you Approve/Reject to commit.

/push - Push committed changes to GitHub
"""
    return {"final_response": help_text}


async def graph_progress_node(state: AgentState) -> Dict[str, Any]:
    """
    Send a private link to the KG progress dashboard (zoom in/out by level).
    No per-category images; one link that opens a drill-down view.
    """
    import os
    from app.kg.progress import (
        get_progress_stats,
        get_progress_summary_text,
        create_progress_view_token,
    )

    chat_id = state.get("chat_id")
    if not chat_id:
        return {"final_response": "❌ No chat ID."}

    try:
        stats = get_progress_stats()
        summary = get_progress_summary_text(stats)
        token = create_progress_view_token(str(chat_id))
        base_url = (os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_URL") or "").rstrip("/")
        if not token:
            return {
                "final_response": f"📊 {summary}\n\n"
                "❌ Private dashboard link requires GRAPH_VIEW_SECRET or ADMIN_API_KEY to be set (Railway Variables)."
            }
        if not base_url:
            return {
                "final_response": f"📊 {summary}\n\n"
                "❌ Set PUBLIC_URL or RAILWAY_URL in Railway Variables to your app URL (e.g. https://your-app.up.railway.app)."
            }
        link = f"{base_url}/graph/progress?token={token}"
        return {
            "final_response": f"📊 {summary}\n\n"
            f"🔗 **Private dashboard** (zoom in/out by level, link valid ~1 hour):\n{link}\n\n"
            "Click to open in browser; expand rows to drill down (Upper Ontology → Categories → Domains)."
        }
    except Exception as e:
        logger.exception("Graph progress failed")
        return {"final_response": f"❌ Failed: {str(e)[:200]}"}


def status_node(state: AgentState) -> Dict[str, Any]:
    """
    Handle /status command.
    Uses telemetry (not chat memory) to summarize system state.
    """
    from app.telemetry.aggregator import get_system_state, summarize_state
    
    # Get comprehensive state from telemetry
    system_state = get_system_state()
    summary = summarize_state(system_state)
    
    # Add current task status if available
    if state.get("approval_required"):
        summary += f"\n\n⏳ **Current Task:** Waiting for approval (diff_id: {state.get('diff_id', 'unknown')})"
    
    return {"final_response": summary}


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
    Telegram layer will show Approve/Reject buttons; graph exits via end_wait so we don't loop.
    """
    return {}


def end_wait_node(state: AgentState) -> Dict[str, Any]:
    """No-op exit node when waiting for approval; single edge to END so graph stops (avoids recursion)."""
    return {}


def end_default_node(state: AgentState) -> Dict[str, Any]:
    """No-op exit when intent doesn't match any route; single edge to END (avoid returning END from conditional)."""
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
    
    # Add improvement agent nodes
    workflow.add_node("improve", improvement_agent_node)
    workflow.add_node("apply_improvements", apply_improvements)
    workflow.add_node("reject_improvements", reject_improvements)
    workflow.add_node("push_changes", push_changes_node)
    workflow.add_node("graph_progress", graph_progress_node)
    workflow.add_node("expansion", expansion_node)
    workflow.add_node("begin", begin_node)

    # Add conditional edges from detect_intent
    def route_after_intent(state: AgentState) -> str:
        # Re-invoke after Approve/Reject: go to wait_for_approval so route_after_wait routes to commit/handle_reject/etc.
        if state.get("approval_decision") and (state.get("proposed_diff") or state.get("proposed_changes")):
            return "wait_for_approval"
        intent = state.get("intent")
        if intent == "help":
            return "help"
        elif intent == "status":
            return "status"
        elif intent == "cancel":
            return "cancel"
        elif intent == "improve":
            return "improve"
        elif intent == "push_changes":
            return "push_changes"
        elif intent == "graph_progress":
            return "graph_progress"
        elif intent == "autonomous_expand":
            return "expansion"
        elif intent == "autonomous_begin":
            return "begin"
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
            return "end_default"  # sink node -> END (never return END from conditional)
    
    workflow.add_node("end_default", end_default_node)
    workflow.add_conditional_edges("detect_intent", route_after_intent)
    workflow.add_edge("end_default", END)
    
    # Linear flow: extract -> link -> write
    # Note: extract and link are async, but LangGraph handles this
    workflow.add_edge("extract", "link")
    workflow.add_edge("link", "write")
    
    # From write, check if approval needed
    workflow.add_conditional_edges("write", route_intent)

    # Improvement agent approval flow
    def route_improvement(state: AgentState) -> str:
        if state.get("approval_required") and not state.get("approval_decision"):
            return "wait_for_approval"
        elif state.get("approval_decision") == "approve":
            return "apply_improvements"
        elif state.get("approval_decision") == "reject":
            return "reject_improvements"
        else:
            return END

    workflow.add_conditional_edges("improve", route_improvement)

    # From wait_for_approval: if still no decision, go to end_wait -> END (stops graph; caller shows UI and re-invokes on button press)
    def route_after_wait(state: AgentState) -> str:
        if state.get("approval_required") and not state.get("approval_decision"):
            return "end_wait"  # dedicated exit node so graph always stops (no END-from-conditional quirks)
        return route_intent(state)

    workflow.add_node("end_wait", end_wait_node)
    workflow.add_conditional_edges("wait_for_approval", route_after_wait)
    workflow.add_edge("end_wait", END)
    workflow.add_edge("commit", END)
    workflow.add_edge("handle_reject", END)
    workflow.add_edge("apply_improvements", END)
    workflow.add_edge("reject_improvements", END)
    workflow.add_edge("push_changes", END)
    
    # Terminal nodes
    workflow.add_edge("help", END)
    workflow.add_edge("status", END)
    workflow.add_edge("cancel", END)
    workflow.add_edge("query", END)
    workflow.add_edge("gather_sources", END)
    workflow.add_edge("graph_progress", END)
    workflow.add_edge("expansion", END)
    workflow.add_edge("begin", END)
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
    # Recursion limit must be top-level in config; keep low so any loop fails fast (default 25)
    recursion_limit = 25
    if config and "recursion_limit" in config:
        recursion_limit = int(config["recursion_limit"])
    run_config = {
        "configurable": {
            "thread_id": thread_id,
            **(config.get("configurable", {}) if config else {})
        },
        "recursion_limit": recursion_limit,
    }
    logger.debug("Invoking graph with recursion_limit=%s", recursion_limit)
    result = await graph.ainvoke(input_state, config=run_config)
    
    return result
