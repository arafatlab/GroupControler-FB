import logging
import httpx

from config import (
    FACEBOOK_ADMIN_ID,
    FACEBOOK_NOTIFICATIONS_ENABLED,
    COOKIE_FILE,
)
from fbchat_v2 import SendAPI
from core.session import create_session

logger = logging.getLogger(__name__)


async def send_facebook(message: str, session: dict | None = None) -> bool:
    if not FACEBOOK_NOTIFICATIONS_ENABLED:
        return False

    if not FACEBOOK_ADMIN_ID:
        logger.warning("Facebook notification skipped: admin ID missing.")
        return False

    try:
        if session is None:
            session = await create_session()

        if not session:
            logger.error("Facebook notification failed: session unavailable.")
            return False

        api = SendAPI()

        result = await api.send(
            dataFB=session,
            contentSend=message,
            threadID=FACEBOOK_ADMIN_ID,
            typeChat="user",
        )

        if not isinstance(result, dict) or not result.get("success"):
            logger.error("Facebook API did not confirm admin notification.")
            return False

        logger.info("Facebook admin notification sent.")
        return True

    except httpx.HTTPStatusError as error:
        response = error.response
        logger.error(
            "Facebook API rejected notification | status=%s | "
            "content_type=%s | server=%s | response_bytes=%s",
            response.status_code,
            response.headers.get("content-type", "unknown"),
            response.headers.get("server", "unknown"),
            len(response.content),
        )
        return False

    except Exception as error:
        logger.error(
            "Facebook notification failed: %s",
            type(error).__name__,
        )
        return False


def send_facebook_sync(message: str) -> bool:
    import asyncio

    try:
        return asyncio.run(send_facebook(message))
    except RuntimeError:
        logger.error("Cannot send Facebook notification in an active event loop.")
        return False
