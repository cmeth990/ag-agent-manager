# Railway Quick Start Checklist

## ✅ Pre-Deployment Checklist

- [x] Telegram Bot Token: `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4`
- [x] Code is ready (all files in place)
- [x] `Procfile` configured
- [x] `railway.json` configured
- [x] `requirements.txt` has all dependencies

## 🚀 Deployment Steps

### 1. Push to GitHub (if not already done)
```bash
cd ag-agent-manager
git add .
git commit -m "Ready for Railway deployment"
git push
```

### 2. Create Railway Project
1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `ag-agent-manager` repository

### 3. Add Postgres
1. In Railway project, click **"+ New"**
2. Select **"Database"** → **"Add Postgres"**
3. Wait for it to provision (auto-injects `DATABASE_URL`)

### 4. Set Environment Variable
In Railway → **Variables** tab:
- Add: `TELEGRAM_BOT_TOKEN` = `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4`

### 5. Get Railway URL
After deployment completes:
- Railway Dashboard → Your Service → Settings → Domains
- Copy the URL (e.g., `https://your-app.up.railway.app`)

### 6. Set Webhook
```bash
cd ag-agent-manager
./scripts/deploy_railway.sh https://your-app.up.railway.app
```

Or manually:
```bash
curl -X POST "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-app.up.railway.app/telegram/webhook"}'
```

### 7. Verify
```bash
curl "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/getWebhookInfo"
```

### 8. Test
Send `/help` to your bot in Telegram!

## 📋 What Railway Auto-Detects

- **Start Command**: From `Procfile`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Python Version**: Auto-detected from code
- **Dependencies**: Installed from `requirements.txt`
- **Port**: Railway sets `$PORT` automatically

## 🔍 Verify Deployment

1. **Check Railway Logs**: Should see "Application startup complete"
2. **Health Check**: Visit `https://your-app.up.railway.app/health` → Should return `{"status": "healthy"}`
3. **Send Test Message**: Bot should respond

## 🆘 Quick Troubleshooting

**Service won't start?**
- Check Railway logs
- Verify `TELEGRAM_BOT_TOKEN` is set
- Ensure Postgres service is running

**Webhook not working?**
- Verify webhook URL is set correctly
- Check Railway logs for incoming requests
- Ensure URL is HTTPS

**Bot not responding?**
- Check Railway logs
- Verify token is correct
- Test webhook endpoint manually

## 📚 Full Guide

See `RAILWAY_DEPLOY.md` for detailed instructions and troubleshooting.
