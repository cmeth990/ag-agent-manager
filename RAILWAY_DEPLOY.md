# Railway Deployment Guide

Quick step-by-step guide to deploy the Telegram KG Manager Bot on Railway.

## Prerequisites

✅ Telegram Bot Token: `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4` (already provided)

## Step-by-Step Deployment

### 1. Push to GitHub

If not already done, push your code to GitHub:

```bash
cd ag-agent-manager
git init  # if not already a git repo
git add .
git commit -m "Initial commit: Telegram KG Manager Bot"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. Create Railway Project

1. Go to [Railway](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository (`ag-agent-manager`)
5. Railway will start deploying automatically

### 3. Add Postgres Database

1. In your Railway project dashboard, click **"+ New"**
2. Select **"Database"** → **"Add Postgres"**
3. Railway will automatically:
   - Create a Postgres database
   - Inject `DATABASE_URL` environment variable
   - Link it to your service

### 4. Set Environment Variables

In Railway project → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4` |

**Note:** `DATABASE_URL` is automatically set by Railway when you add the Postgres service.

### 5. Wait for Deployment

1. Railway will automatically detect your `Procfile` and start the service
2. Wait for the deployment to complete (check the **Deployments** tab)
3. Once deployed, Railway will provide a public URL like:
   ```
   https://your-app-name.up.railway.app
   ```
4. Copy this URL - you'll need it for the webhook

### 6. Set Telegram Webhook

After deployment, set the webhook to your Railway URL:

**Option A: Using the helper script**
```bash
cd ag-agent-manager
chmod +x scripts/deploy_railway.sh
./scripts/deploy_railway.sh https://your-app-name.up.railway.app
```

**Option B: Using Python script**
```bash
cd ag-agent-manager
export TELEGRAM_BOT_TOKEN=8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4
python scripts/set_webhook.py set https://your-app-name.up.railway.app/telegram/webhook
```

**Option C: Using curl directly**
```bash
curl -X POST "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-app-name.up.railway.app/telegram/webhook"}'
```

### 7. Verify Webhook

Check that the webhook is set correctly:

```bash
curl "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/getWebhookInfo"
```

Or use the Python script:
```bash
python scripts/set_webhook.py info
```

You should see:
- `url`: Your Railway webhook URL
- `pending_update_count`: 0 (or a small number)

### 8. Test the Bot

1. Open Telegram and find your bot
2. Send `/help` - should get a response
3. Send `/status` - should show bot status
4. Send `/ingest topic=photosynthesis` - should trigger approval flow
5. Tap **Approve** button - should commit and confirm

### 9. Monitor Logs

In Railway dashboard:
- Go to your service
- Click **"View Logs"** tab
- You should see webhook requests when you send messages

## Troubleshooting

### Service won't start

- Check Railway logs for errors
- Verify `requirements.txt` has all dependencies
- Ensure `Procfile` is correct: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Webhook not receiving updates

1. **Verify webhook URL:**
   ```bash
   curl "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/getWebhookInfo"
   ```

2. **Check Railway service is running:**
   - Go to Railway dashboard → Your service → Logs
   - Should see "Application startup complete"

3. **Verify HTTPS:**
   - Telegram requires HTTPS
   - Railway provides HTTPS automatically
   - Make sure webhook URL starts with `https://`

4. **Check Railway logs:**
   - Look for incoming webhook requests
   - Check for any error messages

### Database connection errors

- Verify Postgres service is running in Railway
- Check `DATABASE_URL` is set (Railway auto-injects it)
- Look for checkpointer initialization in logs

### Bot not responding

1. Check Railway logs for webhook hits
2. Verify `TELEGRAM_BOT_TOKEN` is set correctly
3. Test webhook endpoint directly:
   ```bash
   curl -X POST https://your-app.up.railway.app/telegram/webhook \
     -H "Content-Type: application/json" \
     -d '{"update_id": 1, "message": {"chat": {"id": 123}, "text": "/help"}}'
   ```

## Quick Reference

### Railway Service URL
After deployment, find it in:
- Railway Dashboard → Your Service → Settings → Domains

### Environment Variables in Railway
- Go to Railway Dashboard → Your Service → Variables
- Add/edit variables as needed

### View Logs
- Railway Dashboard → Your Service → Logs tab
- Or use Railway CLI: `railway logs`

### Restart Service
- Railway Dashboard → Your Service → Settings → Restart

## Next Steps

After successful deployment:

1. ✅ Test all commands (`/help`, `/status`, `/ingest`)
2. ✅ Test approval flow (Approve/Reject buttons)
3. ✅ Verify state persistence (restart service, check state survives)
4. ✅ Monitor logs for any errors
5. ✅ Consider adding rate limiting for production
6. ✅ Set up monitoring/alerting if needed

## Support

- Railway Docs: https://docs.railway.app
- Telegram Bot API: https://core.telegram.org/bots/api
- LangGraph Docs: https://langchain-ai.github.io/langgraph/
