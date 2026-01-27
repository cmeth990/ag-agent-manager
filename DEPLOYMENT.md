# Deployment Guide

Quick reference for deploying the Telegram KG Manager Bot.

## Prerequisites

1. **Telegram Bot Token**
   - Message [@BotFather](https://t.me/BotFather)
   - Run `/newbot`
   - Save the token

2. **Postgres Database**
   - Local: Install Postgres and create a database
   - Railway: Will create automatically when you add Postgres service

3. **GitHub Repository**
   - Push this code to a GitHub repo

## Local Development Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and DATABASE_URL

# 3. Start local server
uvicorn app.main:app --reload --port 8000

# 4. In another terminal, start tunnel
ngrok http 8000
# Or: cloudflared tunnel --url http://localhost:8000

# 5. Set webhook to tunnel URL
python scripts/set_webhook.py set https://your-tunnel-url/telegram/webhook

# 6. Test by sending a message to your bot
```

## Railway Deployment

### Step 1: Create Project
1. Go to [Railway](https://railway.app)
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Choose your repository

### Step 2: Add Postgres
1. In Railway project, click **+ New**
2. Select **Database** → **Add Postgres**
3. Railway will auto-inject `DATABASE_URL` environment variable

### Step 3: Set Environment Variables
In Railway project settings → Variables, add:
- `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather

Note: `DATABASE_URL` is auto-set by Railway Postgres service.

### Step 4: Deploy
1. Railway will auto-detect `Procfile` and start the service
2. Wait for deployment to complete
3. Copy the public URL (e.g., `https://your-app.up.railway.app`)

### Step 5: Set Webhook
```bash
# Set webhook to Railway URL
python scripts/set_webhook.py set https://your-app.up.railway.app/telegram/webhook

# Verify webhook
python scripts/set_webhook.py info
```

### Step 6: Test
1. Send a message to your bot in Telegram
2. Check Railway logs to confirm webhook is receiving updates
3. Test the approval flow:
   - Send `/ingest topic=test`
   - Tap Approve button
   - Verify commit confirmation

## Troubleshooting

### Webhook not receiving updates
- Check webhook URL: `python scripts/set_webhook.py info`
- Verify Railway service is running (check logs)
- Ensure URL is HTTPS (Telegram requires HTTPS)
- Check Railway logs for errors

### Database connection errors
- Verify `DATABASE_URL` is set correctly
- Check Postgres service is running in Railway
- For local: ensure Postgres is running and database exists

### State not persisting
- Verify checkpointer tables were created (check logs)
- Ensure `DATABASE_URL` points to the same database
- Check Postgres connection in Railway logs

### Approval buttons not working
- Check callback query parsing in logs
- Verify `thread_id` matches between message and callback
- Check that `proposed_diff` is preserved from checkpoint

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `DATABASE_URL` | Yes | Postgres connection string |
| `PORT` | No | Server port (default: 8000, Railway sets automatically) |
| `RELOAD` | No | Enable auto-reload (default: false) |

## Verification Checklist

- [ ] Bot responds to `/help`
- [ ] Bot responds to `/status`
- [ ] `/ingest topic=test` creates proposed diff
- [ ] Approve button commits changes
- [ ] Reject button discards changes
- [ ] State persists after service restart
- [ ] Multiple chats have independent state
