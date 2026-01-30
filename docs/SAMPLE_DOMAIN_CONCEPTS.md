# Sample Domain: Concepts Derived Through the Integrated Methodology

This document shows **one domain** (Algebra I) with **sources discovered via free secondaries**, **primary identifiers canonicalized**, and **concepts/claims derived** with the audit trail (confidence tier, P(error), evidence summary).

---

## Methodology recap

1. **Secondary → primary:** We query free/low-cost secondary sources (Semantic Scholar, arXiv, OpenAlex, OpenStax, etc.) to discover references. They return metadata and stable primary identifiers (DOI, arXiv ID, URL). We canonicalize these into `Source.identifiers`.
2. **Content:** We rank and optionally fetch content from those primaries.
3. **Extraction:** We extract concepts and claims from content (or from domain-aware templates).
4. **Audit trail:** We assign each claim a **confidence_tier** (Provisional / Supported / Audited), **p_error**, and **evidence_summary** so users get structural credibility and a path to deeper verification.

---

## Sample domain: Algebra I

| Field | Value |
|-------|--------|
| **Domain** | Algebra I |
| **Category** | Mathematics & Computational Sciences |
| **Upper ontology** | Relations |
| **Grade bands** | 6–8, 9–12 |
| **Difficulty** | intermediate |

---

## Sources (discovered via secondary APIs, primary IDs canonicalized)

Sources below are the kind of results we get from `discover_sources_for_domain("Algebra I")` and `enrich_source_with_primary_identifiers()`. Identifiers come from free secondaries and point to primary works.

| # | Title | Type | Primary identifiers | Quality |
|---|--------|------|---------------------|--------|
| 1 | Linear Equations and Inequalities | academic_paper | `doi: 10.1007/978-3-030-12345-6_2` | 0.82 |
| 2 | Introduction to Algebra (OpenStax) | textbook | `url: https://openstax.org/details/books/algebra` | 0.78 |
| 3 | Quadratic Functions: Theory and Practice | preprint | `arxiv: 2103.04567` | 0.71 |
| 4 | Algebra I | university_course | (OER, no DOI) | 0.68 |

*Identifiers are stored in `Source.properties.identifiers` (e.g. `{"doi": "10.1007/..."}` or `{"arxiv": "2103.04567"}`) for reproducibility and dedup.*

---

## Concepts derived for Algebra I

Concepts are the kind of nodes we extract (extractor worker) from content or domain templates. Each is scoped to the domain and can be linked to claims and evidence.

| Concept | Description | Scale |
|---------|-------------|--------|
| **Linear equation in one variable** | An equation of the form ax + b = 0 with one unknown; solution set is at most one value. | micro |
| **Quadratic function** | A polynomial function of degree 2: f(x) = ax² + bx + c; graph is a parabola. | micro |
| **Slope** | Rate of change of a linear function; ratio Δy/Δx between two points. | micro |
| **Systems of linear equations** | Two or more linear equations in the same variables; solution is intersection of solution sets. | meso |

---

## Claims derived (with audit trail)

Claims are evidence-backed statements. Each has **confidence_tier**, **p_error**, and **evidence_summary** from our scoring and `enrich_claim_with_audit()`.

### Claim 1

| Field | Value |
|-------|--------|
| **Text** | A linear equation in one variable has at most one solution over the real numbers. |
| **Claim type** | definition |
| **Scope** | Algebra I, real numbers |
| **confidence_tier** | Supported |
| **p_error** | 0.18 |
| **confidence** | 0.82 |
| **evidence_summary** | Definition aligned with OpenStax Algebra and standard textbook treatments; single primary source (OpenStax) plus secondary convergence. |

### Claim 2

| Field | Value |
|-------|--------|
| **Text** | The graph of a quadratic function f(x) = ax² + bx + c is a parabola opening up if a > 0 and down if a < 0. |
| **Claim type** | definition |
| **Scope** | Algebra I, real-valued quadratics |
| **confidence_tier** | Provisional |
| **p_error** | 0.32 |
| **confidence** | 0.68 |
| **evidence_summary** | Multiple secondary references (preprint, course notes); confidence capped for secondary-only evidence until primary verification. |

### Claim 3

| Field | Value |
|-------|--------|
| **Text** | Two distinct non-vertical lines in the plane are parallel if and only if they have the same slope. |
| **Claim type** | empirical/theoretical |
| **Scope** | Algebra I, Euclidean plane |
| **confidence_tier** | Supported |
| **p_error** | 0.12 |
| **confidence** | 0.88 |
| **evidence_summary** | Standard curriculum claim; supported by textbook and course materials; high agreement across sources. |

---

## How to reproduce this sample

- **Sources:** Run discovery for "Algebra I" and enrich with primary identifiers:
  - `discover_sources_for_domain("Algebra I", max_sources=10)` (uses Semantic Scholar, arXiv, OpenAlex, OpenStax, etc.)
  - Each source is then passed through `enrich_source_with_primary_identifiers(source)` so `identifiers` is set.
- **Concepts/claims:** In the full pipeline, content is fetched from discovered sources and the **extractor** node produces concepts and claims; **scoring** produces confidence; **audit_trail** adds `confidence_tier`, `p_error`, `evidence_summary` via `enrich_claim_with_audit(claim, confidence_score, evidence_summary=...)`.
- **Script:** Run `scripts/sample_domain_concepts.py` to print or regenerate a sample (optionally with `--live` to use real discovery).

---

## References

- **Audit trail spec:** [audit_trail_process.pdf](audit_trail_process.pdf)
- **Methodology in code:** [AUDIT_TRAIL_AND_CLAIM_TIERS.md](AUDIT_TRAIL_AND_CLAIM_TIERS.md) (§8 Securing knowledge claims, §3 Claim tiers)
- **Discovery:** `app/kg/source_discovery.py` (`discover_sources_for_domain`, `canonicalize_primary_identifiers`, `enrich_source_with_primary_identifiers`)
- **Claim tiers:** `app/kg/audit_trail.py` (`assign_confidence_tier`, `enrich_claim_with_audit`)
