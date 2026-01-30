"""
Autonomous KG expansion: intelligently build the graph and report progress.

Runs discovery across multiple domains (from taxonomy or config) and sends
the user an update instead of requiring "gather sources for X" one by one.
"""
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional

from app.graph.state import AgentState
from app.kg.source_discovery import discover_sources_for_domain

logger = logging.getLogger(__name__)

DEFAULT_MAX_DOMAINS = 5
DEFAULT_MAX_SOURCES_PER_DOMAIN = 10


def get_domains_to_expand(max_domains: Optional[int] = None) -> List[str]:
    """
    Get domains to expand in this run.
    Uses EXPANSION_DOMAINS (comma-separated) if set; otherwise samples from taxonomy.
    """
    max_domains = max_domains or int(os.getenv("EXPANSION_MAX_DOMAINS", str(DEFAULT_MAX_DOMAINS)))
    explicit = os.getenv("EXPANSION_DOMAINS", "").strip()
    if explicit:
        domains = [d.strip() for d in explicit.split(",") if d.strip()][:max_domains]
        logger.info(f"Expansion domains from config: {domains}")
        return domains

    try:
        from app.kg.domains import DOMAIN_TAXONOMY
    except ImportError:
        logger.warning("DOMAIN_TAXONOMY not available, using fallback domains")
        return ["Algebra I", "Machine Learning", "Biology"][:max_domains]

    # Sample across categories (one domain per category, then fill)
    domains: List[str] = []
    categories = list(DOMAIN_TAXONOMY.keys())
    round_idx = 0
    while len(domains) < max_domains:
        added = 0
        for cat in categories:
            if len(domains) >= max_domains:
                break
            doms = list(DOMAIN_TAXONOMY[cat].keys())
            if round_idx < len(doms):
                name = doms[round_idx]
                if name not in domains:
                    domains.append(name)
                    added += 1
        if added == 0:
            break
        round_idx += 1

    domains = domains[:max_domains]
    logger.info(f"Expansion domains from taxonomy: {domains}")
    return domains


async def run_expansion_cycle(
    max_domains: Optional[int] = None,
    max_sources_per_domain: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run one expansion cycle: discover sources for multiple domains, aggregate stats.
    Returns dict with domains_explored, total_sources, with_primary_ids, free_sources,
    by_domain, and update_message (text to send to user).
    """
    max_domains = max_domains or int(os.getenv("EXPANSION_MAX_DOMAINS", str(DEFAULT_MAX_DOMAINS)))
    max_sources = max_sources_per_domain or int(
        os.getenv("EXPANSION_MAX_SOURCES_PER_DOMAIN", str(DEFAULT_MAX_SOURCES_PER_DOMAIN))
    )
    domains = get_domains_to_expand(max_domains=max_domains)

    by_domain: Dict[str, Dict[str, Any]] = {}
    all_sources: List[Dict[str, Any]] = []
    total_with_ids = 0

    for domain in domains:
        try:
            result = await discover_sources_for_domain(
                domain_name=domain,
                max_sources=max_sources,
                min_quality=0.5,
            )
            sources = result.get("sources") or []
            stats = result.get("statistics") or {}
            by_domain[domain] = {
                "sources": sources,
                "total": len(sources),
                "statistics": stats,
            }
            all_sources.extend(sources)
            for s in sources:
                ids = (s.get("properties") or {}).get("identifiers") or {}
                if ids:
                    total_with_ids += 1
        except Exception as e:
            logger.warning(f"Expansion failed for domain {domain}: {e}")
            by_domain[domain] = {"sources": [], "total": 0, "statistics": {}, "error": str(e)}

    total = len(all_sources)
    free = sum(1 for s in all_sources if s.get("cost_score", 1.0) == 0.0)
    paid = total - free

    # Build update message for user
    lines = [
        "📈 **KG expansion run**",
        "",
        f"**Domains explored:** {', '.join(domains)}",
        f"**Sources discovered:** {total} (free: {free}, paid: {paid})",
        f"**With primary IDs (DOI/arXiv/URL):** {total_with_ids}",
        "",
    ]
    for domain, data in by_domain.items():
        n = data.get("total", 0)
        err = data.get("error")
        if err:
            lines.append(f"• {domain}: error — {err[:40]}")
        else:
            lines.append(f"• {domain}: {n} sources")
    lines.extend([
        "",
        "💡 **Next:** Run `/expand` again for more domains, or `/graph` for progress. Use `/fetch content for <domain>` then `/ingest` to add content.",
    ])

    update_message = "\n".join(lines)
    return {
        "domains_explored": domains,
        "total_sources": total,
        "with_primary_ids": total_with_ids,
        "free_sources": free,
        "paid_sources": paid,
        "by_domain": by_domain,
        "all_sources": all_sources,
        "update_message": update_message,
    }


async def expansion_node(state: AgentState) -> Dict[str, Any]:
    """
    Autonomous expansion node: run one expansion cycle and return update to user.
    """
    chat_id = state.get("chat_id")
    logger.info(f"Autonomous expansion run for chat {chat_id}")

    try:
        result = await run_expansion_cycle()
        return {
            "final_response": result["update_message"],
            "working_notes": {
                **(state.get("working_notes") or {}),
                "expansion_result": {
                    "domains_explored": result["domains_explored"],
                    "total_sources": result["total_sources"],
                    "with_primary_ids": result["with_primary_ids"],
                    "by_domain": {
                        d: {"total": data["total"]}
                        for d, data in result["by_domain"].items()
                    },
                },
            },
        }
    except Exception as e:
        logger.exception(f"Expansion cycle failed: {e}")
        return {
            "final_response": f"❌ Expansion run failed: {str(e)[:200]}. Try again or run `/gather sources for <domain>` for a single domain.",
            "error": str(e)[:500],
        }
