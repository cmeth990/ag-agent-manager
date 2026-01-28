"""
Source Fetcher Module
Fetches and extracts content from discovered sources.
"""
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import re
from app.security.network import is_url_allowed
from app.security.sanitize import sanitize_content
from app.failure_modes.html_parser import parse_html_with_fallback
from app.failure_modes.paywall import detect_paywall
from app.cost.cache import get_cache, cached

logger = logging.getLogger(__name__)

# Cost tiers for different source types
SOURCE_COST_TIERS = {
    # Free sources
    "free": {
        "openstax": 0.0,
        "khan_academy": 0.0,
        "mit_ocw": 0.0,
        "libretexts": 0.0,
        "wikipedia": 0.0,
        "arxiv": 0.0,
        "openalex": 0.0,
        "government": 0.0,
        "oer": 0.0,
    },
    # Low cost (subscription or one-time)
    "low": {
        "academic_paper": 0.1,  # May require library access
        "textbook": 0.2,  # May require purchase
        "educational_platform": 0.1,  # May require subscription
    },
    # Medium cost
    "medium": {
        "journal_subscription": 0.5,
        "premium_course": 0.4,
    },
    # High cost
    "high": {
        "paywalled_paper": 0.8,
        "proprietary_textbook": 0.9,
        "premium_platform": 0.7,
    }
}


def calculate_source_cost(source: Dict[str, Any]) -> float:
    """
    Calculate cost score for a source (0.0 = free, 1.0 = very expensive).
    
    Args:
        source: Source node dict
    
    Returns:
        Cost score (0.0-1.0)
    """
    props = source.get("properties", {})
    source_type = props.get("type", "unknown")
    url = props.get("url", "")
    domain = props.get("domain", "")
    
    # Check URL domain for known free sources
    if url:
        parsed = urlparse(url)
        domain_lower = parsed.netloc.lower()
        
        # Free domains
        free_domains = [
            "openstax.org", "khanacademy.org", "ocw.mit.edu", "libretexts.org",
            "wikipedia.org", "arxiv.org", "openalex.org", ".gov", ".edu"
        ]
        if any(free_domain in domain_lower for free_domain in free_domains):
            return 0.0
        
        # Check for paywall indicators
        paywall_indicators = ["paywall", "subscription", "purchase", "buy", "premium"]
        if any(indicator in domain_lower for indicator in paywall_indicators):
            return 0.8
    
    # Check source type
    source_type_lower = source_type.lower()
    
    # Free types
    if any(free_type in source_type_lower for free_type in ["openstax", "khan", "ocw", "libretexts", "wikipedia", "arxiv", "oer", "government"]):
        return 0.0
    
    # Low cost types
    if any(low_type in source_type_lower for low_type in ["textbook", "educational_platform"]):
        return 0.2
    
    # Medium cost
    if "subscription" in source_type_lower or "premium" in source_type_lower:
        return 0.5
    
    # High cost
    if "paywall" in source_type_lower or "proprietary" in source_type_lower:
        return 0.8
    
    # Default: assume may have some cost
    return 0.3


