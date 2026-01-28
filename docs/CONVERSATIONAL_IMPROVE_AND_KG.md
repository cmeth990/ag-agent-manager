# Conversational Improve Agents + Expand KG via Telegram

You can use the Telegram bot to have a conversation-style workflow to **improve the agents** and **expand the knowledge graph**, similar to working with an assistant in chat.

## What’s ready today

### 1. **Improve the agents (code changes)**

- **How:** Say `/improve ...` or write in natural language, e.g.  
  *“Improve the source gatherer to handle rate limits better”* or *“Fix the domain scout to filter out more false positives.”*
- **Flow:** The improvement agent analyzes your request, plans changes, proposes edits to files, and sends you an **Approve / Reject** message. If you approve, changes are applied; you can then use `/push` to push to GitHub.
- **Multi-turn:** The agent can use prior context from the same chat (e.g. “last time you proposed X”) when you refer to it in a follow-up message.

### 2. **Expand the knowledge graph**

- **How:** Say `/ingest topic=<topic>` or phrases like *“Expand the knowledge graph”* or *“Add knowledge about photosynthesis.”*
- **Flow:** Extract → link → write → **Approve / Reject** to commit to the KG. Topic can be parsed from the message when you use natural language.
- **Related:** Use `/gather sources for <domain>` then `/fetch content for <domain>` to pull in content before or alongside ingest.

### 3. **Combined “conversation” (improve + expand)**

- **How:** Use two types of messages in the same chat:
  - **Improve:** e.g. *“Improve the source gatherer …”* or *“Fix the extractor to …”*
  - **Expand KG:** e.g. *“Add knowledge about algebra”* or *“Expand the knowledge graph with topic photosynthesis.”*
- **State:** The graph keeps state per chat (thread_id = chat_id). So you can:
  - Improve an agent → approve → then say “Add knowledge about X” → approve → then “Also improve the fetcher to …” in the same thread.

### 4. **What the bot understands (intents)**

| You say (examples) | Intent | What happens |
|--------------------|--------|--------------|
| `/improve ...` or “Improve the source gatherer …” | `improve` | Improvement agent proposes code changes; Approve/Reject. |
| “Expand the knowledge graph” / “Add knowledge about X” | `ingest` | Extract → link → write → Approve/Reject to commit. |
| `/ingest topic=X` | `ingest` | Same as above with explicit topic. |
| `/gather sources for Algebra` | `gather_sources` | Source discovery for domain. |
| `/query …` | `query` | Query the KG. |
| “I want to have a conversation to improve and expand” | Depends on phrasing | Often routes to `ingest` or `improve`; use `/help` for commands. |

## Gaps / limitations

1. **Single intent per message**  
   A message like “Improve the agents and expand the KG” is classified as one intent (e.g. `ingest` if “expand” is detected). For both in one go, do two messages: one improve, one expand.

2. **No dedicated “conversation” node**  
   There is no single node that holds an open “conversation” and decides step-by-step (e.g. “First I’ll improve X, then we’ll add knowledge about Y”). You get there by alternating improve vs ingest messages in the same chat.

3. **Improvement context in multi-turn**  
   The improvement agent can *read* prior context from `working_notes` (e.g. “last request: …”). Writing back a short summary of what was proposed/done into `working_notes` for the next turn is partially in place; further tuning can make follow-ups like “also do Y” more reliable.

4. **LLM required**  
   Improvement agent and ingest (extractor, etc.) need an LLM (e.g. `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`). Without it, improve and ingest flows will not work as intended.

## Quick checklist: “Is the system ready?”

- **Improve agents via chat:** Yes — use `/improve` or natural-language “improve/fix the …” and Approve/Reject.
- **Expand KG via chat:** Yes — use `/ingest topic=X` or “Expand the knowledge graph” / “Add knowledge about X” and Approve/Reject.
- **Same chat, alternate improve + expand:** Yes — state is per chat; you can alternate messages.
- **Single message “improve and expand”:** Partially — one intent is chosen; prefer two messages for clarity.
- **Multi-turn “do what we discussed”:** Partially — improvement agent can use prior context; more polish possible.

So: **yes, the system is ready** to have a conversation-style workflow over Telegram to improve the agents and expand the knowledge graph, as long as you use one clear intent per message (or two messages when you want both improve and expand). Use `/help` in the bot for the exact commands and phrasing.
