"""
Source Quality and Claim Confidence Scoring Formulas

This module provides formulas to:
1. Evaluate source quality for each domain
2. Calculate claim confidence based on multiple sources
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from app.kg.domains import get_domain_by_name

logger = logging.getLogger(__name__)

# ============================================================================
# SOURCE QUALITY SCORING
# ============================================================================

# Base trust scores by source type
SOURCE_TYPE_BASE_SCORES = {
    # Academic sources (highest)
    "peer_reviewed_journal": 0.95,
    "academic_paper": 0.90,
    "preprint": 0.70,
    "academic_book": 0.95,
    "textbook": 0.95,
    "textbook_chapter": 0.90,
    "dissertation": 0.80,
    "conference_proceedings": 0.85,
    
    # Educational sources
    "university_course": 0.90,
    "educational_platform": 0.80,
    "oer": 0.75,
    "video_course": 0.75,
    "tutorial": 0.70,
    
    # Expert sources
    "expert_opinion": 0.80,
    "government_report": 0.85,
    "ngo_report": 0.75,
    "industry_standard": 0.80,
    
    # General sources
    "website": 0.50,
    "blog": 0.40,
    "news_article": 0.60,
    "encyclopedia": 0.70,
    "documentation": 0.65,
    
    # Default
    "unknown": 0.50
}

# Domain-specific recency requirements (years)
# Some domains require recent sources, others value historical sources
DOMAIN_RECENCY_WEIGHTS = {
    # Fast-moving domains (require recent sources)
    "Computer Science": {"optimal_age": 3, "max_age": 10, "weight": 0.20},
    "Machine Learning": {"optimal_age": 2, "max_age": 5, "weight": 0.25},
    "Artificial Intelligence": {"optimal_age": 2, "max_age": 5, "weight": 0.25},
    "Data Science": {"optimal_age": 3, "max_age": 8, "weight": 0.20},
    "Cybersecurity": {"optimal_age": 2, "max_age": 5, "weight": 0.25},
    "Web Development": {"optimal_age": 2, "max_age": 7, "weight": 0.20},
    "Mobile Development": {"optimal_age": 2, "max_age": 7, "weight": 0.20},
    
    # Medium-moving domains
    "Medicine": {"optimal_age": 5, "max_age": 15, "weight": 0.15},
    "Public Health": {"optimal_age": 5, "max_age": 15, "weight": 0.15},
    "Psychology": {"optimal_age": 7, "max_age": 20, "weight": 0.10},
    "Economics": {"optimal_age": 10, "max_age": 30, "weight": 0.10},
    
    # Stable domains (historical sources valuable)
    "Mathematics": {"optimal_age": 20, "max_age": 100, "weight": 0.05},
    "Philosophy": {"optimal_age": 50, "max_age": 200, "weight": 0.05},
    "History": {"optimal_age": 30, "max_age": 200, "weight": 0.05},
    "Classical Literature": {"optimal_age": 50, "max_age": 500, "weight": 0.05},
    
    # Default
    "default": {"optimal_age": 10, "max_age": 30, "weight": 0.10}
}

# Impact factor normalization (typical range: 0-50, some journals >100)
IMPACT_FACTOR_MAX = 100.0


def calculate_source_quality(
    source: Dict[str, Any],
    domain_name: Optional[str] = None,
    domain_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive source quality score for a specific domain.
    
    Formula:
    Q_source = (Q_type * w_type) + (Q_credibility * w_cred) + (Q_relevance * w_rel) + 
               (Q_recency * w_rec) + (Q_impact * w_impact) + (Q_verification * w_ver)
    
    Where:
    - Q_type: Base score from source type
    - Q_credibility: Trust score, peer review, citations
    - Q_relevance: Domain relevance (how well source matches domain)
    - Q_recency: Age appropriateness for domain
    - Q_impact: Impact factor, journal prestige
    - Q_verification: Verification status, DOI, etc.
    
    Args:
        source: Source node dict with properties
        domain_name: Name of the domain this source is for
        domain_metadata: Optional domain metadata (gradebands, difficulty, etc.)
    
    Returns:
        Dict with:
        - quality_score: Overall quality (0-1)
        - components: Breakdown of components
        - domain_relevance: How relevant to domain (0-1)
        - recommendations: List of improvement suggestions
    """
    props = source.get("properties", {})
    
    # Component 1: Source Type Base Score
    source_type = props.get("type", "unknown")
    q_type = SOURCE_TYPE_BASE_SCORES.get(source_type, SOURCE_TYPE_BASE_SCORES["unknown"])
    w_type = 0.25
    
    # Component 2: Credibility (trust score, peer review, citations)
    trust_score = props.get("trustScore", 0.5)
    peer_reviewed = props.get("peerReviewed", False) or "peer" in source_type.lower()
    citation_count = props.get("citationCount", 0) or props.get("citations", 0)
    
    # Normalize citation count (log scale: 0-1000+ citations)
    if citation_count > 0:
        citation_score = min(1.0, 0.5 + (0.5 * (1 - 1 / (1 + citation_count / 100))))
    else:
        citation_score = 0.5
    
    q_credibility = (
        trust_score * 0.5 +
        (1.0 if peer_reviewed else 0.5) * 0.3 +
        citation_score * 0.2
    )
    w_cred = 0.25
    
    # Component 3: Domain Relevance
    q_relevance = calculate_domain_relevance(source, domain_name, domain_metadata)
    w_rel = 0.20
    
    # Component 4: Recency (domain-dependent)
    q_recency = calculate_recency_score(source, domain_name)
    w_rec = 0.15
    
    # Component 5: Impact Factor
    impact_factor = props.get("impactFactor")
    if impact_factor:
        q_impact = min(1.0, impact_factor / IMPACT_FACTOR_MAX)
    else:
        q_impact = 0.5  # Neutral if unknown
    w_impact = 0.10
    
    # Component 6: Verification
    has_doi = bool(props.get("doi"))
    has_url = bool(props.get("url"))
    has_authors = bool(props.get("authors"))
    verified = props.get("verified", False)
    
    q_verification = (
        (1.0 if has_doi else 0.5) * 0.4 +
        (1.0 if has_url else 0.3) * 0.2 +
        (1.0 if has_authors else 0.5) * 0.2 +
        (1.0 if verified else 0.5) * 0.2
    )
    w_ver = 0.05
    
    # Calculate weighted sum
    quality_score = (
        q_type * w_type +
        q_credibility * w_cred +
        q_relevance * w_rel +
        q_recency * w_rec +
        q_impact * w_impact +
        q_verification * w_ver
    )
    
    # Generate recommendations
    recommendations = []
    if q_type < 0.7:
        recommendations.append(f"Consider using peer-reviewed sources (current: {source_type})")
    if q_credibility < 0.6:
        recommendations.append("Source credibility could be improved (add citations, peer review)")
    if q_relevance < 0.7:
        recommendations.append(f"Source may not be highly relevant to domain: {domain_name}")
    if q_recency < 0.5 and domain_name:
        recency_info = DOMAIN_RECENCY_WEIGHTS.get(domain_name, DOMAIN_RECENCY_WEIGHTS["default"])
        recommendations.append(f"Source may be outdated for {domain_name} (optimal age: {recency_info['optimal_age']} years)")
    if not has_doi and source_type in ["peer_reviewed_journal", "academic_paper"]:
        recommendations.append("Academic sources should have DOI for verification")
    
    return {
        "quality_score": round(quality_score, 3),
        "components": {
            "type_score": round(q_type, 3),
            "credibility_score": round(q_credibility, 3),
            "relevance_score": round(q_relevance, 3),
            "recency_score": round(q_recency, 3),
            "impact_score": round(q_impact, 3),
            "verification_score": round(q_verification, 3)
        },
        "weights": {
            "type": w_type,
            "credibility": w_cred,
            "relevance": w_rel,
            "recency": w_rec,
            "impact": w_impact,
            "verification": w_ver
        },
        "domain_relevance": round(q_relevance, 3),
        "recommendations": recommendations
    }


