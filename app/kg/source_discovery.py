"""
Source Discovery Module
Discovers sources from multiple providers for a given domain.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.kg.domains import get_domain_by_name
from app.kg.scoring import calculate_source_quality, get_domain_quality_threshold

logger = logging.getLogger(__name__)

# Source discovery providers
SOURCE_PROVIDERS = {
    "academic": {
        "semantic_scholar": {"enabled": True, "priority": 1},
        "arxiv": {"enabled": True, "priority": 2},
        "openalex": {"enabled": True, "priority": 3},
        "crossref": {"enabled": False, "priority": 4},  # Requires API key
    },
    "educational": {
        "openstax": {"enabled": True, "priority": 1},
        "khan_academy": {"enabled": True, "priority": 2},
        "mit_ocw": {"enabled": True, "priority": 3},
        "libretexts": {"enabled": True, "priority": 4},
    },
    "general": {
        "web_search": {"enabled": True, "priority": 1},
        "wikipedia": {"enabled": True, "priority": 2},
    }
}


async def discover_sources_for_domain(
    domain_name: str,
    max_sources: int = 20,
    min_quality: Optional[float] = None,
    source_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Discover sources for a specific domain.
    
    Args:
        domain_name: Name of the domain
        max_sources: Maximum number of sources to return
        min_quality: Minimum quality score (uses domain threshold if None)
        source_types: List of source types to search (None = all)
    
    Returns:
        Dict with:
        - sources: List of discovered sources with quality scores
        - domain_info: Domain metadata
        - statistics: Discovery statistics
        - recommendations: Recommendations for improvement
    """
    logger.info(f"Discovering sources for domain: {domain_name}")
    
    # Get domain metadata
    domain_info = get_domain_by_name(domain_name)
    if not domain_info:
        logger.warning(f"Domain {domain_name} not found in taxonomy")
        domain_info = {"domain_name": domain_name, "category_key": None}
    
    # Get quality threshold for domain
    if min_quality is None:
        thresholds = get_domain_quality_threshold(domain_name)
        min_quality = thresholds.get("min_source_quality", 0.55)
    
    # Generate search queries for domain
    search_queries = generate_search_queries(domain_name, domain_info)
    
    # Discover sources from all providers
    all_sources = []
    
    # Academic sources
    if not source_types or "academic" in source_types:
        academic_sources = await discover_academic_sources(search_queries, domain_name)
        all_sources.extend(academic_sources)
    
    # Educational sources
    if not source_types or "educational" in source_types:
        educational_sources = await discover_educational_sources(search_queries, domain_name)
        all_sources.extend(educational_sources)
    
    # General sources
    if not source_types or "general" in source_types:
        general_sources = await discover_general_sources(search_queries, domain_name)
        all_sources.extend(general_sources)
    
    # Evaluate and rank sources
    evaluated_sources = []
    for source in all_sources:
        quality_result = calculate_source_quality(source, domain_name, domain_info)
        source["quality_score"] = quality_result["quality_score"]
        source["quality_components"] = quality_result["components"]
        source["domain_relevance"] = quality_result["domain_relevance"]
        source["recommendations"] = quality_result["recommendations"]
        
        # Only include if meets quality threshold
        if source["quality_score"] >= min_quality:
            evaluated_sources.append(source)
    
    # Rank by priority (quality and cost)
    from app.kg.source_fetcher import rank_sources_by_priority
    ranked_sources = rank_sources_by_priority(evaluated_sources, domain_name)
    
    # Take top sources
    top_sources = ranked_sources[:max_sources]
    
    # Calculate statistics
    free_sources = [s for s in top_sources if s.get("cost_score", 1.0) == 0.0]
    paid_sources = [s for s in top_sources if s.get("cost_score", 0.0) > 0.0]
    
    stats = {
        "total_discovered": len(all_sources),
        "meets_quality_threshold": len(evaluated_sources),
        "returned": len(top_sources),
        "average_quality": sum(s["quality_score"] for s in top_sources) / len(top_sources) if top_sources else 0,
        "average_priority": sum(s.get("priority_score", 0) for s in top_sources) / len(top_sources) if top_sources else 0,
        "free_sources": len(free_sources),
        "paid_sources": len(paid_sources),
        "source_types": {}
    }
    
    # Count by type
    for source in top_sources:
        source_type = source.get("properties", {}).get("type", "unknown")
        stats["source_types"][source_type] = stats["source_types"].get(source_type, 0) + 1
    
    # Generate recommendations
    recommendations = []
    if len(top_sources) < thresholds.get("min_sources", 2):
        recommendations.append(f"Only {len(top_sources)} sources found. Need at least {thresholds.get('min_sources', 2)} for {domain_info.get('difficulty', 'intermediate')} level.")
    
    if stats["average_quality"] < min_quality:
        recommendations.append(f"Average source quality ({stats['average_quality']:.2f}) below threshold ({min_quality:.2f}). Consider expanding search.")
    
    # Check diversity
    unique_types = len(stats["source_types"])
    if unique_types < 2:
        recommendations.append("Low source diversity. Seek different source types.")
    
    return {
        "sources": top_sources,
        "domain_info": domain_info,
        "statistics": stats,
        "recommendations": recommendations,
        "quality_threshold": min_quality
    }


