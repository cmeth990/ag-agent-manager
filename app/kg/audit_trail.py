"""
Audit trail and claim tier assignment (Audit Trail Process spec).

Claim tiers: Provisional (capped confidence, exploration) → Supported (independence + scope) → Audited (reproducible verification).
P(error) model and confidence caps align with docs/audit_trail_process.pdf.
"""
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Claim tiers from spec: Provisional | Supported | Audited
CLAIM_TIERS = ("Provisional", "Supported", "Audited")

# Default confidence cap for secondary-only evidence (Provisional)
DEFAULT_C_SEC = 0.70
# Default promotion threshold: min effective primary evidence to allow Supported+
DEFAULT_TAU_P = 0.5


def compute_p_error(
    confidence_score: float,
) -> float:
    """
    Map a confidence score (0-1) to P(error).
    Spec: Conf(c) = 1 - P(error), so P(error) = 1 - Conf(c).
    """
    return max(0.0, min(1.0, 1.0 - float(confidence_score)))


def assign_confidence_tier(
    confidence_score: float,
    effective_primary: Optional[float] = None,
    domain_key: Optional[str] = None,
    claim_type: Optional[str] = None,
    c_sec: Optional[float] = None,
    tau_p: Optional[float] = None,
) -> str:
    """
    Assign claim tier from confidence and optional effective primary evidence.

    - Provisional: confidence capped by c_sec when effective_primary < tau_p.
    - Supported: confidence above cap and/or effective_primary >= tau_p.
    - Audited: reserved for claims with reproducible verification record (caller sets separately).

    Args:
        confidence_score: 0-1 from calculate_claim_confidence or similar.
        effective_primary: Optional effective primary evidence strength (0-1 scale).
        domain_key: Optional; per-domain caps can be applied later.
        claim_type: Optional; per-claim-type caps can be applied later.
        c_sec: Confidence cap for secondary-only (default DEFAULT_C_SEC).
        tau_p: Promotion threshold for primary evidence (default DEFAULT_TAU_P).

    Returns:
        One of CLAIM_TIERS: "Provisional", "Supported", "Audited".
    """
    cap = c_sec if c_sec is not None else DEFAULT_C_SEC
    tau = tau_p if tau_p is not None else DEFAULT_TAU_P
    # Apply cap when primary evidence is below threshold
    if effective_primary is not None and effective_primary < tau:
        effective_conf = min(confidence_score, cap)
    else:
        effective_conf = confidence_score
    # Tier by effective confidence (Audited is not set here; set by human/verifier)
    if effective_conf <= 0.5:
        return CLAIM_TIERS[0]  # Provisional
    if effective_conf < 0.75:
        return CLAIM_TIERS[0]  # Provisional (below typical Supported floor)
    return CLAIM_TIERS[1]  # Supported (Audited remains explicit elsewhere)


def enrich_claim_with_audit(
    claim: Dict[str, Any],
    confidence_score: float,
    effective_primary: Optional[float] = None,
    evidence_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add confidence_tier, p_error, and optional evidence_summary to a claim dict (in-place and return).
    """
    tier = assign_confidence_tier(confidence_score, effective_primary=effective_primary)
    p_error = compute_p_error(confidence_score)
    props = claim.get("properties") or {}
    props["confidence_tier"] = tier
    props["p_error"] = round(p_error, 4)
    props["confidence"] = round(confidence_score, 4)
    if evidence_summary is not None:
        props["evidence_summary"] = str(evidence_summary)[:2000]
    claim["properties"] = props
    return claim
