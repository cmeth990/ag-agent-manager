"""
Domain Taxonomy and Domain Node Generation
Extracts domains from taxonomy and creates domain nodes linked to categories.
"""
import logging
from typing import Dict, Any, List, Optional
from app.kg.knowledge_base import generate_id, NODE_TYPES
from app.kg.categories import (
    CATEGORIES, get_category_by_domain, get_upper_ontology_by_category, 
    get_orp_role_by_category
)
from app.kg.hypernode import infer_scale_from_content

logger = logging.getLogger(__name__)

# Domain taxonomy - extracted from ComprehensiveDomainTaxonomy.js
# Try to import full taxonomy if available, otherwise use comprehensive embedded taxonomy
try:
    from app.kg.domain_taxonomy_generated import DOMAIN_TAXONOMY as FULL_TAXONOMY
    # Only use if it has substantial content (more than just a few domains)
    total_domains = sum(len(domains) for domains in FULL_TAXONOMY.values() if isinstance(domains, dict))
    if total_domains > 100:  # Use generated if it has >100 domains
        DOMAIN_TAXONOMY = FULL_TAXONOMY
        logger.info(f"Loaded full domain taxonomy with {total_domains} domains")
    else:
        logger.warning(f"Generated taxonomy incomplete ({total_domains} domains), using embedded taxonomy")
        # Fall through to embedded taxonomy below
        raise ImportError("Incomplete taxonomy")
