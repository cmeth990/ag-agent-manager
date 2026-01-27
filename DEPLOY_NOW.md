# 🚀 Deploy to Railway - Ready to Go!

Your Telegram KG Manager Bot is **ready for Railway deployment**!

## ✅ Pre-Deployment Checklist

- ✅ Git repository initialized
- ✅ All code files in place
- ✅ `Procfile` configured for Railway
- ✅ `railway.json` configured
- ✅ `requirements.txt` with all dependencies
- ✅ Telegram bot token: `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4`

## 🎯 Quick Deployment Steps

### 1. Push to GitHub (if not already done)

```bash
# Create a new repo on GitHub first: https://github.com/new
# Then:
git remote add origin https://github.com/YOUR_USERNAME/ag-agent-manager.git
git branch -M main
git push -u origin main
```

### 2. Deploy on Railway

1. **Go to Railway:** https://railway.app
2. **New Project** → **Deploy from GitHub repo**
3. **Select** your `ag-agent-manager` repository
4. Railway will auto-detect Python and start building

### 3. Add Postgres Database

1. In Railway project → **"+ New"**
2. **Database** → **Add Postgres**
3. Railway auto-injects `DATABASE_URL` ✅

### 4. Set Environment Variable

In Railway → Your Service → **Variables**:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4` |

### 5. Get Railway URL & Set Webhook

After deployment completes, Railway gives you a URL like:
```
https://your-app-name.up.railway.app
```

**Set webhook:**
```bash
curl -X POST "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-app-name.up.railway.app/telegram/webhook"}'
```

**Verify:**
```bash
curl "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/getWebhookInfo"
```

## 🧪 Test Your Bot

1. Open Telegram → Find your bot
2. Send `/help`
3. Send `/ingest topic=photosynthesis`
4. Tap **Approve** button
5. ✅ Should confirm commit!

## 📊 Monitor Deployment

- **Logs:** Railway Dashboard → Service → **Logs**
- **Metrics:** Railway Dashboard → Service → **Metrics**
- **Variables:** Railway Dashboard → Service → **Variables**

## 🆘 Quick Troubleshooting

**Service won't start?**
- Check Railway logs
- Verify `TELEGRAM_BOT_TOKEN` is set
- Ensure Postgres service is running

**Webhook not working?**
- Verify webhook URL is set (use `getWebhookInfo`)
- Check Railway logs for incoming requests
- Ensure URL uses `https://`

**Database errors?**
- Verify Postgres service is running
- Check `DATABASE_URL` is auto-injected by Railway

## 📚 Full Documentation

- **Detailed Guide:** See `RAILWAY_DEPLOY.md`
- **Quick Start:** See `RAILWAY_QUICKSTART.md`
- **General Setup:** See `README.md`

---

**You're all set! 🎉 Deploy when ready!**
