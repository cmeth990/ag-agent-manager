# Quick Fix: Test Agents Not Working

## The Issue

If `/test agents` isn't working, you need to **restart/redeploy** the bot because:

1. The graph is built on **first import** (cached globally)
2. New code changes require a **fresh server start**
3. The `parallel_test` node needs to be in the compiled graph

## Solution

### If Running Locally:

**Restart your server:**

```bash
# Stop the current server (Ctrl+C)
# Then restart:
cd /Users/cmethod/LUMI_3/ag-agent-manager
python -m uvicorn app.main:app --reload --port 8000
```

The `--reload` flag should auto-reload on code changes, but sometimes you need a manual restart.

### If Deployed on Railway:

**Redeploy:**

1. **Option A: Push to GitHub** (Railway auto-deploys)
   ```bash
   cd /Users/cmethod/LUMI_3/ag-agent-manager
   git add .
   git commit -m "Add parallel agents test"
   git push
   ```

2. **Option B: Manual Redeploy**
   - Go to Railway dashboard
   - Click on your service
   - Click "Redeploy" button

3. **Wait for deployment** (check logs)

## Verify It's Working

After restart/redeploy, test:

1. Send `/help` - should show `/test agents` in the list
2. Send `/test agents` - should start parallel execution
3. Check logs for any errors

## If Still Not Working

Check the logs for errors:

**Local:**
```bash
# Check terminal where server is running
```

**Railway:**
- Go to Railway dashboard → Your service → Logs

Look for:
- Import errors
- Graph build errors
- Missing module errors

## Quick Test Script

Test if the code works locally:

```bash
cd /Users/cmethod/LUMI_3/ag-agent-manager
python -c "
from app.graph.supervisor import detect_intent
state = {'user_input': '/test agents'}
result = detect_intent(state)
print(f'Intent detected: {result.get(\"intent\")}')
print('✅ Should be: parallel_test')
"
```

Expected output:
```
Intent detected: parallel_test
✅ Should be: parallel_test
```
