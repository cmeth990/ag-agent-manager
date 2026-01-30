#!/usr/bin/env python3
"""
Sample domain with concepts derived through the integrated methodology.

Demonstrates: secondary → primary (discover sources, canonicalize identifiers),
then concepts and claims with audit trail (confidence_tier, p_error, evidence_summary).

Usage:
  python scripts/sample_domain_concepts.py              # Print sample (canned data)
  python scripts/sample_domain_concepts.py --live      # Run real discovery for Algebra I
  python scripts/sample_domain_concepts.py --live --domain "Linear Algebra"
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure app is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.kg.audit_trail import enrich_claim_with_audit
from app.kg.source_discovery import discover_sources_for_domain, enrich_source_with_primary_identifiers


SAMPLE_DOMAIN = "Algebra I"
SAMPLE_CONCEPTS = [
    {"name": "Linear equation in one variable", "description": "Equation of the form ax + b = 0; solution set at most one value.", "scale": "micro"},
    {"name": "Quadratic function", "description": "Polynomial of degree 2: f(x) = ax² + bx + c; graph is a parabola.", "scale": "micro"},
    {"name": "Slope", "description": "Rate of change of a linear function; ratio Δy/Δx.", "scale": "micro"},
    {"name": "Systems of linear equations", "description": "Two or more linear equations; solution is intersection of solution sets.", "scale": "meso"},
]
SAMPLE_CLAIMS = [
    {"text": "A linear equation in one variable has at most one solution over the real numbers.", "claimType": "definition", "confidence": 0.82, "evidence_summary": "Definition aligned with OpenStax and standard textbooks; single primary source plus secondary convergence."},
    {"text": "The graph of a quadratic function f(x) = ax² + bx + c is a parabola opening up if a > 0 and down if a < 0.", "claimType": "definition", "confidence": 0.68, "evidence_summary": "Multiple secondary references; confidence capped until primary verification."},
    {"text": "Two distinct non-vertical lines in the plane are parallel if and only if they have the same slope.", "claimType": "empirical", "confidence": 0.88, "evidence_summary": "Standard curriculum claim; high agreement across sources."},
]


def _print_section(title: str, lines: list) -> None:
    print(f"\n## {title}\n")
    for line in lines:
        print(line)
    print()


def _format_sources(sources: list) -> list:
    out = []
    out.append("| # | Title | Type | Primary identifiers | Quality |")
    out.append("|---|--------|------|---------------------|--------|")
    for i, s in enumerate(sources[:8], 1):
        props = s.get("properties") or {}
        title = (props.get("title") or "Untitled")[:45]
        stype = props.get("type", "unknown")
        ids = props.get("identifiers") or {}
        id_str = ", ".join(f"{k}: {v}" for k, v in list(ids.items())[:2]) if ids else "(none)"
        q = s.get("quality_score")
        q_str = f"{q:.2f}" if q is not None else "—"
        out.append(f"| {i} | {title} | {stype} | {id_str} | {q_str} |")
    return out


def _format_concepts(concepts: list) -> list:
    out = []
    out.append("| Concept | Description | Scale |")
    out.append("|---------|-------------|-------|")
    for c in concepts:
        out.append(f"| **{c['name']}** | {c['description']} | {c.get('scale', 'micro')} |")
    return out


def _format_claims(claims: list) -> list:
    out = []
    for i, c in enumerate(claims, 1):
        props = c.get("properties") or {}
        out.append(f"### Claim {i}")
        out.append(f"- **Text:** {props.get('text', '')}")
        out.append(f"- **Claim type:** {props.get('claimType', '')}")
        out.append(f"- **confidence_tier:** {props.get('confidence_tier', '—')}")
        out.append(f"- **p_error:** {props.get('p_error', '—')}")
        out.append(f"- **confidence:** {props.get('confidence', '—')}")
        out.append(f"- **evidence_summary:** {props.get('evidence_summary', '—')}")
        out.append("")
    return out


def run_canned(domain: str) -> None:
    """Print sample using canned data (no API calls)."""
    print(f"# Sample domain: {domain}")
    print("\n*Methodology: secondary → primary (discover sources, canonicalize identifiers); concepts and claims with audit trail.*\n")
    _print_section("Sources (example shape after discovery + canonicalize_primary_identifiers)", [
        "| # | Title | Type | Primary identifiers | Quality |",
        "|---|--------|------|---------------------|--------|",
        "| 1 | Linear Equations and Inequalities | academic_paper | doi: 10.1007/... | 0.82 |",
        "| 2 | Introduction to Algebra (OpenStax) | textbook | url: openstax.org/... | 0.78 |",
        "| 3 | Quadratic Functions: Theory and Practice | preprint | arxiv: 2103.04567 | 0.71 |",
    ])
    _print_section("Concepts derived", _format_concepts(SAMPLE_CONCEPTS))
    # Build claim dicts and enrich with audit
    claims_enriched = []
    for sc in SAMPLE_CLAIMS:
        claim = {"id": "CL:sample", "label": "Claim", "properties": {"text": sc["text"], "claimType": sc["claimType"]}}
        enrich_claim_with_audit(claim, sc["confidence"], evidence_summary=sc.get("evidence_summary"))
        claims_enriched.append(claim)
    _print_section("Claims (with confidence_tier, p_error, evidence_summary)", _format_claims(claims_enriched))


async def run_live(domain: str, max_sources: int = 8) -> None:
    """Run real discovery for domain, then add canned concepts/claims with audit; print report."""
    print(f"# Sample domain: {domain} (live discovery)")
    print("\n*Running discover_sources_for_domain and enrich_source_with_primary_identifiers.*\n")
    try:
        result = await discover_sources_for_domain(domain, max_sources=max_sources, min_quality=0.5)
    except Exception as e:
        print(f"Discovery failed: {e}")
        print("Falling back to canned sample.\n")
        run_canned(domain)
        return
    sources = result.get("sources") or []
    if not sources:
        print("No sources returned; showing canned sample.\n")
        run_canned(domain)
        return
    _print_section("Sources (discovered + canonicalized primary identifiers)", _format_sources(sources))
    _print_section("Concepts derived (sample; full pipeline would extract from content)", _format_concepts(SAMPLE_CONCEPTS))
    claims_enriched = []
    for sc in SAMPLE_CLAIMS:
        claim = {"id": "CL:sample", "label": "Claim", "properties": {"text": sc["text"], "claimType": sc["claimType"]}}
        enrich_claim_with_audit(claim, sc["confidence"], evidence_summary=sc.get("evidence_summary"))
        claims_enriched.append(claim)
    _print_section("Claims (with confidence_tier, p_error, evidence_summary)", _format_claims(claims_enriched))


def main() -> None:
    ap = argparse.ArgumentParser(description="Sample domain with concepts derived through the integrated methodology.")
    ap.add_argument("--live", action="store_true", help="Run real discover_sources_for_domain for the domain")
    ap.add_argument("--domain", default=SAMPLE_DOMAIN, help=f"Domain name (default: {SAMPLE_DOMAIN})")
    ap.add_argument("--max-sources", type=int, default=8, help="Max sources when --live (default: 8)")
    args = ap.parse_args()
    if args.live:
        asyncio.run(run_live(args.domain, max_sources=args.max_sources))
    else:
        run_canned(args.domain)


if __name__ == "__main__":
    main()
