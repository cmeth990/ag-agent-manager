# How to Find Your Railway DATABASE_URL

## Method 1: From Postgres Service Variables (Easiest)

1. **Go to Railway Dashboard**: https://railway.app
2. **Select your project**
3. **Look for a Postgres service** (separate card from your app)
   - It might be named "Postgres" or "Database"
   - Has a database icon
4. **Click on the Postgres service**
5. **Go to "Variables" tab**
6. **Look for `DATABASE_URL`** or `POSTGRES_URL`
7. **Copy the entire value**

It should look like:
```
postgresql://postgres:AbCdEf123456@containers-us-west-123.railway.app:5432/railway
```

## Method 2: From Postgres Service Connection Tab

1. **Click on Postgres service**
2. **Go to "Data" or "Connection" tab**
3. **Look for "Connection String" or "Postgres Connection URL"**
4. **Copy it**

## Method 3: From App Service (If Auto-Injected)

1. **Click on your App service**
2. **Go to "Variables" tab**
3. **Look for `DATABASE_URL`**
4. If it shows the real Railway URL (not localhost), use that
5. If it shows localhost placeholder, you need to get it from Postgres service

## Method 4: Check Railway CLI (If Installed)

```bash
railway variables
```

This will show all environment variables including DATABASE_URL.

## What to Look For

The real connection string will have:
- ✅ A Railway hostname: `containers-us-west-xxx.railway.app` or similar
- ✅ A real password (not "password")
- ✅ Port `5432`
- ✅ Database name (usually "railway" or "postgres")

NOT:
- ❌ `localhost`
- ❌ `user:password` (placeholder)
- ❌ `dbname` (placeholder)

## If You Don't Have a Postgres Service

If you don't see a Postgres service in your Railway project:

1. **Add one**:
   - Railway Dashboard → Your Project
   - Click **+ New**
   - Select **Database** → **Add Postgres**
   - Wait for provisioning (1-2 minutes)

2. **Railway will automatically**:
   - Create the database
   - Generate a unique connection string
   - Link it to your app
   - Inject `DATABASE_URL` into your app's variables

## After You Find It

1. Copy the connection string
2. Go to your **App service** → **Variables**
3. Update `DATABASE_URL` with the real value
4. Save
5. Railway will auto-redeploy

The connection string is unique to your Railway account and project - I can't see it from here!
