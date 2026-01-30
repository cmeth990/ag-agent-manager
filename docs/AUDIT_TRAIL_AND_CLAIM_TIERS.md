# Audit Trail and Claim Tiers

This document maps the **Audit Trail Process** spec ([audit_trail_process.pdf](audit_trail_process.pdf)) to the ag-agent-manager implementation.

## Objective (from spec)

Build a knowledge graph that produces **decision-grade claims** with a **scalable audit trail** by:

1. Using free/low-cost secondary sources to discover and index evidence  
2. Clustering supporting evidence into **independent primary clusters**  
3. Promoting claims through **evidence tiers** (Provisional → Supported → Audited)  
4. Continuously calibrating confidence using **human review**

**Design promise:** Users get structural credibility (independent evidence clusters, scope, recency, contradiction awareness) and a path to deeper verification when required.

---

## 1. Ontology framing

Every claim is categorized under an **upper-ontology output type**. This is already implemented.

| Where | What |
|-------|------|
| `app/kg/categories.py` | `UPPER_ONTOLOGY` (entities, relations, events_processes) and `CATEGORIES` (12 categories under them) |
| `app/kg/domains.py` | Domain taxonomy and `get_domain_by_name`, `get_upper_ontology_by_category` |
| Claim nodes | Optional `domain_key`, `upper_ontology_type` (see knowledge_base schema) |

---

## 2. What “audit trail” means

The audit trail is the information required to **reproduce and defend** a claim’s support status.

- **Trust calibration:** Users can trust a claim without reading primaries; auditors can validate evidence and process.  
- **Reproducibility:** Enough metadata and identifiers to re-run verification.  
- **Accountability:** Who/what produced the claim and when; human review when applied.

| Where | What |
|-------|------|
| `app/kg/provenance.py` | `create_provenance`, `attach_provenance_to_node/edge` — source_agent, source_document, created_at, confidence, reasoning, evidence |
| Extended (this integration) | `last_verified_at`, `evidence_summary` on claims; optional `_provenance` on nodes/edges |

---

## 3. Claim tiers and guarantees

Every claim is assigned a **tier** based on evidence quality, independence, scope, recency, and contradiction handling.

| Tier | Meaning | Use |
|------|---------|-----|
| **Provisional** | Secondary convergence, metadata-level evidence; confidence capped | Exploration, drafts |
| **Supported** | Meets independence and scope with primary identifiers and credible evidence types | Normal use |
| **Audited** | Strict evidence floors, reproducible verification record (human or controlled verifier) | High-stakes |

| Where | What |
|-------|------|
| `app/kg/knowledge_base.py` | `CLAIM_TIERS`, Claim optional_properties: `confidence_tier`, `p_error` |
| `app/kg/audit_trail.py` | `CLAIM_TIERS`, `assign_confidence_tier()`, confidence caps and promotion thresholds |
| `app/kg/scoring.py` | `calculate_claim_confidence` (existing); `compute_p_error` / tier assignment (new hooks) |

---

## 4. Core data model (conceptual → implementation)

| Concept | Spec fields | Implementation |
|--------|-------------|----------------|
| **Claim** | claim_id, domain_key, upper_ontology_type, claim_type, claim_text, scope, confidence_tier, p_error, contradiction_status, last_verified_at, evidence_summary | `NODE_TYPES["Claim"]`: required `text`, `claimType`; optional `scope`, `confidence`, `confidence_tier`, `p_error`, `contradiction_status`, `last_verified_at`, `evidence_summary`, `domain_key`, `upper_ontology_type`, `supports`, `refutations`, `sourceId`, `conceptId` |
| **Source** | source_id, source_type, identifiers (DOI/PMID/arXiv/NCT/CIK+Accession), license_flags, issuer, timestamp/version | `NODE_TYPES["Source"]`: required `title`; optional `authors`, `year`, `type`, `doi`, `url`, `identifiers`, `license_flags`, `issuer`, `trustScore`, `impactFactor`, `cluster_id` (independence cluster) |
| **Evidence edge** | source → (supports \| contradicts \| qualifies \| defines) → claim; extraction_method, scope_alignment_score | `EDGE_TYPES`: SUPPORTS, REFUTES (Evidence→Claim); QUALIFIES, ANCHORS (Source/Evidence→Claim) with `extraction_method`, `scope_alignment_score` |
| **Independence cluster** | Grouping of sources with shared upstream origin (trial, dataset, statute version, filing accession) | Optional `cluster_id` on Source; clustering logic in pipeline (canonicalize IDs → cluster by upstream origin) |

---

## 5. Methodology: secondary → primary clusters

- Collect candidate references from secondary sources.  
- Canonicalize primary identifiers (DOI/PMID/arXiv/NCT/etc.).  
- Expand citation-graph neighborhood where available.  
- **Cluster primaries by upstream origin** (shared trial/dataset/statute/filing + citation overlap).  
- Search for counterevidence and attach contradiction edges.  
- Compute effective evidence strength and assign tier.

| Where | What |
|-------|------|
| `app/kg/source_discovery.py` | Discover sources; canonicalize identifiers where available |
| `app/kg/source_fetcher.py` | Fetch content; rate limit, circuit breaker |
| `app/kg/scoring.py` | Source quality, claim confidence, independence/diversity, conflict penalty |
| `app/kg/deduplication.py` | Contradiction detection between claims; resolve_contradiction |
| Future | Independence clustering (cluster_id, upstream_origin); tier assignment from effective evidence |

---

## 6. Scoring and equations

