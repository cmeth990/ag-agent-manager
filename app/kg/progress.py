"""
Knowledge graph progress at each level of the category hierarchy.
- get_progress_stats() / get_progress_tree() for data
- Token create/validate for private dashboard link
- Optional: render_progress_images() for static charts
"""
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import time
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict

from app.kg.domains import DOMAIN_TAXONOMY, get_domain_by_name
from app.kg.categories import CATEGORIES, UPPER_ONTOLOGY, get_upper_ontology_by_category
from app.kg.client import get_neo4j_driver

logger = logging.getLogger(__name__)

# Token TTL for private progress link (minutes)
PROGRESS_VIEW_TOKEN_TTL_MINUTES = 60


def _get_view_secret() -> str:
    """Secret for signing progress view tokens (ADMIN_API_KEY or GRAPH_VIEW_SECRET)."""
    return (os.getenv("GRAPH_VIEW_SECRET") or os.getenv("ADMIN_API_KEY") or "").strip()


def create_progress_view_token(chat_id: str, expiry_minutes: int = PROGRESS_VIEW_TOKEN_TTL_MINUTES) -> Optional[str]:
    """
    Create a short-lived token so only the user who received the link can open the progress dashboard.
    Returns None if no secret is configured.
    """
    secret = _get_view_secret()
    if not secret:
        return None
    payload = json.dumps({
        "chat_id": str(chat_id),
        "exp": int(time.time()) + expiry_minutes * 60,
    }, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def validate_progress_view_token(token: str) -> Optional[str]:
    """
    Validate token; return chat_id if valid and not expired, else None.
    """
    if not token or "." not in token:
        return None
    secret = _get_view_secret()
    if not secret:
        return None
    payload_b64, sig = token.rsplit(".", 1)
    try:
        payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64_padded.encode()).decode()
        data = json.loads(payload)
    except Exception:
        return None
    expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    if data.get("exp", 0) < int(time.time()):
        return None
    return str(data.get("chat_id", ""))


def get_progress_stats() -> Dict[str, Any]:
    """
    Query Neo4j for node counts by domain; aggregate by category and upper ontology.
    
    Returns:
        Dict with:
        - by_upper_ontology: { "entities": N, "relations": N, "events_processes": N }
        - by_category: { "mathematics": N, ... }
        - by_domain: { "Algebra I": N, ... }
        - total: int
    """
    driver = get_neo4j_driver()
    by_domain: Dict[str, int] = defaultdict(int)
    
    if driver:
        try:
            with driver.session() as session:
                # Count nodes that have a domain property (Concepts, etc.)
                result = session.run("""
                    MATCH (n)
                    WHERE n.domain IS NOT NULL AND trim(n.domain) <> ''
                    RETURN n.domain AS domain, count(n) AS count
                """)
                for record in result:
                    domain = (record.get("domain") or "").strip()
                    if domain:
                        by_domain[domain] += record.get("count", 0)
        except Exception as e:
            logger.warning(f"KG progress query failed: {e}")
    
    # Aggregate by category (map domain -> category via taxonomy)
    by_category: Dict[str, int] = defaultdict(int)
    for domain_name, count in by_domain.items():
        info = get_domain_by_name(domain_name)
        cat = (info or {}).get("category_key") or "interdisciplinary"
        by_category[cat] += count
    
    # Aggregate by upper ontology
    by_upper: Dict[str, int] = defaultdict(int)
    for cat_key, count in by_category.items():
        ont = get_upper_ontology_by_category(cat_key)
        if ont:
            by_upper[ont] += count
        else:
            by_upper["events_processes"] += count  # default
    
    total = sum(by_domain.values())
    
    return {
        "by_upper_ontology": dict(by_upper),
        "by_category": dict(by_category),
        "by_domain": dict(by_domain),
        "total": total,
    }


