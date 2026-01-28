# Railway: "Deployment successful" but no logs and /help does nothing

"Deployment successful" only means the build and start command ran. Two common issues:

## 1. Logs not loading

- In Railway: open your **service** → **Deployments** → click the **latest deployment** → **View Logs** (or the **Logs** tab on the service).
- If you see nothing: add a **Variable** `PYTHONUNBUFFERED` = `1` (Railway → Service → Variables). Redeploy.
- Our Procfile already sets this in the start command; some Railway setups ignore that and only use Variables.

## 2. /help does nothing (bot doesn’t reply)

Telegram only sends messages (including /help) to the **webhook URL** you set. If that URL isn’t your Railway app, the app never receives the update.

### Step 1: Get your Railway URL

In Railway: Service → **Settings** → **Networking** / **Domains** → copy the URL, e.g. `https://your-app.up.railway.app`.

### Step 2: Check that the app is up

From your machine (replace with your URL):

```bash
curl https://YOUR-APP.up.railway.app/health
```

You should see: `{"status":"healthy"}`. If not, the app isn’t responding (crash, wrong port, or wrong URL).

### Step 3: Check where Telegram sends updates

```bash
cd ag-agent-manager
export TELEGRAM_BOT_TOKEN=your_bot_token_from_railway_or_env
python scripts/set_webhook.py info
```

Look at **Webhook URL**. It must be exactly:

`https://YOUR-APP.up.railway.app/telegram/webhook`

If it’s empty or different, Telegram is not sending /help (or any message) to your Railway app.

### Step 4: Set the webhook to Railway

```bash
python scripts/set_webhook.py set https://YOUR-APP.up.railway.app/telegram/webhook
```

Then send `/help` to your bot in Telegram again.

### One-shot verify script

```bash
export RAILWAY_URL=https://YOUR-APP.up.railway.app
export TELEGRAM_BOT_TOKEN=your_token
python scripts/verify_railway.py
```

This checks that `/health` works and that the webhook URL points at your Railway app.

## Summary

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| No logs | Buffering or wrong log tab | Set `PYTHONUNBUFFERED=1` in Variables; check Deployments → View Logs |
| /help does nothing | Webhook not set or wrong URL | Run `set_webhook.py info`, then `set_webhook.py set <railway_url/telegram/webhook>` |
| /health fails | App not running or wrong domain | Check Railway URL and service status; check Variables (e.g. PORT, TELEGRAM_BOT_TOKEN) |
