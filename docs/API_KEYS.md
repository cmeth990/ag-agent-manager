# How to acquire API keys

Minimum to run the bot: **TELEGRAM_BOT_TOKEN**. For full features (ingest, improve, source discovery), add **at least one LLM key**.

---

## Required: Telegram

**Variable:** `TELEGRAM_BOT_TOKEN`

1. Open Telegram and message [**@BotFather**](https://t.me/BotFather).
2. Send `/newbot`.
3. Follow prompts: choose a name and a username (must end in `bot`, e.g. `my_kg_bot`).
4. BotFather returns a token like `123456789:ABCdefGHI...`. Copy it into `.env`:
   ```bash
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
   ```

---

## Required for full features: at least one LLM

You need **one** of: OpenAI, Anthropic, or Moonshot/Kimi.

### OpenAI (recommended for lowest cost)

**Variable:** `OPENAI_API_KEY`  
**Optional:** `OPENAI_MODEL` (default: `gpt-4o-mini`)

1. Go to [**platform.openai.com**](https://platform.openai.com).
2. Sign up or log in.
3. **API keys** → **Create new secret key** → copy the key (starts with `sk-`).
4. Add billing in **Settings → Billing** (pay-as-you-go; GPT-4o-mini is cheap).
5. In `.env`:
   ```bash
   OPENAI_API_KEY=sk-...
   # OPENAI_MODEL=gpt-4o-mini   # optional, this is the default
   ```

### Anthropic (Claude)

**Variable:** `ANTHROPIC_API_KEY`

1. Go to [**console.anthropic.com**](https://console.anthropic.com).
2. Sign up or log in.
3. **API Keys** → **Create Key** → copy the key (starts with `sk-ant-`).
4. Add credits in **Settings → Billing**.
5. In `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### Kimi / Moonshot (cheaper, global endpoint, privacy-focused)

**Variable:** `MOONSHOT_API_KEY` (or `KIMI_API_KEY`)  
**Optional:** `MOONSHOT_MODEL` (default: `moonshot-v1-8k`)

1. Go to [**platform.moonshot.ai**](https://platform.moonshot.ai) (Moonshot AI Open Platform).
2. Sign up or log in.
3. **API Key Management** → create/copy an API key.
4. Add billing if required for full access (new accounts may get free credits).
5. In `.env`:
   ```bash
   MOONSHOT_API_KEY=your_key_here
   # MOONSHOT_MODEL=moonshot-v1-8k   # optional
   ```

See [docs/KIMI_MOONSHOT_LLM.md](KIMI_MOONSHOT_LLM.md) for details and privacy/zero-retention notes.

---

## Optional: Database (Postgres)

**Variable:** `DATABASE_URL`

- **Local:** Install Postgres, create a database, then:
  ```bash
  DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/DATABASE_NAME
  ```
- **Railway:** Add a Postgres service to your project; Railway sets `DATABASE_URL` for you.
- **Other clouds:** Use your provider’s Postgres connection string in the same format.

Without `DATABASE_URL`, the app can still run; checkpointing and the durable queue won’t persist across restarts.

---

## Optional: Neo4j (knowledge graph)

**Variables:** `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`

1. Install Neo4j locally or use [Neo4j Aura](https://neo4j.com/cloud/aura/) / another host.
2. Create a database and user; get the bolt URI (e.g. `bolt://localhost:7687`).
3. In `.env`:
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

---

## Optional: Production (Railway)

- **ADMIN_API_KEY** — Create any long random string; used to protect admin/health endpoints.
- **PUBLIC_URL** — Set by Railway (e.g. `https://your-app.up.railway.app`); or set it yourself if you use a custom domain.
- **USE_DURABLE_QUEUE** — Set to `true` when using Postgres and the background worker.
- **GRAPH_VIEW_SECRET** — Optional secret for the private graph progress link; can reuse `ADMIN_API_KEY`.

---

## Quick checklist

| Key | Required? | Where to get it |
|-----|-----------|-----------------|
| `TELEGRAM_BOT_TOKEN` | **Yes** | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `OPENAI_API_KEY` **or** `ANTHROPIC_API_KEY` **or** `MOONSHOT_API_KEY` | For full features | [OpenAI](https://platform.openai.com) / [Anthropic](https://console.anthropic.com) / [Moonshot](https://platform.moonshot.ai) |
| `DATABASE_URL` | Optional (persistence) | Local Postgres or Railway Postgres |
| `NEO4J_URI` + user/password | Optional (KG storage) | [Neo4j](https://neo4j.com) / Aura |

After adding keys, copy `.env.example` to `.env`, fill in the values, and run:

```bash
uvicorn app.main:app --reload --port 8000
```
