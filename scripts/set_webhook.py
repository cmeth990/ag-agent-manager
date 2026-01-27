#!/usr/bin/env python3
"""Helper script to set Telegram webhook URL."""
import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


async def set_webhook(url: str):
    """Set Telegram webhook URL."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set in environment")
        sys.exit(1)
    
    webhook_url = f"{TELEGRAM_API_BASE}{token}/setWebhook"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json={"url": url})
        response.raise_for_status()
        result = response.json()
        
        if result.get("ok"):
            print(f"✅ Webhook set successfully: {url}")
        else:
            print(f"❌ Failed to set webhook: {result}")
            sys.exit(1)


async def get_webhook_info():
    """Get current webhook information."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set in environment")
        sys.exit(1)
    
    url = f"{TELEGRAM_API_BASE}{token}/getWebhookInfo"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        result = response.json()
        
        if result.get("ok"):
            info = result.get("result", {})
            print(f"Webhook URL: {info.get('url', 'Not set')}")
            print(f"Pending updates: {info.get('pending_update_count', 0)}")
            if info.get("last_error_date"):
                print(f"Last error: {info.get('last_error_message')}")
        else:
            print(f"❌ Failed to get webhook info: {result}")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/set_webhook.py set <url>  - Set webhook URL")
        print("  python scripts/set_webhook.py info       - Get webhook info")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "set":
        if len(sys.argv) < 3:
            print("Error: URL required")
            print("Usage: python scripts/set_webhook.py set <url>")
            sys.exit(1)
        url = sys.argv[2]
        asyncio.run(set_webhook(url))
    elif command == "info":
        asyncio.run(get_webhook_info())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
