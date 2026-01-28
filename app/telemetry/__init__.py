"""
Telemetry system for agent swarm.
Enables: "Can your supervisor summarize state from telemetry (not chat memory)?"
"""
from app.telemetry.aggregator import get_system_state, summarize_state

__all__ = ["get_system_state", "summarize_state"]