def rank_sources_by_priority(
    sources: List[Dict[str, Any]],
    domain_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Rank sources by priority: high confidence & free first, low confidence & costly last.
    
    Priority Formula:
    Priority = (Quality × 0.7) - (Cost × 0.3)
    
    Higher priority = better (high quality, low cost)
    
    Args:
        sources: List of source dicts with quality_score
        domain_name: Optional domain name for context
    
    Returns:
        Ranked list of sources (highest priority first)
    """
    ranked = []
    
    for source in sources:
        # Get quality score (already calculated) - ensure it's a float
        quality_raw = source.get("quality_score", 0.5)
        if isinstance(quality_raw, dict):
            # If quality_score is a dict with 'score' key
            quality = float(quality_raw.get("score", 0.5))
        elif isinstance(quality_raw, (int, float)):
            quality = float(quality_raw)
        else:
            # Try to convert string to float, default to 0.5
            try:
                quality = float(quality_raw) if quality_raw else 0.5
            except (ValueError, TypeError):
                quality = 0.5
        
        # Calculate cost - ensure it's always a float
        cost_raw = calculate_source_cost(source)
        if isinstance(cost_raw, (int, float)):
            cost = float(cost_raw)
        else:
            try:
                cost = float(cost_raw) if cost_raw else 0.3
            except (ValueError, TypeError):
                cost = 0.3  # Default medium cost
        
        source["cost_score"] = cost
        
        # Calculate priority (higher is better)
        # Weight quality more heavily (70%) than cost (30%)
        priority = (quality * 0.7) - (cost * 0.3)
        
        # Boost free sources slightly
        if cost == 0.0:
            priority += 0.1
        
        source["priority_score"] = priority
        source["cost_tier"] = get_cost_tier(cost)
        
        ranked.append(source)
    
    # Sort by priority (descending)
    ranked.sort(key=lambda s: s["priority_score"], reverse=True)
    
    return ranked


def get_cost_tier(cost_score: float) -> str:
    """Get cost tier name from cost score."""
    if cost_score == 0.0:
        return "free"
    elif cost_score < 0.3:
        return "low"
    elif cost_score < 0.6:
        return "medium"
    else:
        return "high"


@cached("fetched_doc", ttl_seconds=86400, key_func=lambda source, max_length=10000: (source.get("url"), max_length))
async def fetch_source_content(
    source: Dict[str, Any],
    max_length: int = 10000
) -> Dict[str, Any]:
    """
    Fetch actual content from a source URL.
    
    Args:
        source: Source node dict
        max_length: Maximum content length to fetch
    
    Returns:
        Dict with:
        - content: Extracted text content
        - metadata: Fetch metadata (status, length, etc.)
        - accessible: Whether source is accessible
    """
    props = source.get("properties", {})
    url = props.get("url")
    
    if not url:
        return {
            "content": None,
            "metadata": {"error": "No URL provided"},
            "accessible": False
        }
    
    # Network egress control: only fetch from allowlisted domains
    if not is_url_allowed(url):
        return {
            "content": None,
            "metadata": {"error": "URL not in network allowlist", "url": url},
            "accessible": False
        }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Set headers to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; KnowledgeGraphBot/1.0; +https://example.com/bot)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Paywall detection: check if content is behind paywall
                    paywall_check = detect_paywall(content, url=url)
                    if paywall_check.get("is_paywall"):
                        logger.warning(f"Paywall detected for {url}: {paywall_check.get('message')}")
                        return {
                            "content": None,
                            "metadata": {
                                "status": response.status,
                                "error": "Paywall detected",
                                "url": url,
                                "paywall_confidence": paywall_check.get("confidence", 0.0),
                            },
                            "accessible": False
                        }
                    
                    # HTML parser with fallback: graceful degradation when parser breaks
                    parsed = parse_html_with_fallback(content)
                    text_content = parsed.get("content", "")
                    
                    # Content sanitization: strip scripts, hidden text, dangerous URIs
                    # (parse_html_with_fallback already does basic sanitization, but do full sanitize)
                    text_content = sanitize_content(
                        text_content,
                        content_type="text",  # Already extracted text
                        max_length=max_length,
                    )
                    
                    if len(text_content) > max_length:
                        text_content = text_content[:max_length] + "..."
                    
                    return {
                        "content": text_content,
                        "metadata": {
                            "status": response.status,
                            "content_length": len(text_content),
                            "url": url,
                            "content_type": response.headers.get("Content-Type", "unknown")
                        },
                        "accessible": True
                    }
                else:
                    return {
                        "content": None,
                        "metadata": {
                            "status": response.status,
                            "error": f"HTTP {response.status}",
                            "url": url
                        },
                        "accessible": False
                    }
    
    except asyncio.TimeoutError:
        return {
            "content": None,
            "metadata": {"error": "Request timeout", "url": url},
            "accessible": False
        }
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
        return {
            "content": None,
            "metadata": {"error": str(e), "url": url},
            "accessible": False
        }


def extract_text_from_html(html: str) -> str:
    """
    Extract text content from HTML (simple implementation).
    
    In production, use a proper HTML parser like BeautifulSoup.
    """
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


async def gather_domain_content_prioritized(
    sources: List[Dict[str, Any]],
    domain_name: str,
    max_sources: int = 10,
    min_priority: float = 0.0
) -> Dict[str, Any]:
    """
    Gather content from sources in priority order (high confidence & free first).
    
    Args:
        sources: List of ranked sources
        domain_name: Domain name for context
        max_sources: Maximum number of sources to fetch
        min_priority: Minimum priority score to fetch
    
    Returns:
        Dict with:
        - fetched_sources: Sources with fetched content
        - statistics: Fetch statistics
        - recommendations: Recommendations
    """
    # Filter by minimum priority
    eligible_sources = [s for s in sources if s.get("priority_score", 0) >= min_priority]
    
    # Take top sources
    sources_to_fetch = eligible_sources[:max_sources]
    
    logger.info(f"Fetching content from {len(sources_to_fetch)} sources for {domain_name}")
    
    # Fetch content in parallel (with rate limiting)
    fetched_sources = []
    fetch_tasks = []
    
    for source in sources_to_fetch:
        task = fetch_source_content(source)
        fetch_tasks.append((source, task))
    
    # Execute with concurrency limit
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
    
    async def fetch_with_limit(source, task):
        async with semaphore:
            result = await task
            source["fetched_content"] = result
            return source
    
    fetch_results = await asyncio.gather(
        *[fetch_with_limit(source, task) for source, task in fetch_tasks],
        return_exceptions=True
    )
    
    # Process results
    successful_fetches = 0
    failed_fetches = 0
    total_content_length = 0
    
    for result in fetch_results:
        if isinstance(result, Exception):
            logger.error(f"Fetch error: {result}")
            failed_fetches += 1
            continue
        
        source = result
        fetched = source.get("fetched_content", {})
        
        if fetched.get("accessible"):
            successful_fetches += 1
            content = fetched.get("content", "")
            total_content_length += len(content) if content else 0
            fetched_sources.append(source)
        else:
            failed_fetches += 1
    
    # Calculate statistics
    free_sources = [s for s in fetched_sources if s.get("cost_score", 1.0) == 0.0]
    paid_sources = [s for s in fetched_sources if s.get("cost_score", 0.0) > 0.0]
    
    avg_quality = sum(s.get("quality_score", 0) for s in fetched_sources) / len(fetched_sources) if fetched_sources else 0
    avg_priority = sum(s.get("priority_score", 0) for s in fetched_sources) / len(fetched_sources) if fetched_sources else 0
    
    statistics = {
        "total_sources": len(sources_to_fetch),
        "successful_fetches": successful_fetches,
        "failed_fetches": failed_fetches,
        "free_sources": len(free_sources),
        "paid_sources": len(paid_sources),
        "total_content_length": total_content_length,
        "average_quality": avg_quality,
        "average_priority": avg_priority
    }
    
    # Generate recommendations
    recommendations = []
    if len(free_sources) < len(fetched_sources) * 0.5:
        recommendations.append("Consider prioritizing more free sources for cost efficiency")
    
    if avg_quality < 0.7:
        recommendations.append("Average source quality is below optimal. Consider higher quality sources.")
    
    if failed_fetches > successful_fetches:
        recommendations.append("Many sources failed to fetch. Check URLs and accessibility.")
    
    return {
        "fetched_sources": fetched_sources,
        "statistics": statistics,
        "recommendations": recommendations,
        "domain_name": domain_name
    }
