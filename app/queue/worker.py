"""
Background worker that processes durable queue tasks (graph_run, mission_continue).
Runs run_graph for graph_run tasks and sends Telegram response; runs expansion for mission_continue.
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
TASK_TYPE_MISSION_CONTINUE = "mission_continue"
POLL_INTERVAL_SECONDS = 2
HEARTBEAT_INTERVAL_SECONDS = 30


async def _process_mission_continue(task_record, queue) -> None:
    """Run one expansion cycle and notify chat; used while a key decision is pending."""
    task_id = task_record.task_id
    payload = task_record.payload or {}
    chat_id = payload.get("chat_id")
    if not chat_id:
        logger.error(f"Task {task_id} missing chat_id in payload")
        queue.fail(task_id, error="Missing chat_id in payload", retry=False)
        return
    from app.queue.mission_continue import run_mission_continue
    try:
        result = await run_mission_continue(str(chat_id))
        queue.complete(task_id, result=result)
        logger.info(f"Mission continue task {task_id} completed for chat {chat_id}")
    except Exception as e:
        logger.warning(f"Mission continue task {task_id} failed: {e}")
        queue.fail(task_id, error=str(e)[:200], retry=True)


async def _process_one_task(task_record) -> None:
    """Run one task: dispatch by task_type (graph_run vs mission_continue)."""
    from app.queue.durable_queue import get_queue

    queue = get_queue()
    task_type = getattr(task_record, "task_type", "graph_run")

    if task_type == TASK_TYPE_MISSION_CONTINUE:
        await _process_mission_continue(task_record, queue)
        return

    # graph_run
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

        # Send Telegram response (same logic as main.py webhook); prefix key decision when set
        if result.get("approval_required") and (result.get("diff_id") or result.get("proposed_changes")):
            diff_id = result.get("diff_id") or f"improve_{hash(result.get('user_input', '')) % 10000}"
            response_text = result.get("final_response", "Please approve or reject the proposed changes.")
            crucial_type = result.get("crucial_decision_type")
            if crucial_type:
                from app.mission import get_crucial_decision_label
                label = get_crucial_decision_label(crucial_type)
                response_text = f"🔑 **Key decision: {label}**\n\n{response_text}"
            keyboard = build_approval_keyboard(diff_id)
            await send_message(int(chat_id), response_text, reply_markup=keyboard)
            # Continue mission work in the meantime
            try:
                queue.enqueue(TASK_TYPE_MISSION_CONTINUE, {"chat_id": str(chat_id)})
            except Exception as enq_err:
                logger.warning("Could not enqueue mission_continue: %s", enq_err)
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
    task_type: Optional[str] = None,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    """
    Run the worker loop: dequeue tasks, process, complete/fail.
    If task_type is None, process any task type (graph_run, mission_continue).
    """
    from app.queue.durable_queue import get_queue

    queue = get_queue()
    logger.info("Worker started (task_type=%s, poll_interval=%ss)", task_type or "any", poll_interval)

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
            logger.error("Worker loop error: %s", e, exc_info=True)
            await asyncio.sleep(poll_interval)


def start_worker_background(
    task_type: Optional[str] = None,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> Optional[asyncio.Task]:
    """
    Start the worker as a background asyncio task.
    If task_type is None, worker processes both graph_run and mission_continue.
    Returns the task so it can be cancelled on shutdown.
    """
    task = asyncio.create_task(run_worker_loop(task_type=task_type, poll_interval=poll_interval))
    return task
