#!/usr/bin/env python3
"""
Script to parse ComprehensiveDomainTaxonomy.js and extract all domains.
This creates a Python representation of the full domain taxonomy.
"""
import re
import json
import sys
import os

# Path to the JS taxonomy file
TAXONOMY_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src", "mapmaker", "kg", "sources", "ComprehensiveDomainTaxonomy.js"
)


def parse_js_taxonomy():
    """Parse the JavaScript taxonomy file and extract all domains."""
    if not os.path.exists(TAXONOMY_JS_PATH):
        print(f"❌ Taxonomy file not found: {TAXONOMY_JS_PATH}")
        return None
    
    with open(TAXONOMY_JS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract KNOWLEDGE_TAXONOMY object
    # This is a simplified parser - for production, use a proper JS parser
    taxonomy = {}
    
    # Find each category section
    category_pattern = r"(\w+):\s*\{\s*label:\s*'([^']+)',\s*domains:\s*\{([^}]+(?:\{[^}]+\}[^}]*)*)\s*\}\s*\}"
    
    # More robust: find category blocks
    categories = {}
    current_category = None
    current_domains = {}
    
    lines = content.split('\n')
    in_domains = False
    domain_name = None
    
    for i, line in enumerate(lines):
        # Detect category start
        if re.match(r'^\s*(\w+):\s*\{', line):
            if current_category:
                categories[current_category] = current_domains
            match = re.match(r'^\s*(\w+):\s*\{', line)
            if match:
                current_category = match.group(1)
                current_domains = {}
                in_domains = False
        
        # Detect label
        if current_category and "label:" in line:
            match = re.search(r"label:\s*'([^']+)'", line)
            if match:
                categories[current_category] = {"label": match.group(1), "domains": {}}
                current_domains = categories[current_category]["domains"]
        
        # Detect domains section
        if current_category and "domains:" in line:
            in_domains = True
        
        # Parse domain entries
        if in_domains and current_category:
            # Match: 'Domain Name': { gradebands: [...], difficulty: '...' }
            domain_match = re.search(r"'([^']+)':\s*\{", line)
            if domain_match:
                domain_name = domain_match.group(1)
                current_domains[domain_name] = {}
            
            # Match gradebands
            gradeband_match = re.search(r"gradebands:\s*\[([^\]]+)\]", line)
            if gradeband_match and domain_name:
                gradebands_str = gradeband_match.group(1)
                gradebands = [gb.strip().strip("'\"") for gb in gradebands_str.split(',')]
                current_domains[domain_name]["gradebands"] = gradebands
            
            # Match difficulty
            difficulty_match = re.search(r"difficulty:\s*'([^']+)'", line)
            if difficulty_match and domain_name:
                current_domains[domain_name]["difficulty"] = difficulty_match.group(1)
    
    # Add last category
    if current_category:
        if isinstance(categories.get(current_category), dict) and "domains" in categories[current_category]:
            categories[current_category]["domains"].update(current_domains)
        else:
            categories[current_category] = current_domains
    
    return categories


def generate_python_taxonomy(taxonomy):
    """Generate Python code for the taxonomy."""
    if not taxonomy:
        return None
    
    output = []
    output.append("# Domain Taxonomy - Auto-generated from ComprehensiveDomainTaxonomy.js")
    output.append("# Total categories: " + str(len(taxonomy)))
    output.append("")
    output.append("DOMAIN_TAXONOMY = {")
    
    for category_key, category_data in taxonomy.items():
        if isinstance(category_data, dict) and "domains" in category_data:
            domains = category_data["domains"]
            output.append(f'    "{category_key}": {{')
            
            for domain_name, domain_config in domains.items():
                gradebands = domain_config.get("gradebands", [])
                difficulty = domain_config.get("difficulty", "intermediate")
                output.append(f'        "{domain_name}": {{"gradebands": {gradebands}, "difficulty": "{difficulty}"}},')
            
            output.append("    },")
        else:
            # Fallback: treat as domains dict directly
            output.append(f'    "{category_key}": {{')
            for domain_name, domain_config in category_data.items():
                gradebands = domain_config.get("gradebands", [])
                difficulty = domain_config.get("difficulty", "intermediate")
                output.append(f'        "{domain_name}": {{"gradebands": {gradebands}, "difficulty": "{difficulty}"}},')
            output.append("    },")
    
    output.append("}")
    
    return "\n".join(output)


if __name__ == "__main__":
    print("Parsing domain taxonomy...")
    taxonomy = parse_js_taxonomy()
    
    if taxonomy:
        print(f"✅ Parsed {len(taxonomy)} categories")
        
        # Count total domains
        total_domains = 0
        for cat_data in taxonomy.values():
            if isinstance(cat_data, dict) and "domains" in cat_data:
                total_domains += len(cat_data["domains"])
            elif isinstance(cat_data, dict):
                total_domains += len(cat_data)
        
        print(f"✅ Found {total_domains} domains")
        
        # Generate Python code
        python_code = generate_python_taxonomy(taxonomy)
        
        if python_code:
            output_path = os.path.join(
                os.path.dirname(__file__),
                "..", "app", "kg", "domain_taxonomy_generated.py"
            )
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(python_code)
            print(f"✅ Generated Python taxonomy: {output_path}")
        else:
            print("❌ Failed to generate Python code")
    else:
        print("❌ Failed to parse taxonomy")
