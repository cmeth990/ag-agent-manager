# Pipeline test checklist

What to do next to test the pipeline end-to-end.

---

## 1. Decide where to test

| Option | When to use |
|--------|-------------|
| **Railway** | You’ve pushed and Railway has deployed. Webhook should point to your Railway URL. |
| **Local** | You run uvicorn and expose it with ngrok (or similar) so Telegram can hit your webhook. |

---

## 2. Make sure the app receives Telegram updates

**If testing on Railway:**

1. Get your Railway app URL (e.g. `https://ag-agent-manager.up.railway.app`).
2. Check health: `curl https://YOUR-RAILWAY-URL/health` → `{"status":"healthy"}`.
3. Check webhook: `cd ag-agent-manager && python scripts/set_webhook.py info`  
   Webhook URL must be: `https://YOUR-RAILWAY-URL/telegram/webhook`
4. If it’s wrong or empty, set it:  
   `python scripts/set_webhook.py set https://YOUR-RAILWAY-URL/telegram/webhook`

**If testing locally:**

1. Start the app: `cd ag-agent-manager && uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Expose with ngrok: `ngrok http 8000` → copy the `https://...` URL.
3. Set webhook to your tunnel:  
   `python scripts/set_webhook.py set https://YOUR-NGROK-URL/telegram/webhook`

---

## 3. Run the pipeline tests (in Telegram)

Send these to your bot in order. Each should get a reply.

| Step | Command / message | What you’re testing |
|------|-------------------|----------------------|
| 1 | `/help` | Webhook → app → graph → help node → reply. |
| 2 | `gather sources for Machine Learning` or `gather sources for photosynthesis` | **Secondary → primary:** free APIs (Semantic Scholar, arXiv, OpenAlex) discover papers; response shows **Primary IDs** (DOI, arXiv, URL) per source. |
| 3 | `fetch content for Algebra` (or `/fetch content for Algebra`) | Content fetcher; uses discovered sources. |
| 4 | `/graph` or `graph progress` | KG progress node → private link to progress dashboard (needs Neo4j + PUBLIC_URL/RAILWAY_URL). |
| 5 | `/ingest topic=photosynthesis` (or similar) | Full ingest: extract → link → write → approval. Needs LLM + optionally Neo4j to commit. |
| 6 | `/query What is photosynthesis?` | Query node; needs Neo4j with data. |

**Minimal pass:** Steps 1 and 2 both succeed (help + gather). That confirms: Telegram → webhook → supervisor → intent → node → Telegram reply.

---

## 4. Optional: test discovery + identifiers locally

Without Telegram, you can test the “secondary → primary” discovery and claim tiers:

```bash
cd ag-agent-manager
python scripts/sample_domain_concepts.py --live --domain "Algebra I"
```

This runs real discovery (Semantic Scholar, arXiv, OpenAlex, OpenStax, etc.), canonicalizes primary identifiers, and prints sample concepts/claims with confidence tiers.

---

## 5. If something fails

| Symptom | Check |
|--------|--------|
| No reply to /help | Webhook URL = your app URL + `/telegram/webhook`? App logs show the incoming update? |
| “No LLM API key” / gather or ingest fails | OPENAI_API_KEY or ANTHROPIC_API_KEY set where the app runs (Railway Variables or local .env)? |
| Ingest/query fails | Neo4j reachable? NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD set? |
| Progress link broken | PUBLIC_URL or RAILWAY_URL set? GRAPH_VIEW_SECRET or ADMIN_API_KEY for token? |

See also: [VERIFY_RAILWAY.md](../VERIFY_RAILWAY.md), [E2E_STATUS.md](E2E_STATUS.md).
