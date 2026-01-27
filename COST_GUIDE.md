# 💰 Most Affordable Agent Setup Guide

This guide outlines the **cheapest possible setup** for running your knowledge graph telegram agent swarm.

## 🏆 Recommended: Ultra-Low-Cost Setup

### Total Monthly Cost: **$0-5** (for light usage)

### 1. LLM: GPT-4o-mini (OpenAI) ⭐ **CHEAPEST**

**Why GPT-4o-mini?**
- **Input:** $0.150 per 1M tokens (3.3x cheaper than GPT-3.5-turbo!)
- **Output:** $0.600 per 1M tokens (2.5x cheaper than GPT-3.5-turbo!)
- **Better quality** than GPT-3.5-turbo
- **128K context window** (vs 16K for GPT-3.5-turbo)

**Cost Estimate:**
- Average extraction: ~500 input tokens, ~200 output tokens
- **Per request:** ~$0.0001 (0.01 cents)
- **1,000 requests/month:** ~$0.10
- **10,000 requests/month:** ~$1.00

**Setup:**
```bash
# In .env file
OPENAI_API_KEY=sk-...
```

**Alternative: Claude 3 Haiku (Anthropic)**
- Similar pricing to GPT-4o-mini
- Good quality, slightly different behavior
- Set `ANTHROPIC_API_KEY` instead

### 2. Knowledge Graph: Neo4j Aura Free Tier ⭐ **FREE**

**Limits:**
- ✅ 200,000 nodes
- ✅ 400,000 relationships
- ✅ 1 free instance per account
- ⚠️ Auto-pauses after 3 days of no writes
- ⚠️ Deleted after 30 days if paused

**Perfect for:**
- Personal projects
- Development/testing
- Small to medium knowledge graphs

**Setup:**
1. Sign up at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Create free AuraDB instance
3. Copy connection URI and password
4. Add to `.env`:
```bash
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

**Alternative: Self-Hosted Neo4j Community Edition**
- **Cost:** $0 (runs on your own server)
- **Limits:** None (unlimited nodes/relationships)
- **Trade-off:** You manage the server

### 3. Database: Railway Postgres Free Tier ⭐ **FREE**

**Limits:**
- ✅ 256 MB storage
- ✅ $5 credit/month (usually enough for small apps)
- ✅ Auto-scales if needed

**Perfect for:**
- LangGraph checkpoint storage
- State persistence

**Setup:**
- Railway auto-injects `DATABASE_URL` when you add Postgres service

### 4. Hosting: Railway Free Tier ⭐ **FREE**

**Limits:**
- ✅ $5 credit/month
- ✅ Enough for small bots
- ✅ Auto-deploys from GitHub

**Alternative Free Hosting:**
- **Render:** Free tier (spins down after inactivity)
- **Fly.io:** Free tier with limits
- **Heroku:** No longer free, but cheap hobby tier

## 💵 Cost Breakdown

### Scenario 1: Light Usage (Personal Bot)
- **LLM:** 1,000 requests/month = **$0.10**
- **Neo4j:** Free tier = **$0**
- **Postgres:** Free tier = **$0**
- **Hosting:** Railway free = **$0**
- **Total: ~$0.10/month** 🎉

### Scenario 2: Moderate Usage (Small Team)
- **LLM:** 10,000 requests/month = **$1.00**
- **Neo4j:** Free tier = **$0** (if under 200k nodes)
- **Postgres:** Free tier = **$0**
- **Hosting:** Railway free = **$0**
- **Total: ~$1.00/month** 🎉

### Scenario 3: Heavy Usage (Active Production)
- **LLM:** 100,000 requests/month = **$10.00**
- **Neo4j:** Free tier or upgrade to Starter ($65/month)
- **Postgres:** Railway free or upgrade
- **Hosting:** Railway free or upgrade
- **Total: ~$10-75/month** depending on Neo4j tier

## 🎯 Optimization Tips

### 1. Reduce LLM Calls
- Cache extraction results for similar inputs
- Batch multiple entities in one extraction
- Use fallback extraction when LLM fails (already implemented)

### 2. Efficient Neo4j Usage
- Use indexes on frequently queried properties
- Batch writes when possible
- Monitor node/relationship counts

### 3. Monitor Costs
- Set up OpenAI usage alerts
- Track token usage in logs
- Use Railway's usage dashboard

## 📊 Model Comparison

| Model | Input Cost/1M | Output Cost/1M | Quality | Context |
|-------|--------------|----------------|---------|---------|
| **GPT-4o-mini** ⭐ | $0.150 | $0.600 | High | 128K |
| GPT-3.5-turbo | $0.500 | $1.500 | Medium | 16K |
| Claude 3 Haiku | ~$0.25 | ~$1.25 | High | 200K |

**Winner: GPT-4o-mini** (cheapest + best quality)

## 🚀 Quick Start: Ultra-Low-Cost Setup

1. **Get OpenAI API Key** (free $5 credit for new users)
   - Sign up at [platform.openai.com](https://platform.openai.com)
   - Add payment method (only charged if you exceed free credit)

2. **Create Neo4j Aura Free Instance**
   - Go to [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
   - Sign up and create free database

3. **Deploy to Railway** (free tier)
   - Connect GitHub repo
   - Add Postgres service (free)
   - Set environment variables

4. **Set Environment Variables:**
```bash
TELEGRAM_BOT_TOKEN=your_token
OPENAI_API_KEY=sk-...
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
DATABASE_URL=postgresql://... (auto-injected by Railway)
```

## 💡 Even Cheaper Options

### Option 1: Local LLM (Ollama)
- **Cost:** $0 (runs on your machine)
- **Trade-off:** Requires local GPU/server
- **Models:** Llama 3, Mistral, etc.
- **Setup:** Would need to add Ollama integration

### Option 2: No LLM (Rule-Based Extraction)
- **Cost:** $0
- **Trade-off:** Lower quality, limited extraction
- **Current:** Falls back to simple extraction if no LLM key

### Option 3: Hybrid Approach
- Use LLM only for complex extractions
- Use rule-based for simple topics
- **Savings:** 50-80% reduction in LLM calls

## 📈 Scaling Costs

If you need to scale beyond free tiers:

1. **Neo4j Aura Starter:** $65/month (unlimited nodes)
2. **Railway Pro:** $20/month (more resources)
3. **LLM costs scale linearly** with usage

**Recommendation:** Start with free tiers, upgrade only when you hit limits.

## ✅ Current Configuration

Your setup is already optimized for cost:
- ✅ Uses GPT-4o-mini (cheapest quality option)
- ✅ Falls back to simple extraction if no LLM
- ✅ Supports Neo4j free tier
- ✅ Works with Railway free tier

**You're already set up for maximum affordability!** 🎉
