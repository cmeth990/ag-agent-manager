# Source Quality and Claim Confidence Scoring Formulas

## Overview

This document describes the formulas used to:
1. **Evaluate source quality** for each domain
2. **Calculate claim confidence** based on multiple sources

## Source Quality Formula

### Formula

```
Q_source = (Q_type × w_type) + (Q_credibility × w_cred) + (Q_relevance × w_rel) + 
           (Q_recency × w_rec) + (Q_impact × w_impact) + (Q_verification × w_ver)
```

Where:
- **Q_type** (25%): Base score from source type (peer-reviewed journal = 0.95, website = 0.50)
- **Q_credibility** (25%): Trust score, peer review status, citation count
- **Q_relevance** (20%): How well source matches the target domain
- **Q_recency** (15%): Age appropriateness for domain (domain-dependent)
- **Q_impact** (10%): Impact factor, journal prestige
- **Q_verification** (5%): DOI, URL, authors, verification status

### Component Details

#### 1. Source Type Base Score (Q_type)

| Source Type | Base Score |
|------------|------------|
| Peer-reviewed journal | 0.95 |
| Academic paper | 0.90 |
| Textbook | 0.95 |
| University course | 0.90 |
| Preprint | 0.70 |
| Educational platform | 0.80 |
| Website | 0.50 |
| Blog | 0.40 |

#### 2. Credibility Score (Q_credibility)

```
Q_credibility = (trustScore × 0.5) + (peerReviewed × 0.3) + (citationScore × 0.2)
```

- **trustScore**: Existing trust score (0-1)
- **peerReviewed**: 1.0 if peer-reviewed, 0.5 otherwise
- **citationScore**: Normalized citation count (log scale: 0-1000+ citations)

#### 3. Domain Relevance (Q_relevance)

- **Exact domain match**: 1.0
- **Domain mentioned in title/description**: 0.8
- **Category match**: 0.7
- **Partial match**: 0.5
- **No match**: 0.3

#### 4. Recency Score (Q_recency)

**Domain-dependent** - some domains need recent sources, others value historical:

| Domain Type | Optimal Age | Max Age | Weight |
|------------|-------------|---------|--------|
| Fast-moving (CS, ML, AI) | 2-3 years | 5-10 years | 0.20-0.25 |
| Medium (Medicine, Psychology) | 5-10 years | 15-30 years | 0.10-0.15 |
| Stable (Math, Philosophy) | 20-50 years | 100-200 years | 0.05 |

Formula:
- If `age ≤ optimal_age`: `score = 1.0 - (0.3 × age/optimal_age)`
- If `optimal_age < age ≤ max_age`: `score = 0.7 × (1 - (age - optimal_age)/(max_age - optimal_age))`
- If `age > max_age`: `score = 0.2 × (max_age/age)`

#### 5. Impact Factor (Q_impact)

```
Q_impact = min(1.0, impactFactor / 100.0)
```

Normalized to typical range (0-100, some journals >100).

#### 6. Verification (Q_verification)

```
Q_verification = (hasDOI × 0.4) + (hasURL × 0.2) + (hasAuthors × 0.2) + (verified × 0.2)
```

### Example Source Quality Calculation

**Source**: Peer-reviewed ML paper from 2024
- Type: `peer_reviewed_journal` → Q_type = 0.95
- Credibility: trustScore=0.90, peerReviewed=True, citations=150 → Q_credibility = 0.92
- Relevance: Domain match → Q_relevance = 1.0
- Recency: Age=0, optimal=2 → Q_recency = 1.0
- Impact: IF=8.5 → Q_impact = 0.085
- Verification: Has DOI, URL, authors → Q_verification = 1.0

**Result**: Q_source = 0.95×0.25 + 0.92×0.25 + 1.0×0.20 + 1.0×0.15 + 0.085×0.10 + 1.0×0.05 = **0.96**

---

## Claim Confidence Formula

### Formula

```
C_claim = (C_source_quality × w_sq) + (C_agreement × w_agr) + (C_diversity × w_div) +
          (C_evidence_strength × w_ev) + (C_independence × w_ind) - (C_conflicts × w_conf)
```

Where:
- **C_source_quality** (30%): Weighted average of source quality scores
- **C_agreement** (20%): How well sources agree on the claim
- **C_diversity** (15%): Diversity of source types, authors, methods
- **C_evidence_strength** (20%): Strength of supporting evidence
- **C_independence** (10%): Independence of sources (different authors, venues)
- **C_conflicts** (5%): Penalty for conflicting sources/evidence

