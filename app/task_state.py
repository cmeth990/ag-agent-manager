"""
Task state tracking for agent swarm.
Enables: "Track task state (pending, in_progress, completed, failed)"
"""
import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task lifecycle states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStateRegistry:
    """
    Registry of task state per thread_id (e.g. chat_id).
    Supervisor/telemetry can query state without relying on chat memory.
    """
    _lock = Lock()
    _by_thread: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def set_status(
        cls,
        thread_id: str,
        status: TaskStatus,
        agent: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set task status for a thread."""
        with cls._lock:
            if thread_id not in cls._by_thread:
                cls._by_thread[thread_id] = {
                    "thread_id": thread_id,
                    "status": TaskStatus.PENDING.value,
                    "agent": None,
                    "error": None,
                    "updated_at": None,
                    "metadata": {},
                }
            rec = cls._by_thread[thread_id]
            rec["status"] = status.value
            rec["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if agent is not None:
                rec["agent"] = agent
            if error is not None:
                rec["error"] = error
            if metadata:
                rec["metadata"] = {**(rec.get("metadata") or {}), **metadata}
            logger.debug(f"Task state: thread_id={thread_id} status={status.value} agent={agent}")

    @classmethod
    def get_status(cls, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get current task state for a thread."""
        with cls._lock:
            return cls._by_thread.get(thread_id)

    @classmethod
    def list_recent(cls, limit: int = 50) -> list:
        """List recent task states (for telemetry/supervisor)."""
        with cls._lock:
            items = list(cls._by_thread.values())
            items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
            return items[:limit]

    @classmethod
    def clear(cls, thread_id: Optional[str] = None) -> None:
        """Clear state for one thread or all threads."""
        with cls._lock:
            if thread_id:
                cls._by_thread.pop(thread_id, None)
            else:
                cls._by_thread.clear()


def set_task_status(
    thread_id: str,
    status: TaskStatus,
    agent: Optional[str] = None,
    error: Optional[str] = None,
    **metadata: Any,
) -> None:
    """Convenience: set task status for a thread."""
    TaskStateRegistry.set_status(
        thread_id=thread_id,
        status=status,
        agent=agent,
        error=error,
        metadata=metadata if metadata else None,
    )


def get_task_status(thread_id: str) -> Optional[Dict[str, Any]]:
    """Convenience: get task status for a thread."""
    return TaskStateRegistry.get_status(thread_id)
