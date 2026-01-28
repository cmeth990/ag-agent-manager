"""
Parallel Agent Execution
Runs multiple agents simultaneously with progress updates.
"""
import logging
import asyncio
from typing import Dict, Any, List
from app.graph.state import AgentState
from app.graph.source_gatherer import source_gatherer_node
from app.graph.domain_scout_worker import domain_scout_node
from app.telegram import send_message
from app.kg.domains import DOMAIN_TAXONOMY
import random

logger = logging.getLogger(__name__)


def get_random_domain() -> str:
    """
    Pick a random domain from the taxonomy.
    """
    all_domains = []
    for category, domains in DOMAIN_TAXONOMY.items():
        if isinstance(domains, dict):
            all_domains.extend(domains.keys())
    
    if not all_domains:
        return "Machine Learning"  # Fallback
    
    return random.choice(all_domains)


async def send_progress_update(chat_id: str, message: str):
    """
    Send progress update to Telegram.
    """
    try:
        if chat_id:
            await send_message(int(chat_id), message, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Failed to send progress update: {e}")


async def parallel_agents_node(state: AgentState) -> Dict[str, Any]:
    """
    Run source gatherer and domain scout agents in parallel with progress updates.
    
    Args:
        state: Agent state with user_input and chat_id
    
    Returns:
        Combined results from both agents
    """
    user_input = state.get("user_input", "")
    chat_id = state.get("chat_id")
    
    # Extract domain from input or pick random
    domain = None
    if "for" in user_input.lower():
        # Try to extract domain from input
        parts = user_input.lower().split("for")
        if len(parts) > 1:
            domain = parts[1].strip()
    
    if not domain:
        domain = get_random_domain()
    
    logger.info(f"Running parallel agents for domain: {domain}")
    
    # Send initial status
    if chat_id:
        await send_progress_update(
            chat_id,
            f"🚀 Starting parallel agent execution...\n\n"
            f"📌 Selected Domain: **{domain}**\n"
            f"🔍 Running:\n"
            f"  • Source Gatherer Agent\n"
            f"  • Domain Scout Agent\n\n"
            f"⏳ Processing..."
        )
    
    # Create states for each agent
    source_state: AgentState = {
        "user_input": f"/gather sources for {domain}",
        "chat_id": chat_id,
        "intent": "gather_sources",
        "task_queue": [],
        "working_notes": {},
        "proposed_diff": None,
        "diff_id": None,
        "approval_required": False,
        "approval_decision": None,
        "final_response": None,
        "error": None
    }
    
    scout_state: AgentState = {
        "user_input": "/scout domains",
        "chat_id": chat_id,
        "intent": "scout_domains",
        "task_queue": [],
        "working_notes": {},
        "proposed_diff": None,
        "diff_id": None,
        "approval_required": False,
        "approval_decision": None,
        "final_response": None,
        "error": None
    }
    
    # Progress tracking
    source_progress = {"status": "starting", "message": None}
    scout_progress = {"status": "starting", "message": None}
    
    async def run_source_gatherer():
        """Run source gatherer with progress updates and timeout."""
        try:
            source_progress["status"] = "running"
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"📚 **Source Gatherer** started\n"
                    f"   Searching for sources: {domain}"
                )
            
            # Add timeout to prevent hanging
            result = await asyncio.wait_for(
                source_gatherer_node(source_state),
                timeout=120.0  # 2 minute timeout
            )
            source_progress["status"] = "completed"
            source_progress["message"] = result.get("final_response", "Completed")
            
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"✅ **Source Gatherer** completed\n"
                    f"   Found sources for: {domain}"
                )
            
            return result
        except asyncio.TimeoutError:
            logger.error("Source gatherer timed out after 2 minutes")
            source_progress["status"] = "timeout"
            source_progress["message"] = "Timeout after 2 minutes"
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"⏱️ **Source Gatherer** timed out\n"
                    f"   Taking too long, stopping..."
                )
            return {"error": "Timeout", "final_response": "Source gathering timed out after 2 minutes"}
        except Exception as e:
            logger.error(f"Source gatherer error: {e}", exc_info=True)
            source_progress["status"] = "error"
            source_progress["message"] = str(e)
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"❌ **Source Gatherer** error: {str(e)[:200]}"
                )
            return {"error": str(e), "final_response": None}
    
    async def run_domain_scout():
        """Run domain scout with progress updates and timeout."""
        try:
            scout_progress["status"] = "running"
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"🔍 **Domain Scout** started\n"
                    f"   Searching for new domains..."
                )
            
            # Add timeout to prevent hanging
            result = await asyncio.wait_for(
                domain_scout_node(scout_state),
                timeout=120.0  # 2 minute timeout
            )
            scout_progress["status"] = "completed"
            scout_progress["message"] = result.get("final_response", "Completed")
            
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"✅ **Domain Scout** completed\n"
                    f"   Discovered new domains"
                )
            
            return result
        except asyncio.TimeoutError:
            logger.error("Domain scout timed out after 2 minutes")
            scout_progress["status"] = "timeout"
            scout_progress["message"] = "Timeout after 2 minutes"
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"⏱️ **Domain Scout** timed out\n"
                    f"   Taking too long, stopping..."
                )
            return {"error": "Timeout", "final_response": "Domain scouting timed out after 2 minutes"}
        except Exception as e:
            logger.error(f"Domain scout error: {e}", exc_info=True)
            scout_progress["status"] = "error"
            scout_progress["message"] = str(e)
            if chat_id:
                await send_progress_update(
                    chat_id,
                    f"❌ **Domain Scout** error: {str(e)[:200]}"
                )
            return {"error": str(e), "final_response": None}
    
    # Run both agents in parallel with overall timeout
    try:
        source_result, scout_result = await asyncio.wait_for(
            asyncio.gather(
                run_source_gatherer(),
                run_domain_scout(),
                return_exceptions=True
            ),
            timeout=180.0  # 3 minute overall timeout
        )
        
        # Handle exceptions
        if isinstance(source_result, Exception):
            source_result = {"error": str(source_result), "final_response": None}
        if isinstance(scout_result, Exception):
            scout_result = {"error": str(scout_result), "final_response": None}
        
    except asyncio.TimeoutError:
        logger.error("Parallel execution timed out after 3 minutes")
        if chat_id:
            await send_progress_update(
                chat_id,
                f"⏱️ **Overall timeout**\n"
                f"   Both agents exceeded 3 minute limit"
            )
        source_result = {"error": "Overall timeout", "final_response": "Execution timed out after 3 minutes"}
        scout_result = {"error": "Overall timeout", "final_response": "Execution timed out after 3 minutes"}
    except Exception as e:
        logger.error(f"Parallel execution error: {e}", exc_info=True)
        source_result = {"error": str(e), "final_response": None}
        scout_result = {"error": str(e), "final_response": None}
    
    # Compile final response
    response_parts = []
    response_parts.append("=" * 60)
    response_parts.append("📊 PARALLEL AGENT EXECUTION RESULTS")
    response_parts.append("=" * 60)
    response_parts.append(f"\n🎯 Test Domain: **{domain}**\n")
    
    # Source Gatherer Results
    response_parts.append("\n" + "=" * 60)
    response_parts.append("📚 SOURCE GATHERER AGENT")
    response_parts.append("=" * 60)
    
    if source_result.get("error"):
        response_parts.append(f"\n❌ Error: {source_result['error']}")
    elif source_result.get("final_response"):
        # Extract key stats from source gatherer response
        source_text = source_result["final_response"]
        response_parts.append(f"\n{source_text}")
    else:
        response_parts.append("\n⚠️ No results returned")
    
    # Domain Scout Results
    response_parts.append("\n" + "=" * 60)
    response_parts.append("🔍 DOMAIN SCOUT AGENT")
    response_parts.append("=" * 60)
    
    if scout_result.get("error"):
        response_parts.append(f"\n❌ Error: {scout_result['error']}")
    elif scout_result.get("final_response"):
        # Extract key stats from domain scout response
        scout_text = scout_result["final_response"]
        response_parts.append(f"\n{scout_text}")
    else:
        response_parts.append("\n⚠️ No results returned")
    
    # Summary
    response_parts.append("\n" + "=" * 60)
    response_parts.append("📈 EXECUTION SUMMARY")
    response_parts.append("=" * 60)
    
    source_status = source_progress.get("status", "unknown")
    scout_status = scout_progress.get("status", "unknown")
    
    response_parts.append(f"\n✅ Source Gatherer: {source_status}")
    response_parts.append(f"✅ Domain Scout: {scout_status}")
    
    if source_status == "completed" and scout_status == "completed":
        response_parts.append("\n🎉 Both agents completed successfully!")
    elif source_status == "error" or scout_status == "error":
        response_parts.append("\n⚠️ Some agents encountered errors")
    else:
        response_parts.append("\n⏳ Execution in progress...")
    
    # Store results in state
    return {
        "final_response": "\n".join(response_parts),
        "source_gatherer_result": source_result,
        "domain_scout_result": scout_result,
        "test_domain": domain,
        "source_status": source_status,
        "scout_status": scout_status,
        "parallel_execution": True
    }
