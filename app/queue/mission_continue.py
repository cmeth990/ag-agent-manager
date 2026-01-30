"""
Mission continuation: run expansion (or other mission work) while a key decision is pending.
When the superintendent surfaces a key decision via Telegram, we continue other operations
in the meantime (e.g. source discovery across domains) and optionally notify the user.
"""
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_mission_continue(chat_id: str) -> Dict[str, Any]:
    """
    Run one expansion cycle (source discovery across domains) and send a short
    "Mission continued while you decide" update to the given chat.
    Used when a key decision is pending so other work continues in the meantime.
    """
    from app.graph.expansion import run_expansion_cycle
    from app.telegram import send_message

    try:
        result = await run_expansion_cycle()
        total = result.get("total_sources", 0)
        domains = result.get("domains_explored", [])
        with_ids = result.get("with_primary_ids", 0)
        update_message = result.get("update_message", "")
        short = (
            f"📈 **Mission continued while you decide:** discovered {total} sources "
            f"across {len(domains)} domain(s) ({with_ids} with primary IDs)."
        )
        try:
            await send_message(int(chat_id), short)
        except Exception as e:
            logger.warning(f"Could not send mission-continue update to {chat_id}: {e}")
        return {"total_sources": total, "domains_explored": domains, "update_message": update_message}
    except Exception as e:
        logger.warning(f"Mission continue (expansion) failed: {e}")
        try:
            await send_message(
                int(chat_id),
                "📈 Mission continued in background; expansion cycle had an issue (see logs)."
            )
        except Exception as send_err:
            logger.warning(f"Could not send fallback message: {send_err}")
        return {"error": str(e)}
