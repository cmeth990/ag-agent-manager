"""
Background worker that processes durable queue tasks (graph_run).
Runs run_graph for each dequeued task and sends Telegram response.
"""
import asyncio
import logging
from typing import Optional

from app.graph.supervisor import run_graph
from app.graph.state import AgentState
from app.task_state import set_task_status, TaskStatus
from app.telegram import send_message, build_approval_keyboard

logger = logging.getLogger(__name__)

TASK_TYPE_GRAPH_RUN = "graph_run"
POLL_INTERVAL_SECONDS = 2
HEARTBEAT_INTERVAL_SECONDS = 30


async def _process_one_task(task_record) -> None:
    """Run graph for one task, send Telegram response, complete or fail the task."""
    from app.queue.durable_queue import get_queue
    
    queue = get_queue()
    task_id = task_record.task_id
    payload = task_record.payload or {}
    chat_id = payload.get("chat_id")
    
    if not chat_id:
        logger.error(f"Task {task_id} missing chat_id in payload")
        queue.fail(task_id, error="Missing chat_id in payload", retry=False)
        return
    
    thread_id = str(chat_id)
    initial_state: AgentState = {
        "user_input": payload.get("user_input", ""),
        "chat_id": str(chat_id),
        "intent": payload.get("intent"),
        "task_queue": payload.get("task_queue", []),
        "working_notes": payload.get("working_notes", {}),
        "proposed_diff": payload.get("proposed_diff"),
        "diff_id": payload.get("diff_id"),
        "approval_required": payload.get("approval_required", False),
        "approval_decision": payload.get("approval_decision"),
        "final_response": payload.get("final_response"),
        "error": payload.get("error"),
    }
    
    set_task_status(thread_id, TaskStatus.IN_PROGRESS, agent="supervisor")
    
    try:
        result = await run_graph(initial_state, thread_id)
        set_task_status(thread_id, TaskStatus.COMPLETED, agent="supervisor")
        
        # Send Telegram response (same logic as main.py webhook)
        if result.get("approval_required") and (result.get("diff_id") or result.get("proposed_changes")):
            diff_id = result.get("diff_id") or f"improve_{hash(result.get('user_input', '')) % 10000}"
            response_text = result.get("final_response", "Please approve or reject the proposed changes.")
            keyboard = build_approval_keyboard(diff_id)
            await send_message(int(chat_id), response_text, reply_markup=keyboard)
        elif result.get("final_response"):
            await send_message(int(chat_id), result["final_response"])
        elif result.get("error"):
            await send_message(int(chat_id), f"❌ Error: {result['error']}")
        else:
            await send_message(int(chat_id), "Processing complete.")
        
        queue.complete(task_id, result={"final_response": result.get("final_response"), "error": result.get("error")})
        logger.info(f"Task {task_id} completed and response sent to {chat_id}")
        
    except Exception as e:
        set_task_status(thread_id, TaskStatus.FAILED, error=str(e)[:500])
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        error_msg = str(e).replace("\n", " ").replace("\r", " ")[:200]
        try:
            await send_message(int(chat_id), f"❌ Error processing command: {error_msg}")
        except Exception as send_err:
            logger.error(f"Failed to send error message: {send_err}")
        queue.fail(task_id, error=error_msg, retry=True)


async def run_worker_loop(
    task_type: str = TASK_TYPE_GRAPH_RUN,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    """
    Run the worker loop: dequeue tasks, process, complete/fail.
    Call this from app startup (background task).
    """
    from app.queue.durable_queue import get_queue
    
    queue = get_queue()
    logger.info(f"Worker started (task_type={task_type}, poll_interval={poll_interval}s)")
    
    while True:
        try:
            tasks = queue.dequeue(task_type=task_type, limit=1)
            if tasks:
                for task in tasks:
                    await _process_one_task(task)
            else:
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(poll_interval)


def start_worker_background(
    task_type: str = TASK_TYPE_GRAPH_RUN,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> Optional[asyncio.Task]:
    """
    Start the worker as a background asyncio task.
    Returns the task so it can be cancelled on shutdown.
    """
    task = asyncio.create_task(run_worker_loop(task_type=task_type, poll_interval=poll_interval))
    return task
