# Fix DATABASE_URL in Railway

## Problem

Your `DATABASE_URL` in Railway is set to a placeholder:
```
postgresql://user:password@localhost:5432/dbname
```

This is why it's trying to connect to localhost instead of Railway's database.

## Solution

### Option 1: Use Railway's Auto-Injected DATABASE_URL (Recommended)

1. **Check if Postgres Service Exists**:
   - Railway Dashboard → Your Project
   - Look for a **Postgres** database service
   - If you see one, it should be linked to your app

2. **Get the Real DATABASE_URL**:
   - Railway Dashboard → **Postgres Service** (not your app)
   - Go to **Variables** tab
   - Look for `DATABASE_URL` or `POSTGRES_URL`
   - Copy the full connection string

3. **Update Your App's DATABASE_URL**:
   - Railway Dashboard → **Your App Service**
   - Go to **Variables** tab
   - Find `DATABASE_URL`
   - **Delete** the placeholder value
   - **Paste** the real connection string from Postgres service
   - Or **delete** `DATABASE_URL` entirely - Railway will auto-inject it if services are linked

### Option 2: Link Postgres Service (If Not Linked)

1. Railway Dashboard → Your Project
2. If Postgres service exists but isn't linked:
   - Click on your **App Service**
   - Go to **Settings** → **Service Connections**
   - Add connection to Postgres service
   - Railway will auto-inject `DATABASE_URL`

### Option 3: Add Postgres Service (If Missing)

1. Railway Dashboard → Your Project
2. Click **+ New**
3. Select **Database** → **Add Postgres**
4. Wait for it to provision
5. Railway will automatically:
   - Create the database
   - Link it to your app
   - Inject `DATABASE_URL` environment variable

## Verify

After updating, check Railway logs. You should see:
```
INFO - Database URL preview: postgresql://postgres:...@some-host.railway.app:5432/railway
```

NOT:
```
postgresql://user:password@localhost:5432/dbname
```

## Quick Fix Steps

1. Go to Railway Dashboard
2. Your Project → **Postgres Service** → **Variables**
3. Copy the `DATABASE_URL` value
4. Your Project → **App Service** → **Variables**
5. Update `DATABASE_URL` with the copied value
6. Redeploy (or wait for auto-redeploy)

The connection string should look like:
```
postgresql://postgres:actual_password@containers-us-west-xxx.railway.app:5432/railway
```
