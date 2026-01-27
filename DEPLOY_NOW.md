# 🚀 Railway Deployment - Quick Start

## Current Status
✅ Project structure ready  
✅ Procfile configured  
✅ railway.json configured  
✅ Telegram token configured  
⚠️  GitHub repository needs to be set up

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `ag-agent-manager` (or any name you prefer)
3. Make it **Private** or **Public** (your choice)
4. **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click **"Create repository"**

## Step 2: Update Git Remote

After creating the GitHub repo, you'll get a URL like:
- `https://github.com/YOUR_USERNAME/ag-agent-manager.git` (HTTPS)
- `git@github.com:YOUR_USERNAME/ag-agent-manager.git` (SSH)

**Update the remote:**
```bash
cd /Users/cmethod/LUMI_3/ag-agent-manager
git remote set-url origin https://github.com/YOUR_USERNAME/ag-agent-manager.git
# Replace YOUR_USERNAME with your actual GitHub username
```

**Verify:**
```bash
git remote -v
```

## Step 3: Push to GitHub

```bash
cd /Users/cmethod/LUMI_3/ag-agent-manager
git add .
git commit -m "Ready for Railway deployment"
git push -u origin main
```

## Step 4: Deploy to Railway

1. Go to https://railway.app and sign in (or create account)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub if prompted
5. Select your `ag-agent-manager` repository
6. Railway will automatically start deploying

## Step 5: Add Postgres Database

1. In Railway project dashboard, click **"+ New"**
2. Select **"Database"** → **"Add Postgres"**
3. Railway automatically:
   - Creates Postgres database
   - Injects `DATABASE_URL` environment variable
   - Links it to your service

## Step 6: Set Environment Variables

1. In Railway project → Click on your **service** (not the database)
2. Go to **"Variables"** tab
3. Click **"+ New Variable"**
4. Add:
   - **Name:** `TELEGRAM_BOT_TOKEN`
   - **Value:** `8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4`
5. Click **"Add"**

**Note:** `DATABASE_URL` is automatically set by Railway (don't add it manually)

## Step 7: Wait for Deployment

1. Check the **"Deployments"** tab
2. Wait for status to show **"Active"** (green)
3. Once deployed, Railway provides a public URL:
   - Go to **"Settings"** → **"Domains"**
   - Copy the URL (e.g., `https://your-app-name.up.railway.app`)

## Step 8: Set Telegram Webhook

After you have your Railway URL, set the webhook:

**Option A: Using Python script (recommended)**
```bash
cd /Users/cmethod/LUMI_3/ag-agent-manager
export TELEGRAM_BOT_TOKEN=8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4
python scripts/set_webhook.py set https://your-app-name.up.railway.app/telegram/webhook
```

**Option B: Using curl**
```bash
curl -X POST "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-app-name.up.railway.app/telegram/webhook"}'
```

## Step 9: Verify Webhook

```bash
python scripts/set_webhook.py info
```

Or:
```bash
curl "https://api.telegram.org/bot8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4/getWebhookInfo"
```

## Step 10: Test the Bot

1. Open Telegram
2. Find your bot
3. Send `/help` - should get a response
4. Send `/ingest topic=photosynthesis` - should trigger approval flow
5. Tap **Approve** button - should commit and confirm

## Troubleshooting

### Service won't start
- Check Railway **Logs** tab for errors
- Verify all environment variables are set
- Check that Postgres service is running

### Webhook not working
- Verify webhook URL is set correctly
- Check Railway logs for incoming requests
- Ensure Railway URL uses HTTPS (Telegram requires it)

### Database errors
- Verify Postgres service is running in Railway
- Check `DATABASE_URL` is automatically set (don't set it manually)
- Look for checkpointer initialization in logs

## Quick Commands Reference

```bash
# Update git remote (after creating GitHub repo)
git remote set-url origin https://github.com/YOUR_USERNAME/ag-agent-manager.git

# Push to GitHub
git push -u origin main

# Set webhook (after Railway deployment)
python scripts/set_webhook.py set https://YOUR_RAILWAY_URL/telegram/webhook

# Check webhook status
python scripts/set_webhook.py info
```

## Next Steps After Deployment

1. ✅ Test all commands (`/help`, `/status`, `/ingest`)
2. ✅ Test approval flow (Approve/Reject buttons)
3. ✅ Verify state persistence (restart service, check state survives)
4. ✅ Monitor Railway logs
5. ✅ Set up monitoring/alerting if needed

---

**Need help?** Check `RAILWAY_DEPLOY.md` for detailed troubleshooting.
