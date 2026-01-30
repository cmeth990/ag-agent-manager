# Autonomous KG building and progress updates

**Goal:** The system builds the knowledge graph **intelligently on its own** and sends you **updates** about how it’s improving, instead of you asking to “gather sources for X” one domain at a time.

---

## 1. Shift from manual to autonomous

| Before | After |
|--------|------|
| You: “gather sources for Algebra”, “gather sources for Machine Learning”, … | You: “/expand” or “Build the KG” → system picks domains, discovers sources, and reports back. |
| One domain per command | One **expansion run** over multiple domains (from taxonomy or config). |
| No summary of “what improved” | **Update message**: “KG expansion: explored N domains, found M sources (X with DOI/arXiv); next steps …” |

---

## 2. How it works

1. **You trigger a run** (once or on a schedule):
   - Telegram: `/expand`, “Build the KG”, “Start building”, “How is the KG improving?”
   - Optional: cron/scheduler calls an internal endpoint to run expansion and send an update to a configured chat.

2. **System runs an expansion cycle**:
   - **Pick domains** – From taxonomy (sample across categories) or from config `EXPANSION_DOMAINS` (comma-separated). Limit per run: `EXPANSION_MAX_DOMAINS` (default 5).
   - **Discover sources** – For each domain, run `discover_sources_for_domain` (secondary APIs → primary IDs). No user prompt per domain.
   - **Aggregate** – Count sources, how many have DOI/arXiv, free vs paid, domains covered.
   - **Optional later steps** – Fetch content for top sources, run extract → link → write (with approval) for selected domains; can be added in a later phase.

3. **You get an update** (e.g. in Telegram):
   - “📈 KG expansion run: Explored [Algebra I, Machine Learning, Biology, …]. Sources discovered: 24 (18 with primary IDs). Free: 20, Paid: 4. Run /expand again for more domains, or /graph for progress.”
   - Optionally: link to progress dashboard, or “N concepts proposed (use /ingest to approve).”

---

## 3. Configuration (env)

| Variable | Purpose |
|----------|---------|
| `EXPANSION_MAX_DOMAINS` | Max domains per expansion run (default 5). |
| `EXPANSION_MAX_SOURCES_PER_DOMAIN` | Max sources to discover per domain in a run (default 10). |
| `EXPANSION_DOMAINS` | Optional comma-separated list; if set, use these instead of sampling from taxonomy. |

If `EXPANSION_DOMAINS` is not set, domains are sampled from the taxonomy (spread across categories).

---

## 4. Where it’s implemented

| Component | Purpose |
|-----------|---------|
| `app/graph/expansion.py` | `get_domains_to_expand()`, `run_expansion_cycle()`, `expansion_node()`. |
| `app/graph/supervisor.py` | Intent `autonomous_expand`, route to `expansion` node, help text for `/expand`. |

---

## 5. Optional: scheduled runs and digest

- **Scheduled expansion:** A cron job or Railway cron could call an internal endpoint (e.g. `POST /internal/expansion/run` with admin key) that runs one expansion cycle and sends the update to a fixed `ADMIN_CHAT_ID` or notification channel.
- **Daily/weekly digest:** Same runner; format a short “KG digest: added N sources across M domains this week” and send to Telegram.

These can be added on top of the on-demand `/expand` flow.