def calculate_domain_relevance(
    source: Dict[str, Any],
    domain_name: Optional[str],
    domain_metadata: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate how relevant a source is to a specific domain.
    
    Factors:
    - Domain mentioned in title/description
    - Source domain matches target domain
    - Gradeband/difficulty alignment
    - Category alignment
    
    Returns:
        Relevance score (0-1)
    """
    if not domain_name:
        return 0.5  # Neutral if no domain specified
    
    props = source.get("properties", {})
    title = (props.get("title") or "").lower()
    description = (props.get("description") or "").lower()
    source_domain = props.get("domain", "").lower()
    domain_lower = domain_name.lower()
    
    # Check if domain is mentioned
    domain_mentioned = (
        domain_lower in title or
        domain_lower in description or
        domain_lower in source_domain
    )
    
    # Exact domain match
    exact_match = source_domain == domain_lower
    
    # Category match (if domain metadata available)
    category_match = False
    if domain_metadata:
        source_category = props.get("category")
        domain_category = domain_metadata.get("category_key")
        if source_category and domain_category and source_category == domain_category:
            category_match = True
    
    # Calculate relevance
    if exact_match:
        relevance = 1.0
    elif domain_mentioned:
        relevance = 0.8
    elif category_match:
        relevance = 0.7
    else:
        # Check for partial matches (e.g., "machine learning" in "AI/ML")
        partial_match = any(
            word in title or word in description
            for word in domain_lower.split()
            if len(word) > 3
        )
        relevance = 0.5 if partial_match else 0.3
    
    return relevance


def calculate_recency_score(source: Dict[str, Any], domain_name: Optional[str]) -> float:
    """
    Calculate recency score based on domain requirements.
    
    Some domains need recent sources (CS, ML), others value historical (Math, Philosophy).
    
    Returns:
        Recency score (0-1)
    """
    props = source.get("properties", {})
    year = props.get("year")
    
    if not year:
        return 0.5  # Neutral if unknown
    
    current_year = datetime.now().year
    age = current_year - year
    
    # Get domain-specific recency requirements
    if domain_name:
        recency_config = DOMAIN_RECENCY_WEIGHTS.get(domain_name, DOMAIN_RECENCY_WEIGHTS["default"])
    else:
        recency_config = DOMAIN_RECENCY_WEIGHTS["default"]
    
    optimal_age = recency_config["optimal_age"]
    max_age = recency_config["max_age"]
    
    # Calculate score: optimal at optimal_age, decreases as distance increases
    if age <= optimal_age:
        # Recent sources: score based on how close to optimal
        score = 1.0 - (0.3 * (age / optimal_age))
    elif age <= max_age:
        # Acceptable age: linear decay
        score = 0.7 * (1 - (age - optimal_age) / (max_age - optimal_age))
    else:
        # Too old: significant penalty
        score = 0.2 * (max_age / age)
    
    return max(0.0, min(1.0, score))


# ============================================================================
# CLAIM CONFIDENCE SCORING
# ============================================================================

def calculate_claim_confidence(
    claim: Dict[str, Any],
    sources: List[Dict[str, Any]],
    evidence_list: List[Dict[str, Any]],
    domain_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate confidence score for a claim based on multiple sources.
    
    Formula:
    C_claim = (C_source_quality * w_sq) + (C_agreement * w_agr) + (C_diversity * w_div) +
              (C_evidence_strength * w_ev) + (C_independence * w_ind) - (C_conflicts * w_conf)
    
    Where:
    - C_source_quality: Weighted average of source quality scores
    - C_agreement: How well sources agree on the claim
    - C_diversity: Diversity of source types, authors, methods
    - C_evidence_strength: Strength of supporting evidence
    - C_independence: Independence of sources (different authors, venues)
    - C_conflicts: Penalty for conflicting sources/evidence
    
    Args:
        claim: Claim node dict
        sources: List of source nodes supporting the claim
        evidence_list: List of evidence nodes supporting the claim
        domain_name: Domain this claim belongs to
    
    Returns:
        Dict with:
        - confidence_score: Overall confidence (0-1)
        - components: Breakdown of components
        - source_count: Number of sources
        - evidence_count: Number of evidence items
        - recommendations: List of improvement suggestions
    """
    if not sources and not evidence_list:
        return {
            "confidence_score": 0.0,
            "components": {},
            "source_count": 0,
            "evidence_count": 0,
            "recommendations": ["No sources or evidence provided for claim"]
        }
    
    # Component 1: Source Quality (weighted by source quality)
    source_qualities = []
    for source in sources:
        quality_result = calculate_source_quality(source, domain_name)
        source_qualities.append(quality_result["quality_score"])
    
    if source_qualities:
        # Weighted average (higher quality sources count more)
        weighted_sum = sum(q ** 2 for q in source_qualities)  # Square to emphasize high quality
        weight_sum = sum(q for q in source_qualities)
        c_source_quality = weighted_sum / weight_sum if weight_sum > 0 else 0.5
    else:
        c_source_quality = 0.3  # Low if no sources
    w_sq = 0.30
    
    # Component 2: Agreement (how well sources agree)
    c_agreement = calculate_agreement_score(sources, evidence_list)
    w_agr = 0.20
    
    # Component 3: Diversity (different types, authors, methods)
    c_diversity = calculate_diversity_score(sources, evidence_list)
    w_div = 0.15
    
    # Component 4: Evidence Strength
    c_evidence_strength = calculate_evidence_strength(evidence_list)
    w_ev = 0.20
    
    # Component 5: Independence (different authors, venues, methods)
    c_independence = calculate_independence_score(sources, evidence_list)
    w_ind = 0.10
    
    # Component 6: Conflicts (penalty for contradictions)
    c_conflicts = calculate_conflict_penalty(claim, sources, evidence_list)
    w_conf = 0.05
    
    # Calculate weighted sum
    confidence_score = (
        c_source_quality * w_sq +
        c_agreement * w_agr +
        c_diversity * w_div +
        c_evidence_strength * w_ev +
        c_independence * w_ind -
        c_conflicts * w_conf
    )
    
    # Normalize to 0-1
    confidence_score = max(0.0, min(1.0, confidence_score))
    
    # Generate recommendations
    recommendations = []
    if len(sources) < 2:
        recommendations.append("At least 2 independent sources recommended")
    if c_source_quality < 0.6:
        recommendations.append("Source quality is low - seek higher quality sources")
    if c_agreement < 0.7:
        recommendations.append("Sources show low agreement - verify claim accuracy")
    if c_diversity < 0.6:
        recommendations.append("Low source diversity - seek different types/authors")
    if c_evidence_strength < 0.5:
        recommendations.append("Evidence strength is weak - need stronger evidence")
    if c_conflicts > 0.3:
        recommendations.append("Conflicting evidence detected - investigate contradictions")
    
    return {
        "confidence_score": round(confidence_score, 3),
        "components": {
            "source_quality": round(c_source_quality, 3),
            "agreement": round(c_agreement, 3),
            "diversity": round(c_diversity, 3),
            "evidence_strength": round(c_evidence_strength, 3),
            "independence": round(c_independence, 3),
            "conflicts": round(c_conflicts, 3)
        },
        "weights": {
            "source_quality": w_sq,
            "agreement": w_agr,
            "diversity": w_div,
            "evidence_strength": w_ev,
            "independence": w_ind,
            "conflicts": w_conf
        },
        "source_count": len(sources),
        "evidence_count": len(evidence_list),
        "source_qualities": [round(q, 3) for q in source_qualities],
        "recommendations": recommendations
    }


def calculate_agreement_score(
    sources: List[Dict[str, Any]],
    evidence_list: List[Dict[str, Any]]
) -> float:
    """
    Calculate how well sources agree on the claim.
    
    Factors:
    - Similarity of claims from different sources
    - Consistency of evidence
    - Lack of contradictions
    
    Returns:
        Agreement score (0-1)
    """
    if len(sources) < 2:
        return 0.5  # Neutral if only one source
    
    # For now, assume high agreement if no explicit contradictions
    # In a full implementation, would compare claim texts, evidence content
    
    # Check for explicit contradictions in evidence
    has_refutations = any(
        ev.get("properties", {}).get("type") == "refutation"
        for ev in evidence_list
    )
    
    if has_refutations:
        return 0.4  # Lower if refutations exist
    
    # More sources = higher agreement (if no contradictions)
    # Diminishing returns: 2 sources = 0.7, 3 = 0.8, 4+ = 0.9
    base_agreement = min(0.9, 0.5 + (len(sources) - 1) * 0.15)
    
    return base_agreement


def calculate_diversity_score(
    sources: List[Dict[str, Any]],
    evidence_list: List[Dict[str, Any]]
) -> float:
    """
    Calculate diversity of sources and evidence.
    
    Factors:
    - Different source types
    - Different authors
    - Different methods
    - Different venues
    
    Returns:
        Diversity score (0-1)
    """
    if len(sources) < 2:
        return 0.3  # Low diversity with single source
    
    # Count unique source types
    source_types = set()
    authors = set()
    methods = set()
    
    for source in sources:
        props = source.get("properties", {})
        source_types.add(props.get("type", "unknown"))
        source_authors = props.get("authors", [])
        if isinstance(source_authors, list):
            authors.update(author.lower() for author in source_authors)
        elif source_authors:
            authors.add(str(source_authors).lower())
    
    for evidence in evidence_list:
        props = evidence.get("properties", {})
        method_id = props.get("methodId")
        if method_id:
            methods.add(method_id)
        method_type = props.get("type")
        if method_type:
            methods.add(method_type)
    
    # Calculate diversity metrics
    type_diversity = min(1.0, len(source_types) / 3.0)  # 3+ types = max
    author_diversity = min(1.0, len(authors) / 2.0)  # 2+ authors = max
    method_diversity = min(1.0, len(methods) / 2.0)  # 2+ methods = max
    
    # Weighted average
    diversity = (
        type_diversity * 0.4 +
        author_diversity * 0.4 +
        method_diversity * 0.2
    )
    
    return diversity


def calculate_evidence_strength(evidence_list: List[Dict[str, Any]]) -> float:
    """
    Calculate strength of evidence supporting the claim.
    
    Factors:
    - Evidence type (empirical > theoretical > anecdotal)
    - Sample size (for empirical)
    - Effect size, p-value (for statistical)
    - Replication status
    
    Returns:
        Evidence strength score (0-1)
    """
    if not evidence_list:
        return 0.0
    
    strengths = []
    for evidence in evidence_list:
        props = evidence.get("properties", {})
        
        # Base strength from type
        ev_type = props.get("type", "unknown")
        type_scores = {
            "empirical": 0.9,
            "experimental": 0.95,
            "meta_analysis": 0.95,
            "systematic_review": 0.90,
            "theoretical": 0.7,
            "case_study": 0.6,
            "anecdotal": 0.3,
            "expert_opinion": 0.6
        }
        base_strength = type_scores.get(ev_type, 0.5)
        
        # Boost for statistical evidence
        sample_size = props.get("sampleSize", 0)
        effect_size = props.get("effectSize")
        p_value = props.get("pValue")
        
        if sample_size > 0:
            # Larger samples = stronger (log scale)
            sample_boost = min(0.1, 0.1 * (1 - 1 / (1 + sample_size / 100)))
            base_strength += sample_boost
        
        if effect_size:
            # Effect size > 0.5 = strong effect
            if abs(effect_size) > 0.5:
                base_strength += 0.05
        
        if p_value:
            # Lower p-value = stronger (p < 0.01 = very strong)
            if p_value < 0.01:
                base_strength += 0.05
            elif p_value < 0.05:
                base_strength += 0.02
        
        # Check explicit strength property
        explicit_strength = props.get("strength", 1.0)
        base_strength = (base_strength + explicit_strength) / 2
        
        strengths.append(min(1.0, base_strength))
    
    # Average evidence strength
    return sum(strengths) / len(strengths) if strengths else 0.0


def calculate_independence_score(
    sources: List[Dict[str, Any]],
    evidence_list: List[Dict[str, Any]]
) -> float:
    """
    Calculate independence of sources (different authors, venues, methods).
    
    Returns:
        Independence score (0-1)
    """
    if len(sources) < 2:
        return 0.3  # Low independence with single source
    
    # Check for same authors across sources
    all_authors = []
    for source in sources:
        props = source.get("properties", {})
        authors = props.get("authors", [])
        if isinstance(authors, list):
            all_authors.extend(author.lower() for author in authors)
        elif authors:
            all_authors.append(str(authors).lower())
    
    unique_authors = len(set(all_authors))
    total_authors = len(all_authors)
    
    # High independence if many unique authors relative to total
    if total_authors > 0:
        author_independence = unique_authors / max(total_authors, 1)
    else:
        author_independence = 0.5
    
    # Check for different venues/publishers
    venues = set()
    for source in sources:
        props = source.get("properties", {})
        publisher = props.get("publisher") or props.get("venue") or props.get("journal")
        if publisher:
            venues.add(publisher.lower())
    
    venue_independence = min(1.0, len(venues) / max(len(sources), 1))
    
    # Combined independence
    independence = (author_independence * 0.6 + venue_independence * 0.4)
    
    return independence


def calculate_conflict_penalty(
    claim: Dict[str, Any],
    sources: List[Dict[str, Any]],
    evidence_list: List[Dict[str, Any]]
) -> float:
    """
    Calculate penalty for conflicts/contradictions.
    
    Returns:
        Conflict score (0-1, higher = more conflicts)
    """
    props = claim.get("properties", {})
    
    # Check for explicit refutations
    refutations = props.get("refutations", [])
    supports = props.get("supports", [])
    
    if refutations:
        # Ratio of refutations to supports
        total_evidence = len(supports) + len(refutations)
        if total_evidence > 0:
            conflict_ratio = len(refutations) / total_evidence
        else:
            conflict_ratio = 0.5
    else:
        conflict_ratio = 0.0
    
    # Check for contradictory evidence types
    evidence_types = [ev.get("properties", {}).get("type") for ev in evidence_list]
    has_contradictory_types = (
        "refutation" in evidence_types and
        "support" in evidence_types
    )
    
    if has_contradictory_types:
        conflict_ratio = max(conflict_ratio, 0.3)
    
    return conflict_ratio


# ============================================================================
# DOMAIN-SPECIFIC QUALITY THRESHOLDS
# ============================================================================

def get_domain_quality_threshold(domain_name: str) -> Dict[str, float]:
    """
    Get quality thresholds for a specific domain.
    
    Returns:
        Dict with min_source_quality, min_confidence, min_sources, etc.
    """
    domain_info = get_domain_by_name(domain_name)
    difficulty = domain_info.get("difficulty", "intermediate") if domain_info else "intermediate"
    
    # Stricter requirements for advanced domains
    if difficulty == "advanced":
        return {
            "min_source_quality": 0.75,
            "min_confidence": 0.70,
            "min_sources": 3,
            "min_evidence": 2
        }
    elif difficulty == "intermediate":
        return {
            "min_source_quality": 0.65,
            "min_confidence": 0.60,
            "min_sources": 2,
            "min_evidence": 1
        }
    else:  # beginner
        return {
            "min_source_quality": 0.55,
            "min_confidence": 0.50,
            "min_sources": 1,
            "min_evidence": 1
        }
