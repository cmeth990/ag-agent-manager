"""
KG versioning and rollback system.
Enables: "Can you roll back graph changes?"
- Store KG changes in a changelog
- Implement versioning (incremental)
- Provide rollback to previous state
"""
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class KGChangelog:
    """
    Changelog for KG modifications.
    Stores incremental changes (diffs) with version numbers.
    """
    
    def __init__(self):
        self._lock = Lock()
        # In-memory storage (could be persisted to DB/file)
        self._versions: List[Dict[str, Any]] = []
        self._current_version = 0
    
    def record_diff(
        self,
        diff: Dict[str, Any],
        diff_id: Optional[str] = None,
        source_agent: Optional[str] = None,
        source_document: Optional[str] = None,
        reason: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a diff application in the changelog.
        
        Args:
            diff: The diff that was applied
            diff_id: Unique diff identifier
            source_agent: Agent that created the diff
            source_document: Source document/input
            reason: Reason for the change
            result: Result from apply_diff (counts, errors, etc.)
        
        Returns:
            Version record dict
        """
        if diff_id is None:
            diff_id = str(uuid.uuid4())
        
        with self._lock:
            self._current_version += 1
            version_record = {
                "version": self._current_version,
                "diff_id": diff_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "diff": diff.copy(),  # Store full diff
                "source_agent": source_agent,
                "source_document": source_document,
                "reason": reason,
                "result": result.copy() if result else None,
                "summary": self._summarize_diff(diff),
            }
            self._versions.append(version_record)
            logger.info(f"Recorded KG change: version {self._current_version}, diff_id={diff_id}")
            return version_record
    
    def _summarize_diff(self, diff: Dict[str, Any]) -> str:
        """Create a summary string for a diff."""
        nodes_add = len(diff.get("nodes", {}).get("add", []))
        nodes_update = len(diff.get("nodes", {}).get("update", []))
        nodes_delete = len(diff.get("nodes", {}).get("delete", []))
        edges_add = len(diff.get("edges", {}).get("add", []))
        edges_update = len(diff.get("edges", {}).get("update", []))
        edges_delete = len(diff.get("edges", {}).get("delete", []))
        
        parts = []
        if nodes_add > 0:
            parts.append(f"+{nodes_add} nodes")
        if nodes_update > 0:
            parts.append(f"~{nodes_update} nodes")
        if nodes_delete > 0:
            parts.append(f"-{nodes_delete} nodes")
        if edges_add > 0:
            parts.append(f"+{edges_add} edges")
        if edges_update > 0:
            parts.append(f"~{edges_update} edges")
        if edges_delete > 0:
            parts.append(f"-{edges_delete} edges")
        
        return ", ".join(parts) if parts else "No changes"
    
    def get_version(self, version: int) -> Optional[Dict[str, Any]]:
        """Get a specific version record."""
        with self._lock:
            for v in self._versions:
                if v["version"] == version:
                    return v.copy()
            return None
    
    def get_current_version(self) -> int:
        """Get current version number."""
        with self._lock:
            return self._current_version
    
    def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent versions (most recent first)."""
        with self._lock:
            versions = self._versions[-limit:]
            return [v.copy() for v in reversed(versions)]
    
    def get_diff_for_rollback(self, target_version: int) -> Optional[Dict[str, Any]]:
        """
        Generate a reverse diff to rollback from current to target_version.
        
        Args:
            target_version: Version to rollback to
        
        Returns:
            Reverse diff dict (to undo changes from target_version+1 to current)
        """
        with self._lock:
            if target_version < 0 or target_version >= self._current_version:
                return None
            
            # Collect all diffs from target_version+1 to current
            reverse_diff = {
                "nodes": {"add": [], "update": [], "delete": []},
                "edges": {"add": [], "update": [], "delete": []},
                "metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "source": "rollback",
                    "reason": f"Rollback from version {self._current_version} to {target_version}",
                },
            }
            
            # Reverse each diff from target_version+1 to current
            for version in range(target_version + 1, self._current_version + 1):
                version_record = self.get_version(version)
                if not version_record:
                    continue
                
                diff = version_record["diff"]
                
                # Reverse: add -> delete, delete -> add, update -> update (restore previous)
                # For simplicity, we'll delete what was added and add what was deleted
                reverse_diff["nodes"]["delete"].extend(diff.get("nodes", {}).get("add", []))
                reverse_diff["nodes"]["add"].extend(diff.get("nodes", {}).get("delete", []))
                # Updates are trickier - we'd need previous state, so we'll skip for now
                # In production, you'd store the previous state before update
                
                reverse_diff["edges"]["delete"].extend(diff.get("edges", {}).get("add", []))
                reverse_diff["edges"]["add"].extend(diff.get("edges", {}).get("delete", []))
            
            return reverse_diff


# Global changelog instance
_changelog = KGChangelog()


def get_changelog() -> KGChangelog:
    """Get the global changelog instance."""
    return _changelog


def record_kg_change(
    diff: Dict[str, Any],
    diff_id: Optional[str] = None,
    source_agent: Optional[str] = None,
    source_document: Optional[str] = None,
    reason: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to record a KG change.
    
    Usage:
        version = record_kg_change(
            diff=proposed_diff,
            diff_id=diff_id,
            source_agent="writer_node",
            result=apply_result
        )
    """
    return _changelog.record_diff(
        diff=diff,
        diff_id=diff_id,
        source_agent=source_agent,
        source_document=source_document,
        reason=reason,
        result=result,
    )
