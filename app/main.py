"""FastAPI server with Telegram webhook endpoint."""
import sys
# Flush stderr immediately so Railway shows logs (Python buffers otherwise)
print("[startup] main.py loading", file=sys.stderr, flush=True)
import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.auth import require_admin_key
import uvicorn
from app.telegram import (
    send_message,
    answer_callback_query,
    build_approval_keyboard
)
from app.graph.supervisor import run_graph
from app.graph.state import AgentState
from app.task_state import set_task_status, TaskStatus, TaskStateRegistry

# Load environment variables from .env file
load_dotenv()


# Configure logging to stderr so Railway captures it (use PYTHONUNBUFFERED=1 in Procfile)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger(__name__)
logger.info("App module loaded")

# Durable queue: when True and DATABASE_URL set, webhook enqueues and worker processes
USE_DURABLE_QUEUE = os.getenv("USE_DURABLE_QUEUE", "false").lower() == "true"
_worker_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background worker when durable queue is enabled."""
    global _worker_task
    if USE_DURABLE_QUEUE and os.getenv("DATABASE_URL"):
        from app.queue.worker import start_worker_background, TASK_TYPE_GRAPH_RUN
        _worker_task = start_worker_background(task_type=TASK_TYPE_GRAPH_RUN)
        logger.info("Durable queue worker started")
    yield
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Durable queue worker stopped")


app = FastAPI(title="Telegram KG Manager Bot", lifespan=lifespan)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "telegram-kg-manager"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/telemetry/tasks", dependencies=[Depends(require_admin_key)])
async def telemetry_tasks(limit: int = 20):
    """
    Telemetry: recent task states (for supervisor/state summarization).
    Does not rely on chat memory.
    """
    tasks = TaskStateRegistry.list_recent(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/telemetry/state", dependencies=[Depends(require_admin_key)])
async def telemetry_state():
    """
    Comprehensive system state from telemetry.
    Supervisor can query this instead of relying on chat memory.
    """
    from app.telemetry.aggregator import get_system_state
    return get_system_state()


@app.get("/telemetry/summary", dependencies=[Depends(require_admin_key)])
async def telemetry_summary():
    """
    Human-readable summary of system state from telemetry.
    """
    from app.telemetry.aggregator import summarize_state
    return {"summary": summarize_state()}


@app.get("/kg/versions", dependencies=[Depends(require_admin_key)])
async def list_kg_versions(limit: int = 20):
    """
    List recent KG versions (changelog).
    """
    from app.kg.rollback import list_versions
    return await list_versions(limit=limit)


@app.get("/kg/versions/{version}", dependencies=[Depends(require_admin_key)])
async def get_kg_version(version: int):
    """
    Get information about a specific KG version.
    """
    from app.kg.rollback import get_version_info
    info = await get_version_info(version)
    if not info:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    return info


@app.post("/kg/rollback/{target_version}", dependencies=[Depends(require_admin_key)])
async def rollback_kg(target_version: int):
    """
    Rollback KG to a specific version.
    
    Args:
        target_version: Version number to rollback to (0 = initial state)
    """
    from app.kg.rollback import rollback_to_version
    result = await rollback_to_version(target_version)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rollback failed"))
    return result


@app.get("/queue/dead-letter", dependencies=[Depends(require_admin_key)])
async def list_dead_letter_queue(limit: int = 50):
    """List tasks in dead-letter queue (for triage)."""
    from app.queue.triage import list_dead_letter_tasks
    tasks = await list_dead_letter_tasks(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/queue/triage/{task_id}", dependencies=[Depends(require_admin_key)])
async def triage_task(task_id: str, action: str = "retry", updated_payload: Optional[Dict[str, Any]] = None):
    """
    Triage a dead-letter queue task.
    
    Actions: "retry", "update_payload", "skip"
    """
    from app.queue.triage import triage_dead_letter_task
    result = await triage_dead_letter_task(task_id, action, updated_payload=updated_payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Triage failed"))
    return result


@app.get("/queue/stuck", dependencies=[Depends(require_admin_key)])
async def list_stuck_tasks(threshold_minutes: int = 30):
    """List stuck tasks (no heartbeat recently)."""
    from app.queue.heartbeat import monitor_stuck_tasks
    result = await monitor_stuck_tasks(stuck_threshold_minutes=threshold_minutes, auto_retry=False)
    return result


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Handle Telegram webhook updates.
    
    Supports:
    - Text messages (commands)
    - Callback queries (button presses)
    """
    try:
        update = await request.json()
        logger.info(f"Received update: {update.get('update_id')}")
        logger.info(f"Update keys: {list(update.keys())}")
        logger.info(f"Full update: {update}")
        
        # Handle message
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "").strip()
            
            if not text:
                return JSONResponse({"ok": True})
            
            logger.info(f"Message from {chat_id}: {text[:100]}")
            
            # Create initial state
            initial_state: AgentState = {
                "user_input": text,
                "chat_id": str(chat_id),
                "intent": None,
                "task_queue": [],
                "working_notes": {},
                "proposed_diff": None,
                "diff_id": None,
                "approval_required": False,
                "approval_decision": None,
                "final_response": None,
                "error": None
            }
            
            # Durable queue: enqueue and return; worker will run graph and send response
            if USE_DURABLE_QUEUE and os.getenv("DATABASE_URL"):
                try:
                    from app.queue.durable_queue import get_queue
                    from app.queue.worker import TASK_TYPE_GRAPH_RUN
                    queue = get_queue()
                    payload = dict(initial_state)
                    task_id = queue.enqueue(
                        TASK_TYPE_GRAPH_RUN,
                        payload,
                        agent="supervisor",
                        max_retries=3,
                    )
                    logger.info(f"Enqueued task {task_id} for chat_id {chat_id}")
                    return JSONResponse({"ok": True, "queued": True, "task_id": task_id})
                except Exception as e:
                    logger.error(f"Enqueue failed, falling back to inline: {e}")
            
            # Inline: run graph and send response
            thread_id = str(chat_id)
            set_task_status(thread_id, TaskStatus.IN_PROGRESS, agent="supervisor")
            try:
                result = await run_graph(initial_state, thread_id)
                set_task_status(thread_id, TaskStatus.COMPLETED, agent="supervisor")
                logger.info(f"Graph execution completed for {chat_id}, intent: {result.get('intent')}")
            except Exception as e:
                set_task_status(thread_id, TaskStatus.FAILED, error=str(e)[:500])
                logger.error(f"Error running graph: {e}", exc_info=True)
                # Clean error message - remove newlines and special chars
                error_msg = str(e).replace('\n', ' ').replace('\r', ' ')[:200]
                try:
                    await send_message(chat_id, f"❌ Error processing command: {error_msg}")
                except Exception as send_err:
                    logger.error(f"Failed to send error message: {send_err}")
                return JSONResponse({"ok": True})
            
            # Check if approval is required (for both diff and improvements)
            if result.get("approval_required") and (result.get("diff_id") or result.get("proposed_changes")):
                # Send approval message with buttons
                diff_id = result.get("diff_id") or f"improve_{hash(result.get('user_input', '')) % 10000}"
                response_text = result.get("final_response", "Please approve or reject the proposed changes.")
                
                keyboard = build_approval_keyboard(diff_id)
                try:
                    await send_message(chat_id, response_text, reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Error sending approval message: {e}")
            elif result.get("final_response"):
                # Send regular response
                try:
                    await send_message(chat_id, result["final_response"])
                    logger.info(f"Sent response to {chat_id}")
                except Exception as e:
                    logger.error(f"Error sending message to {chat_id}: {e}", exc_info=True)
            elif result.get("error"):
                # Send error message
                try:
                    await send_message(chat_id, f"❌ Error: {result['error']}")
                except Exception as e:
                    logger.error(f"Error sending error message: {e}")
            else:
                # Fallback
                try:
                    await send_message(chat_id, "Processing complete.")
                except Exception as e:
                    logger.error(f"Error sending fallback message: {e}")
            
            return JSONResponse({"ok": True})
        
        # Handle callback query (button press)
        if "callback_query" in update:
            callback_query = update["callback_query"]
            callback_id = callback_query["id"]
            chat_id = callback_query["message"]["chat"]["id"]
            data = callback_query.get("data", "")
            
            logger.info(f"Callback from {chat_id}: {data}")
            
            # Parse callback data: "approve:diff_id" or "reject:diff_id"
            if ":" in data:
                action, diff_id = data.split(":", 1)
            else:
                action = data
                diff_id = None
            
            # Answer callback immediately
            await answer_callback_query(callback_id, text="Processing...")
            
            thread_id = str(chat_id)
            
            # Load current state from checkpoint first
            from app.graph.supervisor import get_graph
            graph = get_graph()
            run_config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            
            # Get current checkpoint state to preserve proposed_diff
            try:
                checkpoint_state = await graph.aget_state(run_config)
                current_state = checkpoint_state.values if checkpoint_state else {}
            except Exception as e:
                logger.warning(f"Could not load checkpoint state: {e}, using empty state")
                current_state = {}
            
            # Create state update with approval decision
            # LangGraph will merge this with the checkpoint state automatically
            state_update: AgentState = {
                "chat_id": str(chat_id),  # Required field
                "approval_decision": action,  # This is what we're updating
                "task_queue": [],  # Required field
                "working_notes": {},  # Required field
            }
            
            # Preserve critical fields from checkpoint if available
            if current_state:
                if "proposed_diff" in current_state:
                    state_update["proposed_diff"] = current_state["proposed_diff"]
                if "proposed_changes" in current_state:
                    state_update["proposed_changes"] = current_state["proposed_changes"]
                if "improvement_plan" in current_state:
                    state_update["improvement_plan"] = current_state["improvement_plan"]
                if "diff_id" in current_state:
                    state_update["diff_id"] = current_state.get("diff_id") or diff_id
                if "user_input" in current_state:
                    state_update["user_input"] = current_state["user_input"]
                if "intent" in current_state:
                    state_update["intent"] = current_state["intent"]
            
            # Run graph - it will merge our update with checkpoint state
            result = await run_graph(state_update, thread_id)
            
            # Send result
            if result.get("final_response"):
                await send_message(chat_id, result["final_response"])
            elif result.get("error"):
                await send_message(chat_id, f"❌ Error: {result['error']}")
            else:
                await send_message(chat_id, "Processing complete.")
            
            return JSONResponse({"ok": True})
        
        # Unknown update type
        logger.warning(f"Unknown update type: {update.keys()}")
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )
