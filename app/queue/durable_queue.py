"""
Durable task queue using Postgres (not in-memory).
Enables: "Durable queues (not in-memory)"
"""
import logging
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from threading import Lock

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status in queue."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"  # Moved to DLQ after max retries


@dataclass
class TaskRecord:
    """Record of a task in the durable queue."""
    task_id: str
    task_type: str  # e.g., "source_gathering", "domain_scout", "kg_ingest"
    payload: Dict[str, Any]
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    domain: Optional[str] = None
    source: Optional[str] = None
    agent: Optional[str] = None
    heartbeat_at: Optional[datetime] = None  # For stuck task detection


class DurableTaskQueue:
    """
    Durable task queue backed by Postgres.
    Tasks survive restarts and can be retried.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise ValueError("DATABASE_URL required for durable queue")
        
        self._lock = Lock()
        self._initialized = False
    
    def _ensure_table(self):
        """Create tasks table if it doesn't exist."""
        if self._initialized:
            return
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS task_queue (
                            task_id VARCHAR(255) PRIMARY KEY,
                            task_type VARCHAR(100) NOT NULL,
                            payload JSONB NOT NULL,
                            status VARCHAR(50) NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            updated_at TIMESTAMP NOT NULL,
                            started_at TIMESTAMP,
                            completed_at TIMESTAMP,
                            retry_count INTEGER DEFAULT 0,
                            max_retries INTEGER DEFAULT 3,
                            error TEXT,
                            result JSONB,
                            domain VARCHAR(255),
                            source VARCHAR(255),
                            agent VARCHAR(255),
                            heartbeat_at TIMESTAMP
                        )
                    """)
                    # Create indexes
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue(status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_task_domain ON task_queue(domain)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_task_created ON task_queue(created_at)")
                    conn.commit()
                    self._initialized = True
                    logger.info("Durable task queue table created/verified")
        except Exception as e:
            logger.error(f"Failed to create task queue table: {e}")
            raise
    
    def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        domain: Optional[str] = None,
        source: Optional[str] = None,
        agent: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Enqueue a task.
        
        Returns:
            task_id
        """
        self._ensure_table()
        task_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO task_queue (
                            task_id, task_type, payload, status, created_at, updated_at,
                            retry_count, max_retries, domain, source, agent
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id, task_type, psycopg.types.json.dumps(payload),
                        TaskStatus.PENDING.value, now, now,
                        0, max_retries, domain, source, agent
                    ))
                    conn.commit()
                    logger.info(f"Enqueued task {task_id} ({task_type})")
                    return task_id
        except Exception as e:
            logger.error(f"Failed to enqueue task: {e}")
            raise
    
    def dequeue(
        self,
        task_type: Optional[str] = None,
        limit: int = 1,
    ) -> List[TaskRecord]:
        """
        Dequeue tasks (mark as IN_PROGRESS and return).
        Returns oldest PENDING tasks first.
        """
        self._ensure_table()
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    # Select and update in one transaction
                    if task_type:
                        cur.execute("""
                            SELECT task_id FROM task_queue
                            WHERE status = %s AND task_type = %s
                            ORDER BY created_at ASC
                            LIMIT %s
                            FOR UPDATE SKIP LOCKED
                        """, (TaskStatus.PENDING.value, task_type, limit))
                    else:
                        cur.execute("""
                            SELECT task_id FROM task_queue
                            WHERE status = %s
                            ORDER BY created_at ASC
                            LIMIT %s
                            FOR UPDATE SKIP LOCKED
                        """, (TaskStatus.PENDING.value, limit))
                    
                    task_ids = [row[0] for row in cur.fetchall()]
                    
                    if not task_ids:
                        return []
                    
                    # Update to IN_PROGRESS
                    now = datetime.utcnow()
                    cur.execute("""
                        UPDATE task_queue
                        SET status = %s, updated_at = %s, started_at = COALESCE(started_at, %s), heartbeat_at = %s
                        WHERE task_id = ANY(%s)
                    """, (TaskStatus.IN_PROGRESS.value, now, now, now, task_ids))
                    
                    # Fetch full records
                    cur.execute("""
                        SELECT task_id, task_type, payload, status, created_at, updated_at,
                               started_at, completed_at, retry_count, max_retries,
                               error, result, domain, source, agent, heartbeat_at
                        FROM task_queue
                        WHERE task_id = ANY(%s)
                    """, (task_ids,))
                    
                    records = []
                    for row in cur.fetchall():
                        records.append(TaskRecord(
                            task_id=row[0],
                            task_type=row[1],
                            payload=psycopg.types.json.loads(row[2]) if row[2] else {},
                            status=TaskStatus(row[3]),
                            created_at=row[4],
                            updated_at=row[5],
                            started_at=row[6],
                            completed_at=row[7],
                            retry_count=row[8],
                            max_retries=row[9],
                            error=row[10],
                            result=psycopg.types.json.loads(row[11]) if row[11] else None,
                            domain=row[12],
                            source=row[13],
                            agent=row[14],
                            heartbeat_at=row[15],
                        ))
                    
                    conn.commit()
                    return records
        except Exception as e:
            logger.error(f"Failed to dequeue tasks: {e}")
            return []
    
    def complete(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark task as completed."""
        self._ensure_table()
        now = datetime.utcnow()
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE task_queue
                        SET status = %s, updated_at = %s, completed_at = %s, result = %s
                        WHERE task_id = %s
                    """, (
                        TaskStatus.COMPLETED.value, now, now,
                        psycopg.types.json.dumps(result) if result else None,
                        task_id
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to complete task {task_id}: {e}")
    
    def fail(
        self,
        task_id: str,
        error: str,
        retry: bool = True,
    ) -> None:
        """
        Mark task as failed.
        If retry=True and retry_count < max_retries, resets to PENDING for retry.
        Otherwise moves to DEAD_LETTER.
        """
        self._ensure_table()
        now = datetime.utcnow()
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    # Get current retry count
                    cur.execute("SELECT retry_count, max_retries FROM task_queue WHERE task_id = %s", (task_id,))
                    row = cur.fetchone()
                    if not row:
                        return
                    retry_count, max_retries = row
                    
                    if retry and retry_count < max_retries:
                        # Retry: reset to PENDING
                        cur.execute("""
                            UPDATE task_queue
                            SET status = %s, updated_at = %s, retry_count = retry_count + 1, error = %s,
                                started_at = NULL, heartbeat_at = NULL
                            WHERE task_id = %s
                        """, (TaskStatus.PENDING.value, now, error[:1000], task_id))
                        logger.info(f"Task {task_id} failed, will retry ({retry_count + 1}/{max_retries})")
                    else:
                        # Move to dead-letter queue
                        cur.execute("""
                            UPDATE task_queue
                            SET status = %s, updated_at = %s, error = %s, completed_at = %s
                            WHERE task_id = %s
                        """, (TaskStatus.DEAD_LETTER.value, now, error[:1000], now, task_id))
                        logger.warning(f"Task {task_id} moved to dead-letter queue after {retry_count} retries")
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to fail task {task_id}: {e}")
    
    def heartbeat(self, task_id: str) -> None:
        """Update heartbeat timestamp (for stuck task detection)."""
        self._ensure_table()
        now = datetime.utcnow()
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE task_queue
                        SET heartbeat_at = %s, updated_at = %s
                        WHERE task_id = %s AND status = %s
                    """, (now, now, task_id, TaskStatus.IN_PROGRESS.value))
                    conn.commit()
        except Exception as e:
            logger.debug(f"Failed to update heartbeat for {task_id}: {e}")
    
    def get_stuck_tasks(
        self,
        stuck_threshold_minutes: int = 30,
    ) -> List[TaskRecord]:
        """
        Find tasks that are IN_PROGRESS but haven't sent heartbeat recently.
        These are likely stuck and should be retried or moved to DLQ.
        """
        self._ensure_table()
        cutoff = datetime.utcnow() - timedelta(minutes=stuck_threshold_minutes)
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT task_id, task_type, payload, status, created_at, updated_at,
                               started_at, completed_at, retry_count, max_retries,
                               error, result, domain, source, agent, heartbeat_at
                        FROM task_queue
                        WHERE status = %s
                          AND (heartbeat_at IS NULL OR heartbeat_at < %s)
                        ORDER BY updated_at ASC
                    """, (TaskStatus.IN_PROGRESS.value, cutoff))
                    
                    records = []
                    for row in cur.fetchall():
                        records.append(TaskRecord(
                            task_id=row[0],
                            task_type=row[1],
                            payload=psycopg.types.json.loads(row[2]) if row[2] else {},
                            status=TaskStatus(row[3]),
                            created_at=row[4],
                            updated_at=row[5],
                            started_at=row[6],
                            completed_at=row[7],
                            retry_count=row[8],
                            max_retries=row[9],
                            error=row[10],
                            result=psycopg.types.json.loads(row[11]) if row[11] else None,
                            domain=row[12],
                            source=row[13],
                            agent=row[14],
                            heartbeat_at=row[15],
                        ))
                    
                    return records
        except Exception as e:
            logger.error(f"Failed to get stuck tasks: {e}")
            return []
    
    def get_dead_letter_tasks(self, limit: int = 100) -> List[TaskRecord]:
        """Get tasks in dead-letter queue (for triage)."""
        self._ensure_table()
        
        try:
            import psycopg
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT task_id, task_type, payload, status, created_at, updated_at,
                               started_at, completed_at, retry_count, max_retries,
                               error, result, domain, source, agent, heartbeat_at
                        FROM task_queue
                        WHERE status = %s
                        ORDER BY updated_at DESC
                        LIMIT %s
                    """, (TaskStatus.DEAD_LETTER.value, limit))
                    
                    records = []
                    for row in cur.fetchall():
                        records.append(TaskRecord(
                            task_id=row[0],
                            task_type=row[1],
                            payload=psycopg.types.json.loads(row[2]) if row[2] else {},
                            status=TaskStatus(row[3]),
                            created_at=row[4],
                            updated_at=row[5],
                            started_at=row[6],
                            completed_at=row[7],
                            retry_count=row[8],
                            max_retries=row[9],
                            error=row[10],
                            result=psycopg.types.json.loads(row[11]) if row[11] else None,
                            domain=row[12],
                            source=row[13],
                            agent=row[14],
                            heartbeat_at=row[15],
                        ))
                    
                    return records
        except Exception as e:
            logger.error(f"Failed to get dead-letter tasks: {e}")
            return []


# Global queue instance
_queue: Optional[DurableTaskQueue] = None


def get_queue() -> DurableTaskQueue:
    """Get the global durable task queue instance."""
    global _queue
    if _queue is None:
        _queue = DurableTaskQueue()
    return _queue
