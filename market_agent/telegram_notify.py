"""Send messages to Telegram when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
import os
import requests

def send_message(text: str) -> None:
    """Send a text message to Telegram. No-op if token or chat_id is missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass  # Don't fail the request if Telegram fails
