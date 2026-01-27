"""LangGraph state schema definition."""
from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict):
    """
    State object passed through LangGraph nodes.
    
    Fields:
        user_input: Original user command/message
        chat_id: Telegram chat ID (used as thread_id)
        intent: Detected intent (e.g., "ingest", "query", "update")
        task_queue: List of tasks to process
        working_notes: Intermediate processing notes
        proposed_diff: KG mutation plan (dict with nodes/edges to add/update/delete)
        diff_id: Unique identifier for this diff (for approval tracking)
        approval_required: Whether human approval is needed
        approval_decision: "approve" or "reject" or None
        final_response: Final message to send to user
        error: Error message if processing failed
    """
    user_input: Optional[str]
    chat_id: str
    intent: Optional[str]
    task_queue: List[Dict[str, Any]]
    working_notes: Dict[str, Any]
    proposed_diff: Optional[Dict[str, Any]]
    diff_id: Optional[str]
    approval_required: bool
    approval_decision: Optional[str]
    final_response: Optional[str]
    error: Optional[str]
