import httpx
import logging

logger = logging.getLogger(__name__)

async def notify_discord(webhook_url: str, message: str, color: int = 65280): # Default green
    """
    Sends a rich embed message to a Discord webhook.
    """
    payload = {
        "embeds": [
            {
                "title": "WakeDeck Notice",
                "description": message,
                "color": color
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            return True, "Notification sent"
    except Exception as e:
        logger.error(f"Discord notification failed: {str(e)}")
        return False, str(e)

async def notify_telegram(bot_token: str, chat_id: str, message: str):
    """
    Sends a message to a Telegram bot.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=5.0)
            response.raise_for_status()
            return True, "Notification sent"
    except Exception as e:
        logger.error(f"Telegram notification failed: {str(e)}")
        return False, str(e)
