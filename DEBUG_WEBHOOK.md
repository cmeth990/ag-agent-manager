# Debug: /help Not Working

## Quick Checks

### 1. Check Webhook is Set

```bash
# Get webhook info
python scripts/set_webhook.py info
```

Should show your Railway URL.

### 2. Check Server Logs

When you send `/help`, you should see in Railway logs:
```
INFO: Received update: <update_id>
INFO: Message from <chat_id>: /help
INFO: Graph execution completed for <chat_id>, intent: help
INFO: Sent response to <chat_id>
```

### 3. Check for Errors

Look for:
- `Error running graph:`
- `Error sending message:`
- `ModuleNotFoundError`
- `ImportError`

### 4. Test Webhook Directly

```bash
# Test if webhook endpoint is reachable
curl -X POST https://your-railway-url.up.railway.app/telegram/webhook \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"chat": {"id": 123}, "text": "/help"}}'
```

### 5. Verify Telegram Bot Token

Check Railway environment variables:
- `TELEGRAM_BOT_TOKEN` should be set

### 6. Check Intent Detection

The code should detect `/help` and route to `help` node. Check logs for:
```
intent: help
```

## Common Issues

### Issue: No Response at All

**Possible causes:**
1. Webhook not set correctly
2. Telegram not reaching your server
3. Server crashed on startup

**Fix:**
- Check Railway logs for startup errors
- Verify webhook URL in Telegram

### Issue: Error in Graph Execution

**Check logs for:**
- Import errors
- Database connection errors
- Missing dependencies

**Fix:**
- Check Railway logs
- Verify all dependencies in requirements.txt

### Issue: Telegram API Error

**Check logs for:**
- `Error sending message:`
- Invalid bot token
- Rate limiting

**Fix:**
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check Telegram API status

## Test Locally

If you want to test locally:

```bash
# 1. Set up ngrok
ngrok http 8000

# 2. Set webhook to ngrok URL
python scripts/set_webhook.py set https://your-ngrok-url.ngrok.io/telegram/webhook

# 3. Run server
python -m uvicorn app.main:app --reload --port 8000

# 4. Send /help to bot
# 5. Check terminal for logs
```

## Next Steps

1. **Check Railway logs** - Look for errors when you send `/help`
2. **Share the error** - If you see any errors in logs, share them
3. **Verify webhook** - Make sure webhook is set to your Railway URL