Spec: **P(error | c) = σ( β₀ − βP·EP(c) − βS·ES(c) + βK·K(c) + βT·T(c) + βA·A(c) )**  
σ(x)=1/(1+e^(-x)); EP/ES = effective primary/secondary evidence; K = contradiction; T = time-sensitivity; A = scope mismatch.  
**Confidence = 1 − P(error).**

- **Effective evidence (independence-weighted):**  
  EP(c) = Σ (w·q·r·m) over primary clusters; ES(c) = Σ (w·q·r·m) over secondary clusters (w=independence, q=quality, r=recency, m=scope match).  
- **Confidence caps:** Conf(c) ≤ C_sec unless EP(c) ≥ τP (promotion threshold).

| Where | What |
|-------|------|
| `app/kg/scoring.py` | `calculate_source_quality`, `calculate_claim_confidence` (agreement, diversity, evidence strength, independence, conflict penalty); recency, domain relevance |
| `app/kg/audit_trail.py` | `compute_p_error()`, `assign_confidence_tier()` — map existing scores to P(error) and Provisional/Supported/Audited; caps and τP (configurable per domain/claim_type) |

---

## 7. Human review loop

- **Priority(c) = Impact(c) × P(error | c) × Uncertainty(c)**  
- Reviewers label claims (correct / incorrect / ambiguous) and tag failure modes.  
- Update: weights β, quality priors q, independence heuristics w, staleness r, scope match m, caps/floors.

| Where | What |
|-------|------|
| `app/graph/supervisor.py` | Approval flow: user Approve/Reject before commit |
| `app/graph/workers.py` | commit_node, reject_node; apply_diff or discard |
| Future | Explicit review queue (priority by Impact × P(error) × Uncertainty); store review outcome and update scoring params |

---

## 8. Securing knowledge claims: secondary → primary

**Methodology (from spec):** We use **free/low-cost secondary sources** (indexes, APIs, dumps) as an **affordable way to discover and identify primary sources**. Secondaries give us metadata and stable primary identifiers (DOI, PMID, arXiv ID, NCT, etc.); we then fetch or link to the actual primary works for evidence.

- **Secondary:** Indexes/APIs that list or cite works (e.g. Semantic Scholar, arXiv, OpenAlex, Wikipedia, OpenStax). We query these first; they return references and identifiers.
- **Primary:** The actual paper, book, trial, or dataset. We identify primaries via canonical IDs from secondaries; we store these in `Source.identifiers` and optionally fetch content.

**Where this is implemented:**

| Step | What we do | Where |
|------|------------|--------|
| 1. Query secondary sources | Free APIs (Semantic Scholar, arXiv, OpenAlex, etc.) return metadata + DOI/URL/arXiv ID | `app/kg/source_discovery.py`, `app/kg/api_clients.py` |
| 2. Canonicalize primary IDs | Extract and store DOI, arXiv ID, etc. on Source as `identifiers` | `app/kg/source_discovery.py` → `canonicalize_primary_identifiers()` |
| 3. Rank and filter | Quality/recency/domain relevance; prefer sources with stable IDs | `app/kg/scoring.py`, `app/kg/source_fetcher.py` |
| 4. Fetch primary content | When needed, fetch full text or landing page from primary (via URL/DOI) | `app/kg/source_fetcher.py` → `gather_domain_content_prioritized()` |

So **yes**: we integrate the methodology. Discovery is driven by free secondaries; they give us primary identifiers; we store those and use them for ranking and fetching.

---

## 9. Secondary sources (spec table → our usage)

The spec lists OpenAlex, OpenCitations, Crossref, Wikipedia, Europe PMC, PubMed, ClinicalTrials.gov, PMC OA, arXiv, NASA ADS, IETF/RFC, W3C, SEC EDGAR, FRED, Congress.gov, FederalRegister.gov, CourtListener, Open Library.

| Where | What we use today |
|-------|--------------------|
| `app/kg/source_discovery.py`, `app/kg/api_clients.py` | Semantic Scholar, arXiv, OpenAlex, Wikipedia, OpenStax, Khan, MIT OCW (and similar) |
| Adding more | New sources can be added with stable identifiers (DOI/PMID/arXiv/NCT, etc.) and wired to canonicalize + cluster |

---

## 10. Pipeline summary (spec → system)

1. Ingest secondary sources (metadata, references, identifiers). → **Source discovery, content fetch**  
2. Extract candidate claims (domain-aware templates). → **Extractor worker**  
3. Attach evidence edges (supports/contradicts/qualifies/defines). → **Linker/Writer; SUPPORTS/REFUTES/QUALIFIES/ANCHORS**  
4. Canonicalize and deduplicate sources (stable IDs). → **Deduplication; optional cluster_id**  
5. Form independence clusters; compute effective evidence. → **Scoring; future clustering**  
6. Score P(error); assign tier with caps/floors. → **audit_trail.assign_confidence_tier, scoring**  
7. Publish claim cards (scope, tier, cluster summary, recency, contradictions). → **Query node; progress; future “claim card” API**  
8. Human review loop; recompute. → **Approval flow; future review queue and param updates**

---

## 11. New / updated code references

- **Schema:** `app/kg/knowledge_base.py` — Claim/Source optional props; QUALIFIES, DEFINES edges; CLAIM_TIERS.  
- **Tiers and P(error):** `app/kg/audit_trail.py` — CLAIM_TIERS, assign_confidence_tier(), compute_p_error().  
- **Provenance:** `app/kg/provenance.py` — last_verified_at, evidence_summary in audit provenance.  
- **Architecture:** `docs/ARCHITECTURE_AND_MOVING_PARTS.md` — audit trail and claim tiers section.
