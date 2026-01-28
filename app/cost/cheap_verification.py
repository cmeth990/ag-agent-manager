"""
Cheap verification before expensive reasoning.
Run regex/NER/statistical extraction first, only send uncertain cases to LLMs.
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_with_regex(
    text: str,
    patterns: Dict[str, str],
) -> Dict[str, List[str]]:
    """
    Extract entities using regex patterns.
    
    Args:
        text: Text to extract from
        patterns: Dict of {entity_type: regex_pattern}
    
    Returns:
        Dict of {entity_type: [matches]}
    """
    results = {}
    for entity_type, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        results[entity_type] = matches
    return results


def simple_ner(text: str) -> Dict[str, List[str]]:
    """
    Simple NER using patterns (no LLM).
    
    Extracts:
    - Dates (YYYY-MM-DD, MM/DD/YYYY, etc.)
    - Numbers (including decimals)
    - URLs
    - Email addresses
    - Capitalized phrases (potential proper nouns)
    """
    results = {
        "dates": [],
        "numbers": [],
        "urls": [],
        "emails": [],
        "proper_nouns": [],
    }
    
    # Dates
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
        r'\d{1,2}-\d{1,2}-\d{4}',  # MM-DD-YYYY
    ]
    for pattern in date_patterns:
        results["dates"].extend(re.findall(pattern, text))
    
    # Numbers
    results["numbers"] = re.findall(r'\d+\.?\d*', text)
    
    # URLs
    results["urls"] = re.findall(r'https?://[^\s]+', text)
    
    # Emails
    results["emails"] = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    
    # Proper nouns (capitalized words, 2+ chars, not at start of sentence)
    # Simple heuristic: consecutive capitalized words
    proper_noun_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b'
    results["proper_nouns"] = re.findall(proper_noun_pattern, text)
    
    return results


def statistical_extraction(
    text: str,
    min_frequency: int = 2,
) -> Dict[str, Any]:
    """
    Extract frequent terms/phrases using statistics.
    
    Args:
        text: Text to analyze
        min_frequency: Minimum frequency for extraction
    
    Returns:
        Dict with frequent terms and phrases
    """
    words = text.lower().split()
    
    # Word frequency
    word_freq: Dict[str, int] = {}
    for word in words:
        # Filter out common stop words
        if len(word) > 3:  # Ignore very short words
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Filter by frequency
    frequent_words = {
        word: freq
        for word, freq in word_freq.items()
        if freq >= min_frequency
    }
    
    # Sort by frequency
    sorted_words = sorted(frequent_words.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "frequent_terms": dict(sorted_words[:20]),  # Top 20
        "total_words": len(words),
        "unique_words": len(word_freq),
    }


def should_use_llm(
    text: str,
    confidence_threshold: float = 0.7,
) -> Tuple[bool, float, Dict[str, Any]]:
    """
    Decide if LLM extraction is needed based on cheap verification.
    
    Returns:
        (use_llm, confidence, extraction_results)
        - use_llm: True if LLM needed, False if cheap extraction sufficient
        - confidence: Confidence in cheap extraction (0.0-1.0)
        - extraction_results: Results from cheap extraction
    """
    # Run cheap extraction
    ner_results = simple_ner(text)
    stats = statistical_extraction(text)
    
    # Calculate confidence
    # Higher confidence if we found many entities and frequent terms
    entity_count = sum(len(v) for v in ner_results.values())
    frequent_term_count = len(stats.get("frequent_terms", {}))
    
    # Simple confidence heuristic
    confidence = min(1.0, (entity_count * 0.1) + (frequent_term_count * 0.05))
    
    # Use LLM if confidence is low or text is very short/long
    use_llm = (
        confidence < confidence_threshold or
        len(text) < 50 or  # Too short, might need context
        len(text) > 10000  # Too long, needs chunking/LLM
    )
    
    extraction_results = {
        "ner": ner_results,
        "statistics": stats,
        "confidence": confidence,
    }
    
    if not use_llm:
        logger.debug(f"Cheap extraction sufficient (confidence: {confidence:.2f})")
    else:
        logger.debug(f"LLM extraction needed (confidence: {confidence:.2f})")
    
    return (use_llm, confidence, extraction_results)


def filter_high_impact_candidates(
    candidates: List[Dict[str, Any]],
    max_candidates: int = 10,
) -> List[Dict[str, Any]]:
    """
    Filter to high-impact candidates before expensive validation.
    
    Criteria:
    - High confidence scores
    - Multiple source support
    - Recent/trending
    - Domain relevance
    
    Args:
        candidates: List of candidate entities/facts
        max_candidates: Maximum number to return
    
    Returns:
        Filtered list of high-impact candidates
    """
    # Score candidates
    scored = []
    for candidate in candidates:
        score = 0.0
        
        # Confidence score
        confidence = candidate.get("confidence", 0.5)
        score += confidence * 0.4
        
        # Source count
        source_count = len(candidate.get("sources", []))
        score += min(1.0, source_count / 3.0) * 0.3
        
        # Recency (if timestamp available)
        # score += recency_score * 0.2
        
        # Domain relevance (if available)
        # score += relevance_score * 0.1
        
        scored.append((score, candidate))
    
    # Sort by score (descending)
    scored.sort(reverse=True)
    
    # Return top-k
    return [candidate for _, candidate in scored[:max_candidates]]
