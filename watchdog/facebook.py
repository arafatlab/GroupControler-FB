import logging
import httpx

from config import (
    FACEBOOK_ADMIN_ID,
    FACEBOOK_NOTIFICATIONS_ENABLED,
    COOKIE_FILE,
)
from fbchat_v2 import SendAPI
from fbchat_v2._features._facebook import _get_user_info
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

        result = await SendAPI().send(
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


async def send_group_welcome(
    group_id: str,
    member_id: str,
    session: dict,
) -> bool:
    """Fetch the member's full Facebook name and welcome them in the group."""

    if not FACEBOOK_NOTIFICATIONS_ENABLED:
        return False

    try:
        user_info = await _get_user_info.func(
            session,
            str(member_id),
        )

        full_name = (
            user_info.get("nameUser", "").strip()
            if isinstance(user_info, dict)
            else ""
        )

        if not full_name:
            logger.warning(
                "Group welcome skipped: full name unavailable."
            )
            return False

        message = (
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "       🎉 WELCOME ABOARD 🎉\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            f"💗 Hey {full_name}!\n\n"
            "We're really happy to have you here! 🥰\n"
            "Make yourself comfortable, meet new friends "
            "and enjoy your time with us. ✨\n\n"
            "🌸 Stay active • Spread kindness • Have fun\n\n"
            "       ❤️ ENJOY YOUR STAY ❤️"
        )

        result = await SendAPI().send(
            dataFB=session,
            contentSend=message,
            threadID=str(group_id),
            typeChat=None,
        )

        if not isinstance(result, dict) or not result.get("success"):
            logger.error("Facebook API did not confirm group welcome.")
            return False

        logger.info("Group welcome sent successfully.")
        return True

    except httpx.HTTPStatusError as error:
        logger.error(
            "Facebook rejected group welcome | status=%s",
            error.response.status_code,
        )
        return False

    except Exception as error:
        logger.error(
            "Group welcome failed: %s",
            type(error).__name__,
        )
        return False




async def send_group_goodbye(
    group_id: str,
    member_id: str,
    session: dict,
) -> bool:
    """Send a group goodbye using the member's full Facebook name."""

    if not FACEBOOK_NOTIFICATIONS_ENABLED:
        return False

    try:
        user_info = await _get_user_info.func(session, str(member_id))

        full_name = (
            user_info.get("nameUser", "").strip()
            if isinstance(user_info, dict)
            else ""
        )

        if not full_name:
            logger.warning("Group goodbye skipped: full name unavailable.")
            return False

        message = (
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "         😢 GOODBYE 😢\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            f"💔 Hey {full_name}!\n\n"
            "Looks like it's time to say goodbye. "
            "We'll miss having you around! 🥺\n\n"
            "No matter what, you're always welcome "
            "to come back anytime. ❤️\n\n"
            "🌷 Take care and stay happy!\n\n"
            "       👋 UNTIL WE MEET AGAIN"
        )

        result = await SendAPI().send(
            dataFB=session,
            contentSend=message,
            threadID=str(group_id),
            typeChat=None,
        )

        if not isinstance(result, dict) or not result.get("success"):
            logger.error("Facebook API did not confirm group goodbye.")
            return False

        logger.info("Group goodbye sent successfully.")
        return True

    except httpx.HTTPStatusError as error:
        logger.error(
            "Facebook rejected group goodbye | status=%s",
            error.response.status_code,
        )
        return False

    except Exception as error:
        logger.error("Group goodbye failed: %s", type(error).__name__)
        return False




async def send_group_removal_question(
    group_id: str,
    member_id: str,
    session: dict,
) -> bool:
    """Notify the group and privately contact a removed member."""

    if not FACEBOOK_NOTIFICATIONS_ENABLED:
        return False

    try:
        user_info = await _get_user_info.func(session, str(member_id))
        full_name = (
            user_info.get("nameUser", "").strip()
            if isinstance(user_info, dict)
            else ""
        )

        if not full_name:
            logger.warning("Removal question skipped: name unavailable.")
            return False

        message = (
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "       ⚠️ MEMBER REMOVED ⚠️\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            f"👤 Member: {full_name}\n\n"
            "A member has been removed from this group.\n\n"
            "💬 Could the admin responsible please share "
            "the reason for this action?\n\n"
            "We'd appreciate a little clarification so "
            "everyone can understand what happened. ❤️\n\n"
            "       🤝 THANK YOU"
        )

        group_sent = False
        inbox_sent = False

        # Send notification to the group
        try:
            result = await SendAPI().send(
                dataFB=session,
                contentSend=message,
                threadID=str(group_id),
                typeChat=None,
            )
            group_sent = isinstance(result, dict) and bool(result.get("success"))
        except Exception:
            logger.exception("Group removal notification failed.")

        # Send a private message to the removed member
        private_message = (
            f"⚠️ Hey {full_name}!\\n"
            "We noticed that you were removed from the group. "
            "Could you tell us what happened? "
            "Was there any misunderstanding or issue? ❤️"
        )

        try:
            result = await SendAPI().send(
                dataFB=session,
                contentSend=private_message,
                threadID=str(member_id),
                typeChat="user",
            )
            inbox_sent = isinstance(result, dict) and bool(result.get("success"))
        except Exception:
            logger.exception("Private removal message failed.")

        logger.info(
            "Removal notifications: group=%s inbox=%s member=%s",
            group_sent,
            inbox_sent,
            member_id,
        )

        return group_sent or inbox_sent

    except Exception:
        logger.exception("Removal question preparation failed.")
        return False



def send_facebook_sync(message: str) -> bool:
    import asyncio

    try:
        return asyncio.run(send_facebook(message))
    except RuntimeError:
        logger.error(
            "Cannot send Facebook notification in an active event loop."
        )
        return False