def generate_search_queries(domain_name: str, domain_info: Dict[str, Any]) -> List[str]:
    """
    Generate search queries for a domain.
    
    Returns:
        List of search query strings
    """
    queries = [domain_name]
    
    # Add variations
    if " " in domain_name:
        # Split multi-word domains
        words = domain_name.split()
        queries.append(" ".join(words[:2]))  # First two words
        queries.append(words[0])  # First word only
    
    # Add category-based queries
    category = domain_info.get("category_key")
    if category:
        queries.append(f"{domain_name} {category}")
    
    # Add difficulty/gradeband context
    difficulty = domain_info.get("difficulty")
    gradebands = domain_info.get("gradebands", [])
    if gradebands:
        queries.append(f"{domain_name} {gradebands[0]}")
    
    return list(set(queries))  # Remove duplicates


async def discover_academic_sources(queries: List[str], domain_name: str) -> List[Dict[str, Any]]:
    """
    Discover academic sources (papers, books, journals).
    
    Uses real APIs:
    - Semantic Scholar API
    - arXiv API
    - OpenAlex API
    """
    sources = []
    
    from app.kg.api_clients import search_semantic_scholar, search_arxiv, search_openalex
    
    # Limit queries to avoid rate limits
    for query in queries[:2]:
        # Search Semantic Scholar
        if SOURCE_PROVIDERS["academic"]["semantic_scholar"]["enabled"]:
            try:
                s2_sources = await search_semantic_scholar(query, limit=5)
                for source in s2_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(s2_sources)
                await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"Semantic Scholar search failed: {e}")
        
        # Search arXiv
        if SOURCE_PROVIDERS["academic"]["arxiv"]["enabled"]:
            try:
                arxiv_sources = await search_arxiv(query, limit=5)
                for source in arxiv_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(arxiv_sources)
                await asyncio.sleep(1.0)  # Rate limiting (1 req per 3 sec)
            except Exception as e:
                logger.warning(f"arXiv search failed: {e}")
        
        # Search OpenAlex
        if SOURCE_PROVIDERS["academic"]["openalex"]["enabled"]:
            try:
                oa_sources = await search_openalex(query, limit=5)
                for source in oa_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(oa_sources)
                await asyncio.sleep(0.2)  # Rate limiting
            except Exception as e:
                logger.warning(f"OpenAlex search failed: {e}")
    
    logger.info(f"Discovered {len(sources)} academic sources for {domain_name}")
    return sources


async def discover_educational_sources(queries: List[str], domain_name: str) -> List[Dict[str, Any]]:
    """
    Discover educational sources (OER, courses, textbooks).
    
    Uses real APIs where available:
    - OpenStax (web search)
    - Khan Academy (URL construction)
    - MIT OCW (URL construction)
    """
    sources = []
    
    from app.kg.api_clients import search_openstax, search_khan_academy, search_mit_ocw
    
    for query in queries[:2]:  # Limit queries
        # Search OpenStax
        if SOURCE_PROVIDERS["educational"]["openstax"]["enabled"]:
            try:
                openstax_sources = await search_openstax(query, limit=3)
                for source in openstax_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(openstax_sources)
            except Exception as e:
                logger.warning(f"OpenStax search failed: {e}")
        
        # Search Khan Academy
        if SOURCE_PROVIDERS["educational"]["khan_academy"]["enabled"]:
            try:
                khan_sources = await search_khan_academy(query, limit=3)
                for source in khan_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(khan_sources)
            except Exception as e:
                logger.warning(f"Khan Academy search failed: {e}")
        
        # Search MIT OCW
        if SOURCE_PROVIDERS["educational"]["mit_ocw"]["enabled"]:
            try:
                mit_sources = await search_mit_ocw(query, limit=3)
                for source in mit_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(mit_sources)
            except Exception as e:
                logger.warning(f"MIT OCW search failed: {e}")
    
    logger.info(f"Discovered {len(sources)} educational sources for {domain_name}")
    return sources


async def discover_general_sources(queries: List[str], domain_name: str) -> List[Dict[str, Any]]:
    """
    Discover general sources (web, Wikipedia, etc.).
    
    Uses real APIs:
    - Wikipedia REST API
    """
    sources = []
    
    from app.kg.api_clients import search_wikipedia
    
    for query in queries[:1]:  # Limit queries
        # Search Wikipedia
        if SOURCE_PROVIDERS["general"]["wikipedia"]["enabled"]:
            try:
                wiki_sources = await search_wikipedia(query, limit=3)
                for source in wiki_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(wiki_sources)
            except Exception as e:
                logger.warning(f"Wikipedia search failed: {e}")
    
    logger.info(f"Discovered {len(sources)} general sources for {domain_name}")
    return sources


# API client functions moved to app.kg.api_clients module
# Import them when needed:
# from app.kg.api_clients import (
#     search_semantic_scholar,
#     search_arxiv,
#     search_openalex,
#     search_wikipedia,
#     search_openstax,
#     search_khan_academy,
#     search_mit_ocw
# )
