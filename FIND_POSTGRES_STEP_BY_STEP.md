# Step-by-Step: Finding Postgres Service in Railway

## Step 1: Open Railway Dashboard

1. Go to: **https://railway.app**
2. **Sign in** with your account
3. You should see your **Projects** or **Dashboard**

## Step 2: Select Your Project

1. Look for a project card/tile (might be named after your repo: `ag-agent-manager`)
2. **Click on the project** to open it
3. You should now see the **project dashboard** with services

## Step 3: Look for Services

On the project dashboard, you'll see **service cards** (rectangular boxes). You should see:

1. **Your App Service** (the main one):
   - Name might be: `ag-agent-manager` or `web-production-9f90` or similar
   - Has a web/application icon
   - Shows "Running" or deployment status

2. **Postgres Service** (if it exists):
   - Name might be: `Postgres`, `Database`, `postgres`, or similar
   - Has a **database icon** (looks like a cylinder/barrel or database symbol)
   - Might show "Running" or "Provisioning"

## Step 4: Identify the Postgres Service

**What to look for:**
- ✅ **Database icon** (cylinder/barrel shape, not a web/app icon)
- ✅ Name contains: "Postgres", "Database", "postgres", "db"
- ✅ Separate card from your app service
- ✅ Might show connection info or database stats

**If you see it:**
- **Click on the Postgres service card**

**If you DON'T see it:**
- You need to create one (see Step 5)

## Step 5: If Postgres Service Doesn't Exist

1. On the project dashboard, look for a **"+ New"** or **"+ Add"** button
   - Usually at the top right or in the services area
2. **Click "+ New"**
3. A menu will appear with options like:
   - "GitHub Repo"
   - "Database"
   - "Empty Service"
   - etc.
4. **Click "Database"**
5. **Select "Add Postgres"** or "PostgreSQL"
6. Wait 1-2 minutes for Railway to provision it
7. A new Postgres service card will appear

## Step 6: Get the Connection String

Once you're in the Postgres service:

### Method A: Variables Tab (Easiest)

1. Look for tabs at the top: **"Variables"**, **"Metrics"**, **"Settings"**, etc.
2. **Click "Variables"** tab
3. You'll see a list of environment variables
4. Look for:
   - `DATABASE_URL` (most common)
   - `POSTGRES_URL`
   - `POSTGRES_CONNECTION_STRING`
5. **Click on the value** or **copy icon** next to it
6. **Copy the entire string**

### Method B: Data/Connection Tab

1. Look for **"Data"** or **"Connection"** tab
2. **Click it**
3. Look for:
   - "Connection String"
   - "Postgres Connection URL"
   - "Connection Info"
4. **Copy the connection string**

## Step 7: What the Connection String Looks Like

It should look like one of these formats:

```
postgresql://postgres:AbCdEf123456@containers-us-west-123.railway.app:5432/railway
```

or

```
postgres://postgres:AbCdEf123456@containers-us-west-123.railway.app:5432/railway
```

**Key parts:**
- Starts with `postgresql://` or `postgres://`
- Has a Railway hostname (like `containers-us-west-xxx.railway.app`)
- Has a real password (not "password")
- Port `5432`
- Database name at the end

## Step 8: Update Your App's DATABASE_URL

1. Go back to your **App Service** (the main one, not Postgres)
2. Click on it
3. Go to **"Variables"** tab
4. Find `DATABASE_URL`
5. **Click Edit** or the pencil icon
6. **Delete** the placeholder: `postgresql://user:password@localhost:5432/dbname`
7. **Paste** the real connection string from Step 6
8. **Save**

## Visual Guide

```
Railway Dashboard
├── Projects
    └── Your Project (ag-agent-manager)
        ├── Services:
        │   ├── [App Service] ← Your main app
        │   │   └── Variables tab → DATABASE_URL (currently wrong)
        │   │
        │   └── [Postgres Service] ← Database (what we need!)
        │       └── Variables tab → DATABASE_URL (the real one)
        │
        └── + New button → Add Postgres (if missing)
```

## Troubleshooting

**"I don't see a Postgres service"**
→ Create one: + New → Database → Add Postgres

**"I see Postgres but can't find DATABASE_URL"**
→ Check Variables tab, or Data/Connection tab

**"The connection string still shows localhost"**
→ You're looking at the App service, not Postgres service. Get it from Postgres service.

**"I'm not sure which service is which"**
→ Postgres has a database icon (cylinder). App has a web/app icon.

## Need More Help?

If you're still stuck, tell me:
1. What services you see in your Railway project
2. What tabs you see when you click on services
3. Any error messages

I can guide you further!
