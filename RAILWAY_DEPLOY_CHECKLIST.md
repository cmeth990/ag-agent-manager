# Railway Deployment Checklist

## ✅ Step 1: GitHub Repository
- [x] Repository created: https://github.com/cmeth990/ag-agent-manager
- [x] Code pushed to main branch

## 📋 Step 2: Create Railway Project

1. Go to https://railway.app and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose repository: `cmeth990/ag-agent-manager`
5. Railway will auto-detect the project and start deploying

## 🗄️ Step 3: Add Postgres Database

1. In Railway project dashboard, click **"+ New"**
2. Select **"Database"** → **"Add Postgres"**
3. Railway will automatically:
   - Create a Postgres database
   - Inject `DATABASE_URL` environment variable
   - Link it to your service

**Important:** Wait for Postgres to fully initialize before proceeding.

## 🔐 Step 4: Set Environment Variables

In Railway project → Your service → **Variables** tab, add:

**Required**

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token (e.g. from BotFather) |
| `NEO4J_URI` | Neo4j bolt URL (e.g. `bolt://host:7687` or Neo4j Aura URI) |
| `NEO4J_USER` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `OPENAI_API_KEY` **or** `ANTHROPIC_API_KEY` | At least one LLM provider key |

**Auto-set by Railway**

| Variable | Note |
|----------|------|
| `DATABASE_URL` | Set automatically when you add Postgres — do not set manually |

**Recommended for production**

| Variable | Value |
|----------|-------|
| `USE_DURABLE_QUEUE` | `true` — use Postgres queue and background worker |
| `ADMIN_API_KEY` | Secret key for telemetry/queue/kg admin endpoints (header `X-Admin-Key` or `Authorization: Bearer <key>`) |

## 🚀 Step 5: Wait for Deployment

1. Railway will automatically:
   - Detect your `Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Install dependencies from `requirements.txt`
   - Start the service

2. Monitor the deployment:
   - Go to **Deployments** tab
   - Watch for "Deploy Succeeded"
   - Check **Logs** tab for any errors

3. Once deployed, Railway will provide a public URL:
   ```
   https://your-app-name.up.railway.app
   ```
   - Find it in: **Settings** → **Domains**
   - Copy this URL - you'll need it for the webhook

## 🔗 Step 6: Set Telegram Webhook

After deployment completes, set the webhook:

**Option A: Using Python script (recommended)**
```bash
cd ag-agent-manager
export TELEGRAM_BOT_TOKEN=8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4
python scripts/set_webhook.py set https://YOUR_RAILWAY_URL.up.railway.app/telegram/webhook
```

**Option B: Using curl**
```bash
curl -X POST "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://YOUR_RAILWAY_URL.up.railway.app/telegram/webhook"}'
```

Replace `YOUR_RAILWAY_URL` with your actual Railway domain.

## ✅ Step 7: Verify Webhook

Check that the webhook is set correctly:

```bash
curl "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/getWebhookInfo"
```

Or use the Python script:
```bash
python scripts/set_webhook.py info
```

Expected response:
- `url`: Your Railway webhook URL
- `pending_update_count`: 0 (or a small number)
- `last_error_date`: null (or not present)

## 🧪 Step 8: Test the Bot

1. Open Telegram and find your bot
2. Send `/help` - should get a response
3. Send `/status` - should show bot status
4. Send `/ingest topic=photosynthesis` - should trigger approval flow
5. Tap **Approve** button - should commit and confirm

## 📊 Step 9: Monitor Logs

In Railway dashboard:
- Go to your service
- Click **"Logs"** tab
- You should see:
  - Application startup messages
  - Webhook requests when you send messages
  - Any errors or warnings

## 🐛 Troubleshooting

### Service won't start
- Check Railway logs for errors
- Verify all dependencies in `requirements.txt` are installable
- Ensure `Procfile` is correct

### Webhook not receiving updates
1. Verify webhook URL is set correctly (Step 7)
2. Check Railway service is running (Logs tab)
3. Ensure webhook URL uses HTTPS (Railway provides this automatically)
4. Check Railway logs for incoming webhook requests

### Database connection errors
- Verify Postgres service is running in Railway
- Check `DATABASE_URL` is set (should be auto-injected)
- Look for checkpointer initialization messages in logs

### Bot not responding
1. Check Railway logs for webhook hits
2. Verify `TELEGRAM_BOT_TOKEN` is set correctly
3. Test webhook endpoint directly (see RAILWAY_DEPLOY.md)

## 🎯 Quick Commands Reference

```bash
# Set webhook
python scripts/set_webhook.py set https://YOUR_APP.up.railway.app/telegram/webhook

# Check webhook status
python scripts/set_webhook.py info

# Remove webhook (if needed)
python scripts/set_webhook.py remove
```

## 📝 Next Steps After Deployment

- [ ] Test all commands (`/help`, `/status`, `/ingest`)
- [ ] Test approval flow (Approve/Reject buttons)
- [ ] Verify state persistence (restart service, check state survives)
- [ ] Monitor logs for any errors
- [ ] Consider adding rate limiting for production
- [ ] Set up monitoring/alerting if needed

---

**Repository:** https://github.com/cmeth990/ag-agent-manager  
**Railway Dashboard:** https://railway.app/dashboard
