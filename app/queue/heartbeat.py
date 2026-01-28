"""
Heartbeat monitoring and stuck task detection.
Enables: "Heartbeats + 'stuck task' detection"
"""
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.queue.durable_queue import get_queue, TaskStatus

logger = logging.getLogger(__name__)

# Default: task is stuck if no heartbeat for 30 minutes
DEFAULT_STUCK_THRESHOLD_MINUTES = 30


async def monitor_stuck_tasks(
    stuck_threshold_minutes: int = DEFAULT_STUCK_THRESHOLD_MINUTES,
    auto_retry: bool = False,
) -> Dict[str, Any]:
    """
    Monitor for stuck tasks and optionally retry them.
    
    Args:
        stuck_threshold_minutes: Minutes without heartbeat = stuck
        auto_retry: If True, automatically reset stuck tasks to PENDING
    
    Returns:
        Dict with stuck tasks and actions taken
    """
    queue = get_queue()
    stuck = queue.get_stuck_tasks(stuck_threshold_minutes=stuck_threshold_minutes)
    
    if not stuck:
        return {
            "stuck_count": 0,
            "stuck_tasks": [],
            "actions": [],
        }
    
    actions = []
    for task in stuck:
        logger.warning(
            f"Stuck task detected: {task.task_id} ({task.task_type}) "
            f"last heartbeat: {task.heartbeat_at or 'never'}"
        )
        
        if auto_retry and task.retry_count < task.max_retries:
            # Reset to PENDING for retry
            try:
                import psycopg
                import os
                conn_string = os.getenv("DATABASE_URL")
                with psycopg.connect(conn_string) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE task_queue
                            SET status = %s, retry_count = retry_count + 1, error = %s,
                                started_at = NULL, heartbeat_at = NULL
                            WHERE task_id = %s
                        """, (
                            TaskStatus.PENDING.value,
                            f"Stuck task detected (no heartbeat for {stuck_threshold_minutes} min)",
                            task.task_id
                        ))
                        conn.commit()
                actions.append({
                    "task_id": task.task_id,
                    "action": "auto_retry",
                    "reason": "stuck_task",
                })
                logger.info(f"Auto-retried stuck task {task.task_id}")
            except Exception as e:
                logger.error(f"Failed to auto-retry stuck task {task.task_id}: {e}")
        else:
            # Move to DLQ if max retries exceeded
            if task.retry_count >= task.max_retries:
                try:
                    import psycopg
                    import os
                    conn_string = os.getenv("DATABASE_URL")
                    with psycopg.connect(conn_string) as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE task_queue
                                SET status = %s, error = %s
                                WHERE task_id = %s
                            """, (
                                TaskStatus.DEAD_LETTER.value,
                                f"Stuck task (no heartbeat for {stuck_threshold_minutes} min) after {task.retry_count} retries",
                                task.task_id
                            ))
                            conn.commit()
                    actions.append({
                        "task_id": task.task_id,
                        "action": "move_to_dlq",
                        "reason": "stuck_after_max_retries",
                    })
                    logger.warning(f"Moved stuck task {task.task_id} to DLQ")
                except Exception as e:
                    logger.error(f"Failed to move stuck task {task.task_id} to DLQ: {e}")
    
    return {
        "stuck_count": len(stuck),
        "stuck_tasks": [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "domain": t.domain,
                "retry_count": t.retry_count,
                "last_heartbeat": t.heartbeat_at.isoformat() if t.heartbeat_at else None,
                "started_at": t.started_at.isoformat() if t.started_at else None,
            }
            for t in stuck
        ],
        "actions": actions,
    }


async def start_heartbeat_monitor(
    interval_seconds: int = 300,  # Check every 5 minutes
    stuck_threshold_minutes: int = DEFAULT_STUCK_THRESHOLD_MINUTES,
    auto_retry: bool = False,
) -> None:
    """
    Background task to monitor for stuck tasks.
    Run this in a background task/thread.
    """
    logger.info(f"Heartbeat monitor started (check every {interval_seconds}s, stuck threshold: {stuck_threshold_minutes}m)")
    
    while True:
        try:
            result = await monitor_stuck_tasks(
                stuck_threshold_minutes=stuck_threshold_minutes,
                auto_retry=auto_retry,
            )
            if result["stuck_count"] > 0:
                logger.warning(f"Heartbeat monitor: found {result['stuck_count']} stuck tasks")
        except Exception as e:
            logger.error(f"Heartbeat monitor error: {e}")
        
        await asyncio.sleep(interval_seconds)
