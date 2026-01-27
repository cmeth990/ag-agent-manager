"""
Examples and tests for source quality and claim confidence scoring.
"""
from app.kg.scoring import (
    calculate_source_quality,
    calculate_claim_confidence,
    get_domain_quality_threshold
)

# Example 1: High-quality academic source for Mathematics
example_source_1 = {
    "id": "SRC:example1",
    "label": "Source",
    "properties": {
        "title": "Introduction to Abstract Algebra",
        "authors": ["John Smith", "Jane Doe"],
        "year": 2020,
        "type": "textbook",
        "doi": "10.1234/example",
        "trustScore": 0.95,
        "impactFactor": None,
        "peerReviewed": True
    }
}

# Example 2: Recent ML paper
example_source_2 = {
    "id": "SRC:example2",
    "label": "Source",
    "properties": {
        "title": "Transformer Architecture in Machine Learning",
        "authors": ["Alice Researcher"],
        "year": 2024,
        "type": "peer_reviewed_journal",
        "doi": "10.5678/ml2024",
        "trustScore": 0.90,
        "impactFactor": 8.5,
        "citationCount": 150,
        "peerReviewed": True
    }
}

# Example 3: Website source
example_source_3 = {
    "id": "SRC:example3",
    "label": "Source",
    "properties": {
        "title": "Understanding Quantum Mechanics",
        "type": "website",
        "url": "https://example.com/quantum",
        "trustScore": 0.50,
        "year": 2023
    }
}

# Example evidence
example_evidence = [
    {
        "id": "E:example1",
        "label": "Evidence",
        "properties": {
            "type": "empirical",
            "content": "Experimental results show...",
            "sourceId": "SRC:example2",
            "strength": 0.9,
            "sampleSize": 1000,
            "pValue": 0.001
        }
    }
]

# Example claim
example_claim = {
    "id": "CL:example1",
    "label": "Claim",
    "properties": {
        "text": "Transformer models outperform RNNs in sequence tasks",
        "claimType": "empirical",
        "supports": ["E:example1"],
        "refutations": []
    }
}


def example_source_quality_calculations():
    """Example calculations for source quality."""
    print("=" * 60)
    print("SOURCE QUALITY EXAMPLES")
    print("=" * 60)
    
    # Mathematics domain (values historical sources)
    print("\n1. Textbook for Mathematics domain:")
    result1 = calculate_source_quality(example_source_1, domain_name="Abstract Algebra")
    print(f"   Quality Score: {result1['quality_score']}")
    print(f"   Components: {result1['components']}")
    print(f"   Domain Relevance: {result1['domain_relevance']}")
    
    # Machine Learning domain (values recent sources)
    print("\n2. Recent ML paper for Machine Learning domain:")
    result2 = calculate_source_quality(example_source_2, domain_name="Machine Learning")
    print(f"   Quality Score: {result2['quality_score']}")
    print(f"   Components: {result2['components']}")
    print(f"   Domain Relevance: {result2['domain_relevance']}")
    
    # Website source
    print("\n3. Website source for Quantum Mechanics:")
    result3 = calculate_source_quality(example_source_3, domain_name="Quantum Mechanics")
    print(f"   Quality Score: {result3['quality_score']}")
    print(f"   Components: {result3['components']}")
    print(f"   Recommendations: {result3['recommendations']}")


def example_claim_confidence_calculations():
    """Example calculations for claim confidence."""
    print("\n" + "=" * 60)
    print("CLAIM CONFIDENCE EXAMPLES")
    print("=" * 60)
    
    # Single high-quality source
    print("\n1. Claim with single high-quality source:")
    result1 = calculate_claim_confidence(
        example_claim,
        sources=[example_source_2],
        evidence_list=example_evidence,
        domain_name="Machine Learning"
    )
    print(f"   Confidence Score: {result1['confidence_score']}")
    print(f"   Components: {result1['components']}")
    print(f"   Source Count: {result1['source_count']}")
    print(f"   Recommendations: {result1['recommendations']}")
    
    # Multiple sources
    print("\n2. Claim with multiple sources:")
    result2 = calculate_claim_confidence(
        example_claim,
        sources=[example_source_2, example_source_1],
        evidence_list=example_evidence,
        domain_name="Machine Learning"
    )
    print(f"   Confidence Score: {result2['confidence_score']}")
    print(f"   Components: {result2['components']}")
    print(f"   Source Qualities: {result2['source_qualities']}")


def example_domain_thresholds():
    """Example domain-specific thresholds."""
    print("\n" + "=" * 60)
    print("DOMAIN QUALITY THRESHOLDS")
    print("=" * 60)
    
    domains = ["Arithmetic", "Calculus I", "Machine Learning"]
    for domain in domains:
        thresholds = get_domain_quality_threshold(domain)
        print(f"\n{domain}:")
        print(f"   Min Source Quality: {thresholds['min_source_quality']}")
        print(f"   Min Confidence: {thresholds['min_confidence']}")
        print(f"   Min Sources: {thresholds['min_sources']}")
        print(f"   Min Evidence: {thresholds['min_evidence']}")


if __name__ == "__main__":
    example_source_quality_calculations()
    example_claim_confidence_calculations()
    example_domain_thresholds()
