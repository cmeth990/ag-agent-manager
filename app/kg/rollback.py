"""
KG rollback functionality.
Enables rolling back KG to a previous version.
"""
import logging
from typing import Dict, Any, Optional
from app.kg.versioning import get_changelog
from app.kg.client import apply_diff

logger = logging.getLogger(__name__)


async def rollback_to_version(target_version: int) -> Dict[str, Any]:
    """
    Rollback KG to a specific version.
    
    Args:
        target_version: Version number to rollback to (0 = initial state)
    
    Returns:
        Result dict with success status and details
    """
    changelog = get_changelog()
    current_version = changelog.get_current_version()
    
    if target_version < 0:
        return {
            "success": False,
            "error": f"Invalid target version: {target_version} (must be >= 0)",
        }
    
    if target_version >= current_version:
        return {
            "success": False,
            "error": f"Cannot rollback to version {target_version} (current version is {current_version})",
        }
    
    logger.info(f"Rolling back KG from version {current_version} to {target_version}")
    
    # Generate reverse diff
    reverse_diff = changelog.get_diff_for_rollback(target_version)
    if not reverse_diff:
        return {
            "success": False,
            "error": f"Could not generate rollback diff to version {target_version}",
        }
    
    # Apply reverse diff
    try:
        result = await apply_diff(reverse_diff)
        
        if result.get("success"):
            # Update changelog to reflect rollback
            from app.kg.versioning import record_kg_change
            record_kg_change(
                diff=reverse_diff,
                diff_id=None,  # Auto-generate
                source_agent="rollback_system",
                reason=f"Rollback from version {current_version} to {target_version}",
                result=result,
            )
            
            logger.info(f"Successfully rolled back to version {target_version}")
            return {
                "success": True,
                "from_version": current_version,
                "to_version": target_version,
                "rollback_result": result,
            }
        else:
            return {
                "success": False,
                "error": f"Rollback diff application failed: {result.get('error', 'Unknown error')}",
                "rollback_result": result,
            }
    except Exception as e:
        logger.error(f"Error during rollback: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Rollback failed: {str(e)}",
        }


async def list_versions(limit: int = 20) -> Dict[str, Any]:
    """
    List recent KG versions.
    
    Args:
        limit: Maximum number of versions to return
    
    Returns:
        Dict with versions list and current version
    """
    changelog = get_changelog()
    versions = changelog.list_versions(limit=limit)
    current_version = changelog.get_current_version()
    
    return {
        "current_version": current_version,
        "versions": versions,
        "count": len(versions),
    }


async def get_version_info(version: int) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific version.
    
    Args:
        version: Version number
    
    Returns:
        Version record dict or None if not found
    """
    changelog = get_changelog()
    return changelog.get_version(version)
