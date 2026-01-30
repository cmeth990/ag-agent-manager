# Telegram Manager + LangGraph Agent Team

A Telegram bot that manages a knowledge graph using LangGraph with human-in-the-loop approval for writes.

📋 **One doc for all moving parts:** [docs/ARCHITECTURE_AND_MOVING_PARTS.md](docs/ARCHITECTURE_AND_MOVING_PARTS.md) — components, flows, config, API, and where to find more detail.

💰 **Ultra-Low-Cost Setup:** Can run for **~$0.10-1/month** with free tiers! See [COST_GUIDE.md](COST_GUIDE.md) for details.

## Features

- 🤖 Telegram bot interface for commands
- 🔄 LangGraph supervisor that delegates to worker agents
- 💾 Persistent state across messages (Postgres checkpointer)
- ✅ Human approval workflow before committing KG writes
- 🚀 Deployed on Railway with HTTPS webhook

## Architecture

```
Telegram → FastAPI Webhook → LangGraph Supervisor → Worker Agents → KG Client
                                      ↓
                              Postgres Checkpointer
```

### Components

- **app/main.py**: FastAPI server with Telegram webhook endpoint
- **app/telegram.py**: Telegram Bot API utilities
- **app/graph/supervisor.py**: LangGraph supervisor definition
- **app/graph/workers.py**: Worker nodes (extractor/linker/writer/commit)
- **app/graph/state.py**: Typed state schema
- **app/graph/checkpoint.py**: Postgres checkpointer setup
- **app/kg/client.py**: KG client interface (stub)
- **app/kg/diff.py**: Diff format utilities

## Setup

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Run `/newbot`
3. Choose a bot name and username
4. Copy the bot token → `TELEGRAM_BOT_TOKEN`

### 2. Local Development

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` file (see `.env.example`):
   ```bash
   TELEGRAM_BOT_TOKEN=your_token_here
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   ```
4. Run locally:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### 3. Local Webhook Testing

For local testing, use a tunnel service:

**Option A: ngrok**
```bash
ngrok http 8000
# Use the HTTPS URL: https://xxxx.ngrok.io/telegram/webhook
```

**Option B: Cloudflare Tunnel**
```bash
cloudflared tunnel --url http://localhost:8000
```

Set webhook:
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-tunnel-url/telegram/webhook"
```

### 4. Deploy on Railway

1. Push repo to GitHub
2. In Railway: **New Project** → **Deploy from GitHub repo**
3. Add a **Postgres** service to the project
4. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `DATABASE_URL` (Railway auto-injects for Postgres service)
5. Railway will auto-detect the start command from `Procfile`

### 5. Set Production Webhook

After deployment, Railway provides a URL like:
```
https://your-app.up.railway.app
```

Set webhook:
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-app.up.railway.app/telegram/webhook"
```

Verify:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## Usage

### Commands

- `/ingest topic=photosynthesis` - Ingest new knowledge
- `/query <question>` - Query the knowledge graph
- `/status` - Check bot status
- `/cancel` - Cancel current operation
- `/help` - Show help

### Approval Flow

1. User sends `/ingest topic=photosynthesis`
2. Bot processes through extractor → linker → writer
3. Bot sends proposed diff summary with **Approve/Reject** buttons
4. User taps button
5. Bot commits (if approved) or discards (if rejected)
6. Bot confirms with result

## State Persistence

- Each Telegram chat uses `chat_id` as `thread_id` in LangGraph
- State persists across messages via Postgres checkpointer
- Pending approvals survive service restarts

## Development Notes

### Stub Components

- **KG Client** (`app/kg/client.py`): Currently logs diffs. Replace with actual Neo4j/Postgres/API integration.
- **Extractor** (`app/graph/workers.py`): Placeholder extraction. Replace with LLM/NER.
- **Linker** (`app/graph/workers.py`): Pass-through. Add entity linking/deduplication.

### Extending

1. **Add new commands**: Update `detect_intent()` and add handler nodes
2. **Improve extraction**: Replace `extractor_node()` with LLM calls
3. **Add KG backend**: Implement `apply_diff()` in `app/kg/client.py`
4. **Add interrupts**: Use LangGraph's interrupt mechanism for cleaner approval pauses

## Troubleshooting

### Webhook not receiving updates
- Verify webhook URL: `getWebhookInfo`
- Check Railway logs for errors
- Ensure HTTPS (Telegram requires HTTPS)

### State not persisting
- Verify `DATABASE_URL` is set correctly
- Check Postgres service is running
- Review checkpointer initialization logs

### Approval buttons not working
- Check callback query parsing in `main.py`
- Verify `thread_id` matches between message and callback
- Review graph routing logic

## Deployment Checklist

### Pre-deployment
- [ ] Create Telegram bot via @BotFather and get token
- [ ] Set up local Postgres database (for testing) or Railway Postgres (for production)
- [ ] Test locally with tunnel (ngrok/cloudflared)
- [ ] Verify webhook receives updates

### Railway Deployment
- [ ] Push code to GitHub
- [ ] Create Railway project from GitHub repo
- [ ] Add Postgres service to Railway project
- [ ] Set environment variables:
  - [ ] `TELEGRAM_BOT_TOKEN`
  - [ ] `DATABASE_URL` (auto-injected by Railway for Postgres)
- [ ] Deploy and wait for service to start
- [ ] Copy Railway public URL (e.g., `https://your-app.up.railway.app`)

### Post-deployment
- [ ] Set webhook URL:
  ```bash
  python scripts/set_webhook.py set https://your-app.up.railway.app/telegram/webhook
  ```
- [ ] Verify webhook:
  ```bash
  python scripts/set_webhook.py info
  ```
- [ ] Send test message to bot
- [ ] Check Railway logs for webhook hits
- [ ] Test approval flow end-to-end

## Testing

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Set up .env file
cp .env.example .env
# Edit .env with your tokens

# Run server
uvicorn app.main:app --reload --port 8000

# In another terminal, set up tunnel
ngrok http 8000

# Set webhook to tunnel URL
python scripts/set_webhook.py set https://your-ngrok-url.ngrok.io/telegram/webhook
```

### Acceptance Test
1. Send `/ingest topic=photosynthesis` to bot
2. Bot should reply with proposed diff and Approve/Reject buttons
3. Tap **Approve**
4. Bot should confirm commit with counts
5. Restart Railway service
6. Send `/status` - should show bot is ready (state persisted)

## License

MIT
