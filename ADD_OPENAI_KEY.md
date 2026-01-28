# Add OpenAI API Key to Railway

## ⚠️ IMPORTANT: Never commit API keys to git!

Your OpenAI API key has been provided. Here's how to add it securely to Railway:

## Steps

1. **Go to Railway Dashboard**: https://railway.app
2. **Select your project** → **Your App Service**
3. **Click "Variables" tab**
4. **Click "New Variable"** or **"+ Add"**
5. **Add:**
   - **Variable Name**: `OPENAI_API_KEY`
   - **Value**: (paste your key from OpenAI dashboard — never commit real keys)
6. **Save**
7. Railway will automatically redeploy

## After Adding

Once Railway redeploys:
- ✅ Domain extraction will work (domain scout)
- ✅ Intent parsing will work (source gatherer)
- ✅ Better domain filtering (fewer false positives)
- ✅ Full functionality enabled

## Security Note

- ✅ API key is stored securely in Railway (encrypted)
- ✅ Never commit API keys to git
- ✅ Railway variables are private to your deployment

## Test After Deploy

Once Railway redeploys, try:
- `/test agents` - Should work fully now
- `/scout domains` - Should extract real domains
- `/gather sources for <domain>` - Should parse intent correctly