def get_progress_tree(stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build a nested tree for the drill-down dashboard:
    Level 1: Upper ontology (entities, relations, events_processes)
    Level 2: Categories under each ontology
    Level 3: Domains under each category (with counts)
    """
    if stats is None:
        stats = get_progress_stats()
    by_domain = stats.get("by_domain", {})
    by_category = stats.get("by_category", {})

    def domain_count_for_category(cat_key: str) -> List[Dict[str, Any]]:
        out = []
        for dname, count in by_domain.items():
            info = get_domain_by_name(dname)
            if info and info.get("category_key") == cat_key:
                out.append({"label": dname, "count": count, "children": []})
        out.sort(key=lambda x: -x["count"])
        return out

    children_l1 = []
    for ont_key, ont_data in UPPER_ONTOLOGY.items():
        cat_keys = ont_data.get("categories", [])
        cat_children = []
        for ck in cat_keys:
            if ck not in CATEGORIES:
                continue
            cat_label = CATEGORIES[ck].get("label", ck)
            domains = domain_count_for_category(ck)
            cat_children.append({
                "label": cat_label,
                "key": ck,
                "count": by_category.get(ck, 0),
                "children": domains,
            })
        count = sum(by_category.get(ck, 0) for ck in cat_keys if ck in CATEGORIES)
        children_l1.append({
            "label": ont_data.get("label", ont_key),
            "key": ont_key,
            "count": count,
            "children": cat_children,
        })

    return {
        "total": stats.get("total", 0),
        "label": "Knowledge Graph",
        "children": children_l1,
    }


def _render_bar_chart(
    labels: List[str],
    values: List[int],
    title: str,
    xlabel: str = "Count",
) -> bytes:
    """Render a horizontal bar chart to PNG bytes."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed, cannot render progress images")
        return b""
    
    fig, ax = plt.subplots(figsize=(8, max(4, len(labels) * 0.35)))
    ax.barh(labels, values, color="steelblue", edgecolor="navy", alpha=0.8)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=12)
    ax.invert_yaxis()
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_progress_images(stats: Optional[Dict[str, Any]] = None) -> List[Tuple[str, bytes]]:
    """
    Generate one image per major hierarchy level.
    
    Returns:
        List of (caption, png_bytes) for Level 1 (upper ontology), Level 2 (categories),
        and Level 3 (one image per category showing domains).
    """
    if stats is None:
        stats = get_progress_stats()
    
    images: List[Tuple[str, bytes]] = []
    
    # Level 1: Upper ontology (always show all three, 0 if no data)
    upper = stats.get("by_upper_ontology", {})
    ont_keys = ["entities", "relations", "events_processes"]
    ont_labels = {
        "entities": "Entities (Objects)",
        "relations": "Relations",
        "events_processes": "Events/Processes",
    }
    labels = [ont_labels.get(k, k.replace("_", " ").title()) for k in ont_keys]
    values = [upper.get(k, 0) for k in ont_keys]
    png = _render_bar_chart(
        labels, values,
        title="KG Progress — Level 1: Upper Ontology",
        xlabel="Nodes",
    )
    if png:
        images.append(("Level 1: Upper Ontology", png))
    
    # Level 2: Categories (all categories, count 0 if no data)
    by_cat = stats.get("by_category", {})
    if CATEGORIES:
        cat_display = []
        cat_counts = []
        for ck in CATEGORIES:
            cat_display.append((CATEGORIES[ck].get("label", ck) or ck)[:30])
            cat_counts.append(by_cat.get(ck, 0))
        png = _render_bar_chart(
            cat_display, cat_counts,
            title="KG Progress — Level 2: Categories",
            xlabel="Nodes",
        )
        if png:
            images.append(("Level 2: Categories", png))
    
    # Level 3: Domains per category (one image per category that has data)
    by_domain = stats.get("by_domain", {})
    for cat_key in CATEGORIES:
        domain_names = DOMAIN_TAXONOMY.get(cat_key, {})
        # Domains in KG that belong to this category
        counts_in_cat = []
        labels_in_cat = []
        for dname, count in by_domain.items():
            info = get_domain_by_name(dname)
            if info and info.get("category_key") == cat_key:
                labels_in_cat.append(dname[:28])
                counts_in_cat.append(count)
        if not labels_in_cat:
            continue
        # Sort by count descending, take top 20
        paired = sorted(zip(counts_in_cat, labels_in_cat), reverse=True)[:20]
        labels_in_cat = [l for _, l in paired]
        counts_in_cat = [c for c, _ in paired]
        cat_label = CATEGORIES[cat_key].get("label", cat_key)
        png = _render_bar_chart(
            labels_in_cat, counts_in_cat,
            title=f"KG Progress — Level 3: {cat_label[:40]}",
            xlabel="Nodes",
        )
        if png:
            images.append((f"Level 3: {cat_label}", png))
    
    return images


def get_progress_summary_text(stats: Optional[Dict[str, Any]] = None) -> str:
    """Short text summary of progress (for caption)."""
    if stats is None:
        stats = get_progress_stats()
    total = stats.get("total", 0)
    by_cat = stats.get("by_category", {})
    n_cats = len([c for c in by_cat if by_cat[c] > 0])
    return f"Knowledge graph: {total} nodes across {n_cats} categories."
