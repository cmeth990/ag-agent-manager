#!/usr/bin/env python3
"""
Verify Railway deployment: app is up and Telegram webhook points to it.
Run: RAILWAY_URL=https://your-app.up.railway.app python scripts/verify_railway.py
     (TELEGRAM_BOT_TOKEN from env or .env)
"""
import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


async def main():
    railway_url = os.getenv("RAILWAY_URL", "").rstrip("/")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    if not railway_url:
        print("Set RAILWAY_URL to your app URL, e.g.:")
        print("  export RAILWAY_URL=https://your-app.up.railway.app")
        print("  python scripts/verify_railway.py")
        sys.exit(1)

    webhook_url = f"{railway_url}/telegram/webhook"
    health_url = f"{railway_url}/health"

    print("1. Checking if app is reachable...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(health_url)
            if r.status_code == 200 and (r.json() or {}).get("status") == "healthy":
                print(f"   OK  GET {health_url} -> {r.json()}")
            else:
                print(f"   FAIL GET {health_url} -> {r.status_code} {r.text[:200]}")
                sys.exit(1)
    except Exception as e:
        print(f"   FAIL {e}")
        sys.exit(1)

    if not token:
        print("2. TELEGRAM_BOT_TOKEN not set — skipping webhook check.")
        print("   Set it to verify where Telegram sends /help and other updates.")
        return

    print("2. Checking Telegram webhook...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{TELEGRAM_API_BASE}{token}/getWebhookInfo")
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                print(f"   FAIL getWebhookInfo: {data}")
                sys.exit(1)
            info = data.get("result", {})
            current = info.get("url") or "(not set)"
            print(f"   Current webhook URL: {current}")
            if current != webhook_url:
                print(f"   Expected:            {webhook_url}")
                print("   -> Telegram is not sending updates to your Railway app.")
                print("   Fix: python scripts/set_webhook.py set", webhook_url)
                sys.exit(1)
            print("   OK  Webhook points to your Railway app.")
    except Exception as e:
        print(f"   FAIL {e}")
        sys.exit(1)

    print("\nAll checks passed. Try sending /help to your bot in Telegram.")


if __name__ == "__main__":
    asyncio.run(main())
