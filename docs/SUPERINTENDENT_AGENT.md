# Superintendent agent

The **superintendent** is the top-level agent that owns the overarching mission. It constantly monitors, improves, and updates the other agents, and **comes to you for key decisions** at crucial intersections.

---

## 1. Overarching mission

The superintendent’s mission is defined in `app/mission.py` and summarized as:

- **Build and maintain a decision-grade knowledge graph** using free secondary sources → primary identifiers (DOI, arXiv, etc.) to secure claims.
- **Expand the graph autonomously** across domains (discovery, primary IDs, optional fetch/ingest).
- **Monitor** agents, queue, cost, and KG health; **improve** agents when gaps or failures are detected.
- **Surface crucial decisions** to you: approve/reject KG writes, approve/reject code changes, resolve contradictions, prioritize domains, handle budget caps.

This mission is what the superintendent “knows”; routing, expansion, and approval flows are aligned with it.

---

## 2. What the superintendent does

| Activity | What it does |
|----------|----------------|
| **Monitoring** | Tracks KG progress, queue (stuck, DLQ), cost vs budget, agent errors and rate limits. Can run `/status`, `/graph`, and telemetry internally or on demand. |
| **Improving** | When it detects gaps (e.g. “source gatherer often returns 0 for niche domains”), it can propose improvements (e.g. expanded queries, lower threshold) via the improvement agent; you Approve/Reject. |
| **Updating agents** | Applies approved code changes, config, or pipeline tweaks. Improvement flow is the main path; future: auto-tune thresholds from feedback. |
| **Autonomous expansion** | Runs expansion cycles (e.g. `/expand`) that discover sources across domains and report back; does not require you to “gather for X” one by one. |
| **Key decisions** | At crucial intersections, it stops and asks you instead of auto-deciding. |

---

## 3. Crucial intersections (when it comes to you)

These are the decision types where the superintendent **must** get your input (defined in `app/mission.CRUCIAL_DECISION_TYPES`):

| Decision type | Meaning |
|---------------|--------|
| **kg_write** | Commit or reject proposed KG changes (nodes/edges). Already implemented: writer → approval → commit/reject. |
| **code_change** | Apply or reject proposed code/agent improvements. Already implemented: improvement agent → approval → apply/reject. |
| **contradiction_resolution** | Conflicting claims detected; how to resolve (flag both, prefer new, prefer existing). Implemented in dedup/triage; can surface as “Key decision: resolve contradiction” with options. |
| **domain_priority** | Which domains to expand next when multiple candidates exist. Can surface after scout or expansion: “I have 10 candidate domains; which batch should I expand?” |
| **budget_cap** | Budget limit approached; pause expansion or continue with reduced scope. Can surface when cost envelope hits cap. |
| **stuck_tasks** | Tasks stuck in queue; retry, skip, or triage. Implemented as runbooks; can surface “N tasks stuck; [Retry] [Skip] [Triage]”. |

The superintendent sets `crucial_decision_type` (and optional `crucial_decision_context`) in state when it needs one of these; the Telegram layer shows "🔑 **Key decision: …**" and the appropriate buttons or options. When a key decision is surfaced, the system **continues mission work in the meantime**: with durable queue, a `mission_continue` task is enqueued and the worker runs one expansion cycle (source discovery), then sends "📈 **Mission continued while you decide:** discovered N sources across M domain(s)." Without the queue, an in-process background task runs the same expansion. See `app/queue/mission_continue.py` and `app/queue/worker.py` (task type `mission_continue`).

---

## 4. Where it’s implemented

| Component | Purpose |
|-----------|---------|
| `app/mission.py` | `OVERARCHING_MISSION`, `CRUCIAL_DECISION_TYPES`, `get_mission_summary()`, `get_crucial_decision_label()`. |
| `app/graph/state.py` | Optional `crucial_decision_type`, `crucial_decision_context` so approval flows can label the decision. |
| `app/graph/supervisor.py` | Superintendent graph: uses mission in help text; sets `crucial_decision_type` when routing to approval (kg_write vs code_change). |
| `app/main.py` | When sending approval message, prefixes with "Key decision: …" using `crucial_decision_type`; triggers mission_continue after sending. |
| `app/queue/mission_continue.py` | Runs expansion cycle while key decision is pending; sends "Mission continued while you decide" update to chat. |
| `app/queue/worker.py` | Processes graph_run and mission_continue; enqueues mission_continue when sending approval. |
| `docs/SUPERINTENDENT_AGENT.md` | This doc. |

---

## 5. Making the mission clear to the superintendent

- **In code:** The superintendent graph imports `app.mission` and uses `get_mission_summary()` in the help node and in any prompt that describes the agent’s role (e.g. improvement agent system prompt).
- **In state:** When the graph needs a key decision, it sets `crucial_decision_type` (and optionally `crucial_decision_context`) so the UI and logs show “Key decision: Commit KG changes?” vs “Key decision: Apply code changes?”.
- **In docs:** This file and `ARCHITECTURE_AND_MOVING_PARTS.md` reference the superintendent and mission so the behavior is explicit.

Future: a dedicated “superintendent loop” (background or cron) that periodically checks “what should I do next?” (expand, improve, triage) and either acts or surfaces a crucial decision to the user.