### Component Details

#### 1. Source Quality (C_source_quality)

Weighted average (higher quality sources count more):

```
C_source_quality = Σ(q²) / Σ(q)
```

Where `q` is the quality score of each source.

#### 2. Agreement Score (C_agreement)

- **2 sources, no refutations**: 0.7
- **3 sources, no refutations**: 0.8
- **4+ sources, no refutations**: 0.9
- **Has refutations**: 0.4 (or lower based on ratio)

#### 3. Diversity Score (C_diversity)

```
C_diversity = (type_diversity × 0.4) + (author_diversity × 0.4) + (method_diversity × 0.2)
```

- **Type diversity**: `min(1.0, unique_types / 3)`
- **Author diversity**: `min(1.0, unique_authors / 2)`
- **Method diversity**: `min(1.0, unique_methods / 2)`

#### 4. Evidence Strength (C_evidence_strength)

Base strength by type:
- Empirical/Experimental: 0.9-0.95
- Meta-analysis: 0.95
- Systematic review: 0.90
- Theoretical: 0.7
- Case study: 0.6
- Anecdotal: 0.3

Boosts:
- Large sample size: +0.1 (log scale)
- Strong effect size (>0.5): +0.05
- Low p-value (<0.01): +0.05

#### 5. Independence Score (C_independence)

```
C_independence = (author_independence × 0.6) + (venue_independence × 0.4)
```

- **Author independence**: `unique_authors / total_authors`
- **Venue independence**: `unique_venues / total_sources`

#### 6. Conflict Penalty (C_conflicts)

```
C_conflicts = refutations_count / (supports_count + refutations_count)
```

Higher ratio = more conflicts = higher penalty.

### Example Claim Confidence Calculation

**Claim**: "Transformer models outperform RNNs"
- **Sources**: 2 high-quality papers (Q=0.96, Q=0.90)
- **Evidence**: 1 empirical study (strength=0.95, sample=1000, p<0.01)
- **No refutations**

**Components**:
- C_source_quality = (0.96² + 0.90²) / (0.96 + 0.90) = 0.93
- C_agreement = 0.7 (2 sources, no refutations)
- C_diversity = 0.8 (different authors, same type)
- C_evidence_strength = 0.95
- C_independence = 0.9 (different authors, different venues)
- C_conflicts = 0.0

**Result**: C_claim = 0.93×0.30 + 0.7×0.20 + 0.8×0.15 + 0.95×0.20 + 0.9×0.10 - 0.0×0.05 = **0.87**

---

## Domain-Specific Quality Thresholds

Different domains have different quality requirements:

| Difficulty | Min Source Quality | Min Confidence | Min Sources | Min Evidence |
|------------|-------------------|----------------|-------------|--------------|
| Advanced | 0.75 | 0.70 | 3 | 2 |
| Intermediate | 0.65 | 0.60 | 2 | 1 |
| Beginner | 0.55 | 0.50 | 1 | 1 |

---

## Usage

### Calculate Source Quality

```python
from app.kg.scoring import calculate_source_quality

source = {
    "properties": {
        "title": "Introduction to Algebra",
        "type": "textbook",
        "year": 2020,
        "trustScore": 0.95,
        "doi": "10.1234/example"
    }
}

result = calculate_source_quality(source, domain_name="Algebra")
print(f"Quality: {result['quality_score']}")
print(f"Components: {result['components']}")
```

### Calculate Claim Confidence

```python
from app.kg.scoring import calculate_claim_confidence

claim = {"properties": {"text": "...", "claimType": "empirical"}}
sources = [source1, source2]
evidence = [evidence1]

result = calculate_claim_confidence(claim, sources, evidence, domain_name="Machine Learning")
print(f"Confidence: {result['confidence_score']}")
print(f"Components: {result['components']}")
print(f"Recommendations: {result['recommendations']}")
```

---

## Recommendations

The scoring system provides recommendations for improvement:

- **Source Quality**: "Consider using peer-reviewed sources"
- **Confidence**: "At least 2 independent sources recommended"
- **Agreement**: "Sources show low agreement - verify claim accuracy"
- **Diversity**: "Low source diversity - seek different types/authors"
- **Evidence**: "Evidence strength is weak - need stronger evidence"
- **Conflicts**: "Conflicting evidence detected - investigate contradictions"

These recommendations help guide source selection and claim verification.
