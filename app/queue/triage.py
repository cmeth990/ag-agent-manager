"""
Dead-letter queue triage workflows.
Enables manual review and retry of failed tasks.
"""
import logging
from typing import Dict, Any, List, Optional
from app.queue.durable_queue import get_queue, TaskStatus

logger = logging.getLogger(__name__)


async def triage_dead_letter_task(
    task_id: str,
    action: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Triage a task from dead-letter queue.
    
    Actions:
    - "retry": Retry the task (resets to PENDING)
    - "update_payload": Update payload and retry
    - "skip": Mark as skipped (no retry)
    - "manual_fix": Mark for manual intervention
    
    Args:
        task_id: Task ID from dead-letter queue
        action: Triage action
        **kwargs: Additional params (e.g., updated_payload for "update_payload")
    
    Returns:
        Result dict
    """
    queue = get_queue()
    dlq_tasks = queue.get_dead_letter_tasks(limit=1000)
    
    task = next((t for t in dlq_tasks if t.task_id == task_id), None)
    if not task:
        return {"success": False, "error": f"Task {task_id} not found in dead-letter queue"}
    
    if action == "retry":
        # Reset to PENDING for retry
        try:
            import psycopg
            import os
            conn_string = os.getenv("DATABASE_URL")
            with psycopg.connect(conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE task_queue
                        SET status = %s, retry_count = 0, error = NULL, started_at = NULL, heartbeat_at = NULL
                        WHERE task_id = %s
                    """, (TaskStatus.PENDING.value, task_id))
                    conn.commit()
            logger.info(f"Task {task_id} moved from DLQ to PENDING for retry")
            return {"success": True, "action": "retry", "task_id": task_id}
        except Exception as e:
            logger.error(f"Failed to retry task {task_id}: {e}")
            return {"success": False, "error": str(e)}
    
    elif action == "update_payload":
        updated_payload = kwargs.get("updated_payload", task.payload)
        try:
            import psycopg
            import os
            conn_string = os.getenv("DATABASE_URL")
            with psycopg.connect(conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE task_queue
                        SET status = %s, payload = %s, retry_count = 0, error = NULL, started_at = NULL, heartbeat_at = NULL
                        WHERE task_id = %s
                    """, (TaskStatus.PENDING.value, psycopg.types.json.dumps(updated_payload), task_id))
                    conn.commit()
            logger.info(f"Task {task_id} updated and moved to PENDING")
            return {"success": True, "action": "update_payload", "task_id": task_id}
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            return {"success": False, "error": str(e)}
    
    elif action == "skip":
        # Mark as skipped (could add a SKIPPED status, or leave in DLQ)
        logger.info(f"Task {task_id} marked as skipped")
        return {"success": True, "action": "skip", "task_id": task_id}
    
    else:
        return {"success": False, "error": f"Unknown action: {action}"}


async def list_dead_letter_tasks(limit: int = 50) -> List[Dict[str, Any]]:
    """List tasks in dead-letter queue for triage."""
    queue = get_queue()
    tasks = queue.get_dead_letter_tasks(limit=limit)
    return [
        {
            "task_id": t.task_id,
            "task_type": t.task_type,
            "domain": t.domain,
            "source": t.source,
            "error": t.error,
            "retry_count": t.retry_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tasks
    ]
