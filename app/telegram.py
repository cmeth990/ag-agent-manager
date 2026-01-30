"""Telegram Bot API utilities for sending messages and handling callbacks."""
import os
import httpx
from typing import Optional, Dict, Any, Union


TELEGRAM_API_BASE = "https://api.telegram.org/bot"


def get_bot_token() -> str:
    """Get bot token from environment variable."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    # Clean token - remove any whitespace/newlines that might have been added
    token = token.strip()
    # Remove any newlines or carriage returns
    token = token.replace('\n', '').replace('\r', '')
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
    # Clean text - Telegram API can handle newlines in message text
    # But ensure no other problematic control characters
    if text:
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Remove any control characters except newline and tab (Telegram supports these)
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    
    token = get_bot_token()
    # Ensure URL is clean - no newlines in token or base URL
    base_url = TELEGRAM_API_BASE.strip().replace('\n', '').replace('\r', '')
    clean_token = token.strip().replace('\n', '').replace('\r', '')
    url = f"{base_url}{clean_token}/sendMessage"
    
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


async def send_photo(
    chat_id: int,
    photo: Union[bytes, str],
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a photo to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID
        photo: PNG/JPEG bytes or file_id/URL string
        caption: Optional caption
        parse_mode: Optional parse mode for caption (e.g. "Markdown", "HTML")
    
    Returns:
        API response dict
    """
    token = get_bot_token()
    url = f"{TELEGRAM_API_BASE}{token}/sendPhoto"
    
    if isinstance(photo, bytes):
        async with httpx.AsyncClient() as client:
            payload: Dict[str, Any] = {"chat_id": str(chat_id)}
            if caption:
                payload["caption"] = caption[:1024]
            if parse_mode:
                payload["parse_mode"] = parse_mode
            files = {"photo": ("progress.png", photo, "image/png")}
            response = await client.post(url, data=payload, files=files)
    else:
        payload = {"chat_id": chat_id, "photo": photo}
        if caption:
            payload["caption"] = caption
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
