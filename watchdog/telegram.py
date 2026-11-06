import asyncio
import logging

import httpx

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


async def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram notification skipped: credentials not configured.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                },
            )
            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                logger.error("Telegram API rejected notification.")
                return False

            return True

    except (httpx.HTTPError, ValueError) as error:
        logger.error(
            "Telegram notification failed: %s",
            type(error).__name__,
        )
        return False


def send_telegram_sync(message: str) -> bool:
    try:
        return asyncio.run(send_telegram(message))
    except RuntimeError:
        logger.error(
            "Cannot send synchronous Telegram notification in active event loop."
        )
        return False
