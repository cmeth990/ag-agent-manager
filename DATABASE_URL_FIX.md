# DATABASE_URL Issue

## Problem

The logs show the code is working correctly, but it's trying to connect to `localhost:5432` instead of the Railway database.

## Root Cause

The `DATABASE_URL` environment variable is either:
1. **Not set** in Railway
2. **Set incorrectly** (pointing to localhost)
3. **Not accessible** to the application

## Solution

### Check Railway Environment Variables

1. Go to Railway Dashboard
2. Your Service → **Variables** tab
3. Look for `DATABASE_URL`
4. It should look like:
   ```
   postgresql://postgres:password@hostname:5432/railway
   ```
   NOT:
   ```
   postgresql://localhost:5432/...
   ```

### If DATABASE_URL is Missing

Railway should auto-inject `DATABASE_URL` when you add a Postgres service. If it's missing:

1. **Check Postgres Service**:
   - Railway Dashboard → Your Project
   - Look for a Postgres database service
   - If missing, add one: **+ New** → **Database** → **Add Postgres**

2. **Verify Link**:
   - The Postgres service should be linked to your app service
   - Railway auto-injects `DATABASE_URL` when linked

3. **Manual Check**:
   - Railway Dashboard → Postgres Service → **Variables**
   - Copy the connection string
   - Add it to your app service as `DATABASE_URL`

### Verify in Logs

After the next deploy, check logs for:
```
INFO - Database URL preview: postgresql://...
```

If it shows `localhost`, the `DATABASE_URL` is wrong.
If it shows the Railway database URL, the connection should work.

## Next Steps

1. Check Railway Variables for `DATABASE_URL`
2. Verify Postgres service is linked
3. Check logs after deploy to see the actual URL being used
