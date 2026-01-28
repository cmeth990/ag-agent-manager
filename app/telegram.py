"""Telegram Bot API utilities for sending messages and handling callbacks."""
import os
import httpx
from typing import Optional, Dict, Any


TELEGRAM_API_BASE = "https://api.telegram.org/bot"


def get_bot_token() -> str:
    """Get bot token from environment variable."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    return token


async def send_message(
    chat_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a message to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID
        text: Message text
        reply_markup: Optional inline keyboard markup
        parse_mode: Optional parse mode (e.g., "Markdown", "HTML")
    
    Returns:
        API response dict
    """
    # Clean text - remove any problematic characters that could break URLs
    if text:
        # Remove newlines and other control characters that could break JSON/URL encoding
        text = text.replace('\r\n', '\n').replace('\r', '\n')  # Normalize line endings
        # Telegram API can handle \n in text, but we need to ensure no other control chars
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    
    token = get_bot_token()
    url = f"{TELEGRAM_API_BASE}{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False
) -> Dict[str, Any]:
    """
    Answer a callback query (button press).
    
    Args:
        callback_query_id: Callback query ID from Telegram
        text: Optional text to show to user
        show_alert: If True, show as alert; if False, show as notification
    
    Returns:
        API response dict
    """
    token = get_bot_token()
    url = f"{TELEGRAM_API_BASE}{token}/answerCallbackQuery"
    
    payload = {
        "callback_query_id": callback_query_id,
    }
    
    if text:
        payload["text"] = text
    
    if show_alert:
        payload["show_alert"] = True
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def build_approval_keyboard(diff_id: str) -> Dict[str, Any]:
    """
    Build inline keyboard markup for Approve/Reject buttons.
    
    Args:
        diff_id: Unique identifier for the proposed diff
    
    Returns:
        Inline keyboard markup dict
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve",
                    "callback_data": f"approve:{diff_id}"
                },
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject:{diff_id}"
                }
            ]
        ]
    }


async def set_webhook(url: str) -> Dict[str, Any]:
    """
    Set Telegram webhook URL.
    
    Args:
        url: Full HTTPS URL for webhook endpoint
    
    Returns:
        API response dict
    """
    token = get_bot_token()
    webhook_url = f"{TELEGRAM_API_BASE}{token}/setWebhook"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json={"url": url})
        response.raise_for_status()
        return response.json()


async def get_webhook_info() -> Dict[str, Any]:
    """Get current webhook information."""
    token = get_bot_token()
    url = f"{TELEGRAM_API_BASE}{token}/getWebhookInfo"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
