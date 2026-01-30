# Sample run analysis (terminal output)

Analysis of running `python scripts/sample_domain_concepts.py --live` for **Algebra I** and **Linear Algebra**.

---

## What happened

### 1. Environment / shell

- **`cd: no such directory: ag-agent-manager`** — Script was run from a parent dir (e.g. `LUMI_3`); the script does not `cd` into `ag-agent-manager`, so either run from inside `ag-agent-manager` or use `python ag-agent-manager/scripts/sample_domain_concepts.py`.
- **`zsh: unknown sort specifier`** / **`zsh: unknown username 'e'`** / **`zsh: command not found: #`** — Likely from copy-pasting multi-line commands or a line starting with `#` into the shell. Run the script as a single command:  
  `python scripts/sample_domain_concepts.py --live --domain "Linear Algebra"`

### 2. Taxonomy

- **"Generated taxonomy incomplete (16 domains), using embedded taxonomy"** — `domain_taxonomy_generated` has only 16 domains, so the code falls back to the embedded taxonomy (287 domains). Both "Algebra I" and "Linear Algebra" exist there; discovery still runs.

### 3. LLM / query generation

- **"No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY"** — Query enhancement for discovery is skipped.
- **"LLM query generation failed ... using basic queries only"** — Search queries are the raw domain name (e.g. "Algebra I", "Linear Algebra") instead of LLM-expanded queries. Discovery still uses these.

### 4. Semantic Scholar API

- **Algebra I:** **429 (Too Many Requests)** — Rate limited. No papers from Semantic Scholar for that run.
- **Linear Algebra:** **400 (Bad Request)** — Request rejected (e.g. query format or API change). No papers from Semantic Scholar for that run.

So in both runs, **academic** results came from **arXiv** (and possibly OpenAlex when it’s used), not from Semantic Scholar.

### 5. Discovery results

- **Algebra I (live):** 8 sources — OpenStax, MIT OCW (×2), Khan Academy, plus 4 academic/preprints (one generic “Social network analysis…”, three arXiv with IDs).
- **Linear Algebra (live):** 8 sources — OpenStax, MIT OCW, Khan Academy, plus 5 arXiv preprints (e.g. “Non-linear positive maps…”, “Grüss type inequalities…”, “Linear Mappings of Free Algebra”).

So **live discovery did run** and returned real sources; educational sources (OpenStax, MIT OCW, Khan) plus arXiv preprints.

### 6. Primary identifiers

- **arXiv preprints:** Show **arxiv: 25xx.xxxxx** or **arxiv: 1xxx.xxxx** — `canonicalize_primary_identifiers` correctly extracted arXiv IDs from source `id` or URL.
- **OpenStax, MIT OCW, Khan Academy:** Show **(none)** — These providers only set `url` (and sometimes `id` like `SRC:openstax_algebra`). Current canonicalization only derives **DOI** and **arXiv**; it does not yet treat stable OER URLs as primary identifiers, so educational sources get no identifier in the table.

### 7. Concepts and claims

- Concepts and claims are the **same** for both domains — they come from the script’s canned **Algebra I** sample (linear equation, quadratic function, slope, systems). The script does not yet switch to domain-specific concepts/claims for "Linear Algebra" (e.g. vector space, eigenvalue).

---

## Summary

| Item | Status |
|------|--------|
| Script runs from project root | OK (no need to be in `ag-agent-manager` if path is correct) |
| Live discovery | OK — real sources returned |
| Taxonomy fallback | OK — embedded taxonomy used |
| LLM query enhancement | Skipped — no API key; basic queries used |
| Semantic Scholar | 429 / 400 — no S2 results in these runs |
| arXiv | OK — preprints returned with **arxiv** IDs |
| OpenStax / MIT OCW / Khan | OK — returned; identifiers **(none)** until we add URL-based ids |
| Claim tiers / p_error / evidence_summary | OK — displayed correctly |

---

## Recommendations

1. **Run from the right directory**  
   From repo root:  
   `cd ag-agent-manager && python scripts/sample_domain_concepts.py --live --domain "Linear Algebra"`  
   Or from `ag-agent-manager`:  
   `python scripts/sample_domain_concepts.py --live --domain "Linear Algebra"`

2. **Optional: set LLM API key**  
   Export `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` so query generation can expand "Linear Algebra" into multiple search queries and improve discovery.

3. **Semantic Scholar**  
   - 429: add backoff / fewer concurrent requests or retry with exponential backoff.  
   - 400: check query encoding and API docs (e.g. allowed characters, required params).

4. **Educational sources (OpenStax, Khan, MIT OCW)**  
   Add URL-based primary identifiers in `canonicalize_primary_identifiers` (e.g. normalize `openstax.org`, `khanacademy.org`, `ocw.mit.edu` URLs and store as `url` or `source_id` in `identifiers`) so they show a stable id instead of **(none)**.

5. **Domain-specific concepts/claims**  
   For `--live --domain "Linear Algebra"`, optionally use different canned concepts/claims (e.g. vector space, eigenvalue, linear map) or add a small mapping from domain name → sample concepts so the output matches the requested domain.

Implementing (4) and (5) in code next is straightforward; (2) and (3) are env/API and rate-limit tuning.