except ImportError:
    logger.info("Using comprehensive embedded domain taxonomy")
    # Comprehensive embedded taxonomy with all 12 categories and ~287 domains
    DOMAIN_TAXONOMY = {
    "mathematics": {
        "Arithmetic": {"gradebands": ["K-2", "3-5"], "difficulty": "beginner"},
        "Pre-Algebra": {"gradebands": ["6-8"], "difficulty": "beginner"},
        "Algebra I": {"gradebands": ["6-8", "9-12"], "difficulty": "intermediate"},
        "Algebra II": {"gradebands": ["9-12"], "difficulty": "intermediate"},
        "Geometry": {"gradebands": ["6-8", "9-12"], "difficulty": "intermediate"},
        "Trigonometry": {"gradebands": ["9-12"], "difficulty": "intermediate"},
        "Pre-Calculus": {"gradebands": ["9-12"], "difficulty": "advanced"},
        "Calculus I": {"gradebands": ["9-12", "college"], "difficulty": "advanced"},
        "Calculus II": {"gradebands": ["college"], "difficulty": "advanced"},
        "Calculus III": {"gradebands": ["college"], "difficulty": "advanced"},
        "Multivariable Calculus": {"gradebands": ["college"], "difficulty": "advanced"},
        "Differential Equations": {"gradebands": ["college"], "difficulty": "advanced"},
        "Linear Algebra": {"gradebands": ["college"], "difficulty": "advanced"},
        "Abstract Algebra": {"gradebands": ["college"], "difficulty": "advanced"},
        "Real Analysis": {"gradebands": ["college"], "difficulty": "advanced"},
        "Complex Analysis": {"gradebands": ["college"], "difficulty": "advanced"},
        "Topology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Number Theory": {"gradebands": ["college"], "difficulty": "advanced"},
        "Discrete Mathematics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Combinatorics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Graph Theory": {"gradebands": ["college"], "difficulty": "advanced"},
        "Statistics": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Probability": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Mathematical Statistics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Applied Statistics": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Numerical Analysis": {"gradebands": ["college"], "difficulty": "advanced"},
        "Optimization": {"gradebands": ["college"], "difficulty": "advanced"},
        "Game Theory": {"gradebands": ["college"], "difficulty": "advanced"},
        "Operations Research": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Computer Science Fundamentals": {"gradebands": ["9-12", "college"], "difficulty": "beginner"},
        "Programming": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Data Structures": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Algorithms": {"gradebands": ["college"], "difficulty": "advanced"},
        "Computer Architecture": {"gradebands": ["college"], "difficulty": "advanced"},
        "Operating Systems": {"gradebands": ["college"], "difficulty": "advanced"},
        "Databases": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Computer Networks": {"gradebands": ["college"], "difficulty": "advanced"},
        "Software Engineering": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Cybersecurity": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Artificial Intelligence": {"gradebands": ["college"], "difficulty": "advanced"},
        "Machine Learning": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Data Science": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Web Development": {"gradebands": ["9-12", "college", "professional"], "difficulty": "intermediate"},
        "Mobile Development": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
    },
    "natural_sciences": {
        "Life Science": {"gradebands": ["3-5", "6-8"], "difficulty": "beginner"},
        "Biology": {"gradebands": ["9-12"], "difficulty": "intermediate"},
        "General Biology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Cell Biology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Molecular Biology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Genetics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Microbiology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Immunology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Anatomy": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Physiology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Neuroscience": {"gradebands": ["college"], "difficulty": "advanced"},
        "Ecology": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Evolutionary Biology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Botany": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Zoology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Marine Biology": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Biochemistry": {"gradebands": ["college"], "difficulty": "advanced"},
        "Chemistry": {"gradebands": ["6-8", "9-12"], "difficulty": "intermediate"},
        "General Chemistry": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Organic Chemistry": {"gradebands": ["college"], "difficulty": "advanced"},
        "Inorganic Chemistry": {"gradebands": ["college"], "difficulty": "advanced"},
        "Physical Chemistry": {"gradebands": ["college"], "difficulty": "advanced"},
        "Analytical Chemistry": {"gradebands": ["college"], "difficulty": "advanced"},
        "Environmental Chemistry": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Physical Science": {"gradebands": ["3-5", "6-8"], "difficulty": "beginner"},
        "Physics": {"gradebands": ["9-12"], "difficulty": "intermediate"},
        "General Physics": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Classical Mechanics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Electromagnetism": {"gradebands": ["college"], "difficulty": "advanced"},
        "Thermodynamics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Quantum Mechanics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Relativity": {"gradebands": ["college"], "difficulty": "advanced"},
        "Optics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Nuclear Physics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Particle Physics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Astrophysics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Condensed Matter Physics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Earth Science": {"gradebands": ["3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Geology": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Meteorology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Oceanography": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Astronomy": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Cosmology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Planetary Science": {"gradebands": ["college"], "difficulty": "advanced"},
        "Environmental Science": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Climate Science": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
    },
    "engineering": {
        "Engineering Fundamentals": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Mechanical Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Electrical Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Civil Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Chemical Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Biomedical Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Aerospace Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Computer Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Environmental Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Materials Science": {"gradebands": ["college"], "difficulty": "advanced"},
        "Industrial Engineering": {"gradebands": ["college"], "difficulty": "advanced"},
        "Systems Engineering": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Robotics": {"gradebands": ["9-12", "college"], "difficulty": "advanced"},
        "Nanotechnology": {"gradebands": ["college"], "difficulty": "advanced"},
    },
    "social_sciences": {
        "Psychology": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Developmental Psychology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Cognitive Psychology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Social Psychology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Abnormal Psychology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Clinical Psychology": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Educational Psychology": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Sociology": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Anthropology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Cultural Anthropology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Archaeology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Criminology": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Urban Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Civics": {"gradebands": ["6-8", "9-12"], "difficulty": "beginner"},
        "Government": {"gradebands": ["9-12"], "difficulty": "intermediate"},
        "Political Science": {"gradebands": ["college"], "difficulty": "intermediate"},
        "International Relations": {"gradebands": ["college"], "difficulty": "advanced"},
        "Public Policy": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Comparative Politics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Geography": {"gradebands": ["3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Human Geography": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Physical Geography": {"gradebands": ["college"], "difficulty": "intermediate"},
        "GIS and Cartography": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
    },
    "history": {
        "Ancient History": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Medieval History": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Modern History": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "World History": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "European History": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Asian History": {"gradebands": ["college"], "difficulty": "intermediate"},
        "African History": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Latin American History": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Middle Eastern History": {"gradebands": ["college"], "difficulty": "intermediate"},
        "US History": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "American Revolution": {"gradebands": ["6-8", "9-12"], "difficulty": "intermediate"},
        "Civil War Era": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "US Constitutional History": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Art History": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Military History": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Economic History": {"gradebands": ["college"], "difficulty": "advanced"},
        "History of Science": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Religious History": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Cultural Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Gender Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Ethnic Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Area Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
    },
    "languages_literature": {
        "English Language Arts": {"gradebands": ["K-2", "3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Reading": {"gradebands": ["K-2", "3-5", "6-8"], "difficulty": "beginner"},
        "Writing": {"gradebands": ["K-2", "3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Grammar": {"gradebands": ["3-5", "6-8", "9-12"], "difficulty": "intermediate"},
        "Composition": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Rhetoric": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Creative Writing": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Technical Writing": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Literature": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "American Literature": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "British Literature": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "World Literature": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Contemporary Literature": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Poetry": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Drama": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Literary Theory": {"gradebands": ["college"], "difficulty": "advanced"},
        "Comparative Literature": {"gradebands": ["college"], "difficulty": "advanced"},
        "Linguistics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Phonetics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Syntax": {"gradebands": ["college"], "difficulty": "advanced"},
        "Semantics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Sociolinguistics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Spanish": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "beginner"},
        "French": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "beginner"},
        "German": {"gradebands": ["9-12", "college"], "difficulty": "beginner"},
        "Chinese (Mandarin)": {"gradebands": ["9-12", "college"], "difficulty": "beginner"},
        "Japanese": {"gradebands": ["9-12", "college"], "difficulty": "beginner"},
        "Italian": {"gradebands": ["9-12", "college"], "difficulty": "beginner"},
        "Latin": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Arabic": {"gradebands": ["college"], "difficulty": "beginner"},
        "Russian": {"gradebands": ["college"], "difficulty": "beginner"},
        "Portuguese": {"gradebands": ["college"], "difficulty": "beginner"},
        "Korean": {"gradebands": ["college"], "difficulty": "beginner"},
        "ESL/English as Second Language": {"gradebands": ["K-2", "3-5", "6-8", "9-12", "college"], "difficulty": "beginner"},
    },
    "arts": {
        "Art": {"gradebands": ["K-2", "3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Drawing": {"gradebands": ["3-5", "6-8", "9-12", "college"], "difficulty": "beginner"},
        "Painting": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Sculpture": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Photography": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Digital Art": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Graphic Design": {"gradebands": ["9-12", "college", "professional"], "difficulty": "intermediate"},
        "Animation": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Film Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Architecture": {"gradebands": ["college"], "difficulty": "advanced"},
        "Music": {"gradebands": ["K-2", "3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Music Theory": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Music History": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Music Composition": {"gradebands": ["college"], "difficulty": "advanced"},
        "Music Performance": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Vocal Music": {"gradebands": ["3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Instrumental Music": {"gradebands": ["3-5", "6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Theater": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Drama": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Dance": {"gradebands": ["K-2", "3-5", "6-8", "9-12", "college"], "difficulty": "beginner"},
        "Film Production": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
    },
    "business_economics": {
        "Economics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Microeconomics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Macroeconomics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "International Economics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Development Economics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Econometrics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Behavioral Economics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Business": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Accounting": {"gradebands": ["9-12", "college", "professional"], "difficulty": "intermediate"},
        "Finance": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Marketing": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Management": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Entrepreneurship": {"gradebands": ["9-12", "college", "professional"], "difficulty": "intermediate"},
        "Business Analytics": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Supply Chain Management": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Human Resources": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Organizational Behavior": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Business Ethics": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Real Estate": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Law": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Constitutional Law": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Criminal Law": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Civil Law": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Business Law": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "International Law": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Environmental Law": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
    },
    "health_medicine": {
        "Health": {"gradebands": ["K-2", "3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Physical Education": {"gradebands": ["K-2", "3-5", "6-8", "9-12"], "difficulty": "beginner"},
        "Nutrition": {"gradebands": ["6-8", "9-12", "college"], "difficulty": "intermediate"},
        "Public Health": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Health Policy": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Epidemiology": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Medicine": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Nursing": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Pharmacology": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Medical Technology": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Dentistry": {"gradebands": ["professional"], "difficulty": "advanced"},
        "Veterinary Medicine": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Physical Therapy": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Occupational Therapy": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
    },
    "philosophy_religion": {
        "Philosophy": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Ethics": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Logic": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Epistemology": {"gradebands": ["college"], "difficulty": "advanced"},
        "Metaphysics": {"gradebands": ["college"], "difficulty": "advanced"},
        "Political Philosophy": {"gradebands": ["college"], "difficulty": "advanced"},
        "Philosophy of Science": {"gradebands": ["college"], "difficulty": "advanced"},
        "Philosophy of Mind": {"gradebands": ["college"], "difficulty": "advanced"},
        "Ancient Philosophy": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Modern Philosophy": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Eastern Philosophy": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Religion": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Comparative Religion": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Religious Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Theology": {"gradebands": ["college"], "difficulty": "advanced"},
    },
    "vocational": {
        "Career and Technical Education": {"gradebands": ["9-12"], "difficulty": "intermediate"},
        "Culinary Arts": {"gradebands": ["9-12", "professional"], "difficulty": "intermediate"},
        "Automotive Technology": {"gradebands": ["9-12", "professional"], "difficulty": "intermediate"},
        "Construction Trades": {"gradebands": ["9-12", "professional"], "difficulty": "intermediate"},
        "Welding": {"gradebands": ["9-12", "professional"], "difficulty": "intermediate"},
        "Electrical Technology": {"gradebands": ["9-12", "professional"], "difficulty": "intermediate"},
        "HVAC": {"gradebands": ["professional"], "difficulty": "intermediate"},
        "Cosmetology": {"gradebands": ["professional"], "difficulty": "beginner"},
        "Agriculture": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Horticulture": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Fashion Design": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Interior Design": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
    },
    "interdisciplinary": {
        "Environmental Studies": {"gradebands": ["9-12", "college"], "difficulty": "intermediate"},
        "Sustainability": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Data Science": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Cognitive Science": {"gradebands": ["college"], "difficulty": "advanced"},
        "Information Science": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Communication Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Media Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Gender and Sexuality Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Disability Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Critical Race Theory": {"gradebands": ["college"], "difficulty": "advanced"},
        "Peace and Conflict Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Global Studies": {"gradebands": ["college"], "difficulty": "intermediate"},
        "Library Science": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Education": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
        "Special Education": {"gradebands": ["college", "professional"], "difficulty": "advanced"},
        "Instructional Design": {"gradebands": ["college", "professional"], "difficulty": "intermediate"},
    },
}


def create_domain_node(
    domain_name: str,
    category_key: str,
    gradebands: List[str],
    difficulty: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a domain node (Concept at meso scale) with full metadata.
    
    Args:
        domain_name: Name of the domain
        category_key: Category this domain belongs to
        gradebands: List of grade bands (e.g., ["9-12", "college"])
        difficulty: Difficulty level (beginner, intermediate, advanced)
        description: Optional description
    
    Returns:
        Domain node dict ready for KG insertion
    """
    # Get category and upper ontology info
    upper_ontology = get_upper_ontology_by_category(category_key)
    orp_role = get_orp_role_by_category(category_key)
    
    # Create domain as Concept node at meso scale
    domain_id = generate_id("Concept")
    
    domain_node = {
        "id": domain_id,
        "label": "Concept",
        "properties": {
            "id": domain_id,
            "name": domain_name,
            "domain": domain_name,  # Domain is itself
            "description": description or f"Domain: {domain_name}",
            "category": category_key,
            "upper_ontology": upper_ontology,
            "orp_role": orp_role,
            "scale": "meso",  # Domains are at meso scale
            "level": "domain",
            "gradebands": gradebands,
            "difficulty": difficulty,
            "metadata": {
                "domain_type": "knowledge_domain",
                "category_key": category_key,
                "gradebands": gradebands,
                "difficulty": difficulty
            }
        }
    }
    
    logger.debug(f"Created domain node: {domain_name} ({category_key})")
    return domain_node


def create_domain_structure_for_category(
    category_key: str,
    category_hypernode_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create all domain nodes for a specific category.
    
    Args:
        category_key: Category key (e.g., "mathematics")
        category_hypernode_id: Optional actual category hypernode ID from KG
    
    Returns:
        Dict with nodes and edges for this category's domains
    """
    if category_key not in DOMAIN_TAXONOMY:
        logger.warning(f"Category {category_key} not found in domain taxonomy")
        return {"nodes": [], "edges": []}
    
    domains = DOMAIN_TAXONOMY[category_key]
    nodes = []
    edges = []
    
    # Use provided ID or expected format
    if not category_hypernode_id:
        category_hypernode_id = f"CAT:{category_key}"
    
    for domain_name, domain_config in domains.items():
        # Create domain node
        domain_node = create_domain_node(
            domain_name=domain_name,
            category_key=category_key,
            gradebands=domain_config.get("gradebands", []),
            difficulty=domain_config.get("difficulty", "intermediate")
        )
        nodes.append(domain_node)
        
        # Create NESTED_IN edge from domain to category
        edges.append({
            "from": domain_node["id"],
            "to": category_hypernode_id,
            "type": "NESTED_IN",
            "properties": {
                "nesting_depth": 2,
                "scale": "meso",
                "domain_name": domain_name,
                "category_key": category_key
            }
        })
    
    logger.info(f"Created {len(nodes)} domain nodes for category {category_key}")
    return {"nodes": nodes, "edges": edges}


def create_all_domains(category_hypernode_ids: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Create all domain nodes for all categories.
    
    Args:
        category_hypernode_ids: Optional dict mapping category_key to actual hypernode ID
    
    Returns:
        Dict with all nodes, edges, and metadata
    """
    all_nodes = []
    all_edges = []
    domain_count_by_category = {}
    
    for category_key in CATEGORIES.keys():
        if category_key in DOMAIN_TAXONOMY:
            # Get actual category hypernode ID if provided
            cat_hypernode_id = None
            if category_hypernode_ids and category_key in category_hypernode_ids:
                cat_hypernode_id = category_hypernode_ids[category_key]
            
            structure = create_domain_structure_for_category(
                category_key,
                category_hypernode_id=cat_hypernode_id
            )
            all_nodes.extend(structure["nodes"])
            all_edges.extend(structure["edges"])
            domain_count_by_category[category_key] = len(structure["nodes"])
        else:
            logger.warning(f"No domains found for category {category_key}")
            domain_count_by_category[category_key] = 0
    
    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "metadata": {
            "total_domains": len(all_nodes),
            "total_edges": len(all_edges),
            "domains_by_category": domain_count_by_category
        }
    }


def get_domain_by_name(domain_name: str) -> Optional[Dict[str, Any]]:
    """
    Get domain information by name.
    Exact match first; then fuzzy match (e.g. "Algebra" -> "Algebra I").
    
    Args:
        domain_name: Name of the domain
    
    Returns:
        Dict with domain info or None
    """
    name_lower = domain_name.strip().lower()
    for category_key, domains in DOMAIN_TAXONOMY.items():
        if domain_name in domains:
            domain_config = domains[domain_name]
            return {
                "domain_name": domain_name,
                "category_key": category_key,
                "gradebands": domain_config.get("gradebands", []),
                "difficulty": domain_config.get("difficulty", "intermediate"),
                "upper_ontology": get_upper_ontology_by_category(category_key),
                "orp_role": get_orp_role_by_category(category_key)
            }
    # Fuzzy: prefer domain that starts with query (e.g. "Algebra" -> "Algebra I" not "Pre-Algebra")
    candidates = []
    for category_key, domains in DOMAIN_TAXONOMY.items():
        for dname, domain_config in domains.items():
            d_lower = dname.lower()
            if name_lower in d_lower or d_lower in name_lower:
                candidates.append((dname, category_key, domain_config))
    if not candidates:
        return None
    # Prefer exact start match ("algebra i" starts with "algebra"), then shortest
    def rank(c):
        dname, _, _ = c
        d_lower = dname.lower()
        starts = 1 if d_lower.startswith(name_lower) or name_lower.startswith(d_lower.split()[0] if d_lower.split() else "") else 0
        return (-starts, len(dname))
    candidates.sort(key=rank)
    dname, category_key, domain_config = candidates[0]
    return {
        "domain_name": dname,
        "category_key": category_key,
        "gradebands": domain_config.get("gradebands", []),
        "difficulty": domain_config.get("difficulty", "intermediate"),
        "upper_ontology": get_upper_ontology_by_category(category_key),
        "orp_role": get_orp_role_by_category(category_key)
    }


def get_domains_by_category(category_key: str) -> List[str]:
    """
    Get all domain names for a category.
    
    Args:
        category_key: Category key
    
    Returns:
        List of domain names
    """
    if category_key in DOMAIN_TAXONOMY:
        return list(DOMAIN_TAXONOMY[category_key].keys())
    return []


def get_domains_by_gradeband(gradeband: str) -> List[Dict[str, Any]]:
    """
    Get all domains for a specific gradeband.
    
    Args:
        gradeband: Grade band (e.g., "9-12", "college")
    
    Returns:
        List of domain info dicts
    """
    domains = []
    for category_key, category_domains in DOMAIN_TAXONOMY.items():
        for domain_name, domain_config in category_domains.items():
            if gradeband in domain_config.get("gradebands", []):
                domains.append({
                    "domain_name": domain_name,
                    "category_key": category_key,
                    "gradebands": domain_config.get("gradebands", []),
                    "difficulty": domain_config.get("difficulty", "intermediate")
                })
    return domains


def get_domains_by_difficulty(difficulty: str) -> List[Dict[str, Any]]:
    """
    Get all domains for a specific difficulty level.
    
    Args:
        difficulty: Difficulty level (beginner, intermediate, advanced)
    
    Returns:
        List of domain info dicts
    """
    domains = []
    for category_key, category_domains in DOMAIN_TAXONOMY.items():
        for domain_name, domain_config in category_domains.items():
            if domain_config.get("difficulty") == difficulty:
                domains.append({
                    "domain_name": domain_name,
                    "category_key": category_key,
                    "gradebands": domain_config.get("gradebands", []),
                    "difficulty": difficulty
                })
    return domains
