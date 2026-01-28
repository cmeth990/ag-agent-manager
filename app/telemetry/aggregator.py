"""
Telemetry aggregator for system state summarization.
Supervisor can query this instead of relying on chat memory.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from app.cost.tracker import get_cost_tracker
from app.cost.budget import get_budget_manager
from app.circuit_breaker import CircuitBreakerRegistry
from app.task_state import TaskStateRegistry, TaskStatus

logger = logging.getLogger(__name__)


def get_system_state() -> Dict[str, Any]:
    """
    Get comprehensive system state from telemetry.
    
    Returns:
        Dict with:
        - agent_health: Circuit breaker status per domain/source
        - cost_tracking: Current costs, budgets, limits
        - task_states: Recent task states (pending/in_progress/completed/failed)
        - error_rates: Error counts and rates
        - processing_rates: Tasks processed per time period
        - kg_statistics: KG version, change history
    """
    state = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent_health": get_agent_health(),
        "cost_tracking": get_cost_tracking(),
        "task_states": get_task_states(),
        "error_rates": get_error_rates(),
        "processing_rates": get_processing_rates(),
        "kg_statistics": get_kg_statistics(),
    }
    return state


def get_agent_health() -> Dict[str, Any]:
    """Get agent health status from circuit breakers."""
    try:
        status = CircuitBreakerRegistry.list_status()
        
        # Count by state
        domain_states = {}
        source_states = {}
        
        for domain, domain_status in status.get("domains", {}).items():
            state = domain_status.get("state", "closed")
            domain_states[state] = domain_states.get(state, 0) + 1
        
        for source, source_status in status.get("sources", {}).items():
            state = source_status.get("state", "closed")
            source_states[state] = source_states.get(state, 0) + 1
        
        return {
            "domains": {
                "total": len(status.get("domains", {})),
                "by_state": domain_states,
                "open": [k for k, v in status.get("domains", {}).items() if v.get("state") == "open"],
                "half_open": [k for k, v in status.get("domains", {}).items() if v.get("state") == "half_open"],
            },
            "sources": {
                "total": len(status.get("sources", {})),
                "by_state": source_states,
                "open": [k for k, v in status.get("sources", {}).items() if v.get("state") == "open"],
                "half_open": [k for k, v in status.get("sources", {}).items() if v.get("state") == "half_open"],
            },
            "status": status,
        }
    except Exception as e:
        logger.error(f"Error getting agent health: {e}")
        return {"error": str(e)}


def get_cost_tracking() -> Dict[str, Any]:
    """Get cost tracking statistics."""
    try:
        tracker = get_cost_tracker()
        budget_manager = get_budget_manager()
        
        stats = tracker.get_stats()
        budget_status = budget_manager.get_status()
        
        return {
            "total_cost_usd": stats.get("total_cost_usd", 0.0),
            "total_calls": stats.get("total_calls", 0),
            "successful_calls": stats.get("successful_calls", 0),
            "failed_calls": stats.get("failed_calls", 0),
            "total_tokens": stats.get("total_tokens", 0),
            "top_domains": stats.get("top_domains", [])[:5],
            "top_queues": stats.get("top_queues", [])[:5],
            "budget": {
                "global_daily_limit": budget_status.get("global_daily_limit"),
                "global_daily_spent": budget_status.get("global_daily_spent", 0.0),
                "global_daily_remaining": budget_status.get("global_daily_remaining"),
                "domain_limits": len(budget_status.get("domain_limits", {})),
                "queue_limits": len(budget_status.get("queue_limits", {})),
            },
        }
    except Exception as e:
        logger.error(f"Error getting cost tracking: {e}")
        return {"error": str(e)}


def get_task_states() -> Dict[str, Any]:
    """Get task state statistics."""
    try:
        recent_tasks = TaskStateRegistry.list_recent(limit=100)
        
        # Count by status
        by_status = {}
        for task in recent_tasks:
            status = task.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
        
        # Count by agent
        by_agent = {}
        for task in recent_tasks:
            agent = task.get("agent", "unknown")
            by_agent[agent] = by_agent.get(agent, 0) + 1
        
        # Recent failures
        failed_tasks = [
            t for t in recent_tasks
            if t.get("status") == TaskStatus.FAILED.value
        ][:10]
        
        return {
            "total_tasks": len(recent_tasks),
            "by_status": by_status,
            "by_agent": by_agent,
            "recent_failures": [
                {
                    "thread_id": t.get("thread_id"),
                    "agent": t.get("agent"),
                    "error": t.get("error"),
                    "updated_at": t.get("updated_at"),
                }
                for t in failed_tasks
            ],
        }
    except Exception as e:
        logger.error(f"Error getting task states: {e}")
        return {"error": str(e)}


def get_error_rates() -> Dict[str, Any]:
    """Get error rate statistics."""
    try:
        tracker = get_cost_tracker()
        recent_calls = tracker.get_recent_calls(limit=100)
        
        # Count errors in recent calls
        errors = [c for c in recent_calls if not c.success]
        error_rate = len(errors) / len(recent_calls) if recent_calls else 0.0
        
        # Error by provider
        errors_by_provider = {}
        for call in errors:
            provider = call.provider
            errors_by_provider[provider] = errors_by_provider.get(provider, 0) + 1
        
        return {
            "recent_calls": len(recent_calls),
            "errors": len(errors),
            "error_rate": error_rate,
            "errors_by_provider": errors_by_provider,
            "recent_errors": [
                {
                    "model": e.model,
                    "provider": e.provider,
                    "error": e.error,
                    "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
                }
                for e in errors[:10]
            ],
        }
    except Exception as e:
        logger.error(f"Error getting error rates: {e}")
        return {"error": str(e)}


def get_processing_rates() -> Dict[str, Any]:
    """Get processing rate statistics."""
    try:
        recent_tasks = TaskStateRegistry.list_recent(limit=100)
        
        # Calculate rates (tasks per hour, approximate)
        now = datetime.utcnow()
        tasks_last_hour = []
        for t in recent_tasks:
            if not t.get("updated_at"):
                continue
            try:
                # Parse ISO timestamp
                ts_str = t["updated_at"].replace("Z", "+00:00")
                if "+00:00" not in ts_str:
                    ts_str = ts_str + "+00:00"
                task_time = datetime.fromisoformat(ts_str.replace("+00:00", ""))
                if (now - task_time).total_seconds() < 3600:
                    tasks_last_hour.append(t)
            except Exception:
                continue  # Skip if timestamp parsing fails
        
        completed_tasks = [
            t for t in recent_tasks
            if t.get("status") == TaskStatus.COMPLETED.value
        ]
        
        return {
            "recent_tasks": len(recent_tasks),
            "tasks_last_hour": len(tasks_last_hour),
            "completed_tasks": len(completed_tasks),
            "completion_rate": len(completed_tasks) / len(recent_tasks) if recent_tasks else 0.0,
        }
    except Exception as e:
        logger.error(f"Error getting processing rates: {e}")
        return {"error": str(e)}


def get_kg_statistics() -> Dict[str, Any]:
    """Get KG statistics."""
    try:
        from app.kg.versioning import get_changelog
        
        changelog = get_changelog()
        current_version = changelog.get_current_version()
        recent_versions = changelog.list_versions(limit=10)
        
        return {
            "current_version": current_version,
            "recent_changes": len(recent_versions),
            "latest_change": recent_versions[0] if recent_versions else None,
        }
    except Exception as e:
        logger.error(f"Error getting KG statistics: {e}")
        return {"error": str(e)}


def summarize_state(state: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a human-readable summary of system state.
    
    Args:
        state: Optional system state dict (if None, fetches current state)
    
    Returns:
        Formatted summary string
    """
    if state is None:
        state = get_system_state()
    
    parts = []
    parts.append("📊 **System State Summary**\n")
    
    # Agent Health
    health = state.get("agent_health", {})
    if health and "error" not in health:
        parts.append(f"\n🔧 **Agent Health:**")
        domains = health.get("domains", {})
        sources = health.get("sources", {})
        parts.append(f"  • Domains: {domains.get('total', 0)} total")
        if domains.get("open"):
            parts.append(f"  • ⚠️  Paused domains: {', '.join(domains['open'][:5])}")
        parts.append(f"  • Sources: {sources.get('total', 0)} total")
        if sources.get("open"):
            parts.append(f"  • ⚠️  Paused sources: {', '.join(sources['open'][:5])}")
    
    # Cost Tracking
    costs = state.get("cost_tracking", {})
    if costs and "error" not in costs:
        parts.append(f"\n💰 **Cost Tracking:**")
        parts.append(f"  • Total: ${costs.get('total_cost_usd', 0.0):.4f}")
        parts.append(f"  • Calls: {costs.get('total_calls', 0)} ({costs.get('successful_calls', 0)} successful)")
        budget = costs.get("budget", {})
        if budget.get("global_daily_limit"):
            remaining = budget.get("global_daily_remaining")
            if remaining is not None:
                parts.append(f"  • Daily budget: ${budget.get('global_daily_spent', 0.0):.2f} / ${budget['global_daily_limit']:.2f} (${remaining:.2f} remaining)")
    
    # Task States
    tasks = state.get("task_states", {})
    if tasks and "error" not in tasks:
        parts.append(f"\n📋 **Task States:**")
        parts.append(f"  • Total: {tasks.get('total_tasks', 0)}")
        by_status = tasks.get("by_status", {})
        for status, count in by_status.items():
            parts.append(f"  • {status}: {count}")
        if tasks.get("recent_failures"):
            parts.append(f"  • ⚠️  Recent failures: {len(tasks['recent_failures'])}")
    
    # Error Rates
    errors = state.get("error_rates", {})
    if errors and "error" not in errors:
        parts.append(f"\n❌ **Error Rates:**")
        error_rate = errors.get("error_rate", 0.0)
        parts.append(f"  • Rate: {error_rate:.1%}")
        parts.append(f"  • Recent errors: {errors.get('errors', 0)} / {errors.get('recent_calls', 0)} calls")
    
    # Processing Rates
    processing = state.get("processing_rates", {})
    if processing and "error" not in processing:
        parts.append(f"\n⚡ **Processing:**")
        parts.append(f"  • Tasks last hour: {processing.get('tasks_last_hour', 0)}")
        completion_rate = processing.get("completion_rate", 0.0)
        parts.append(f"  • Completion rate: {completion_rate:.1%}")
    
    # KG Statistics
    kg = state.get("kg_statistics", {})
    if kg and "error" not in kg:
        parts.append(f"\n📚 **Knowledge Graph:**")
        parts.append(f"  • Current version: {kg.get('current_version', 0)}")
        parts.append(f"  • Recent changes: {kg.get('recent_changes', 0)}")
    
    return "\n".join(parts)
