# Quick Start Guide

## 1. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

**Note:** Your Telegram bot token should be set as an environment variable. Get it from @BotFather on Telegram.

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Verify Setup

```bash
python scripts/verify_setup.py
```

## 4. Run Locally

```bash
uvicorn app.main:app --reload --port 8000
```

## 5. Set Up Webhook (Local Testing)

In another terminal, start a tunnel:

```bash
# Option 1: ngrok
ngrok http 8000

# Option 2: cloudflared
cloudflared tunnel --url http://localhost:8000
```

Then set the webhook:

```bash
python scripts/set_webhook.py set https://your-tunnel-url/telegram/webhook
```

## 6. Test

1. Open Telegram and find your bot
2. Send `/help` - should show help message
3. Send `/ingest topic=photosynthesis` - should show proposed diff with buttons
4. Tap **Approve** - should confirm commit

## 7. Deploy to Railway

1. Push code to GitHub
2. Create Railway project from GitHub repo
3. Add Postgres service
4. Set `TELEGRAM_BOT_TOKEN` environment variable
5. Deploy
6. Set webhook to Railway URL:
   ```bash
   python scripts/set_webhook.py set https://your-app.up.railway.app/telegram/webhook
   ```

## Troubleshooting

- **Webhook not working?** Check `python scripts/set_webhook.py info`
- **Database errors?** Verify `DATABASE_URL` is correct
- **State not persisting?** Check Postgres connection and checkpointer logs
