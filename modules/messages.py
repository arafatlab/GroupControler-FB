from collections import deque

from fbchat_v2 import SendAPI

from modules.ai_engine import AIEngine
from modules.memory import MemoryStore
from modules.ff_checker import GamesKinbo, GamesKinboError, format_player

from config import DRY_RUN, GROUP_COMMAND


class AIMessageHandler:

    def __init__(self, session):
        self.session = session
        self.sender_id = str(session.get("FacebookID") or "")

        self.api = SendAPI()
        self.ai = AIEngine()
        self.memory = MemoryStore()
        self.ff_checker = GamesKinbo()

        self.dry_run = DRY_RUN
        self.prefix = GROUP_COMMAND.strip()

        self.processed_ids = set()
        self.processed_order = deque(maxlen=500)

    def is_duplicate(self, message_id):
        if not message_id:
            return False

        message_id = str(message_id)

        if message_id in self.processed_ids:
            return True

        if len(self.processed_order) == self.processed_order.maxlen:
            oldest = self.processed_order.popleft()
            self.processed_ids.discard(oldest)

        self.processed_order.append(message_id)
        self.processed_ids.add(message_id)

        return False

    async def send_group_reply(self, thread_id, message_id, reply):

        if self.dry_run:
            print("\n[DRY RUN] Group reply:")
            print(reply)
            print("[DRY RUN] Message not sent.")
            return

        if not message_id:
            print("[-] Original message ID missing.")
            return

        result = await self.api.send(
            dataFB=self.session,
            contentSend=reply,
            threadID=thread_id,
            typeChat=None,
            replyMessage=True,
            messageID=str(message_id),
        )

        if not isinstance(result, dict) or not result.get("success"):
            print("[-] Facebook did not confirm the message.")
            return

        print("[+] Group reply sent successfully.")

    async def handle_ff(self, uid, thread_id, message_id):

        print("\n[FREE FIRE CHECKER]")
        print("UID:", uid or "Missing")

        if not uid:
            await self.send_group_reply(
                thread_id,
                message_id,
                "Usage: /ff <Free Fire UID>\nExample: /ff 123456789",
            )
            return

        try:
            player = await self.ff_checker.check_player(uid)
            reply = format_player(player)

            print(reply)

            await self.send_group_reply(
                thread_id,
                message_id,
                reply,
            )

        except ValueError as error:
            print("[-] Invalid UID:", error)

            await self.send_group_reply(
                thread_id,
                message_id,
                f"⚠️ Invalid UID: {error}",
            )

        except GamesKinboError as error:
            print("[-] GamesKinbo error:", error)

            await self.send_group_reply(
                thread_id,
                message_id,
                "⚠️ Free Fire checker is temporarily unavailable. Please try again later.",
            )

        except Exception as error:
            print(
                "[-] Free Fire error:",
                type(error).__name__,
                str(error),
            )

            await self.send_group_reply(
                thread_id,
                message_id,
                "⚠️ An unexpected error occurred while checking the UID.",
            )

    def get_user_text(self, message):

        if not self.prefix:
            return None

        body = message.get("body")

        if not isinstance(body, str):
            return None

        body = body.strip()

        if not body:
            return None

        message_type = message.get("type")

        # Group: only configured AI command
        if message_type == "thread":

            parts = body.split(maxsplit=1)

            if len(parts) != 2:
                return None

            if parts[0].casefold() != self.prefix.casefold():
                return None

            return parts[1].strip() or None

        # Personal chat: any text message
        if message_type == "user":
            return body

        return None

    async def handle(self, message):

        if not isinstance(message, dict):
            return

        sender_id = str(message.get("userID") or "")

        # Ignore own messages
        if not sender_id or sender_id == self.sender_id:
            return

        message_id = message.get("messageID")

        if self.is_duplicate(message_id):
            return

        thread_id = message.get("replyToID")
        message_type = message.get("type")
        body = message.get("body")

        is_swipe_reply = message.get("is_swipe_reply") is True

        # Swipe replies are accepted only when targeting the bot's own message.
        if is_swipe_reply:
            if (
                message_type != "thread"
                or str(message.get("replied_to_user_id") or "") != self.sender_id
            ):
                print("[SWIPE REPLY IGNORED] Target is not the bot.")
                return

        if not thread_id:
            return

        # Free Fire checker: group only
        if message_type == "thread" and isinstance(body, str):

            parts = body.strip().split()

            if parts and parts[0].casefold() == "/ff":

                if len(parts) == 2:
                    uid = parts[1]
                else:
                    uid = None

                await self.handle_ff(
                    uid,
                    thread_id,
                    message_id,
                )
                return

        # Existing Anu AI handler
        user_text = (
            body.strip()
            if is_swipe_reply and isinstance(body, str)
            else self.get_user_text(message)
        )

        if not user_text:
            return

        print("\n[ANU AI]")
        print(f"User ID   : {sender_id}")
        print(f"Chat Type : {message_type}")
        print(f"Message   : {user_text}")

        user_memory = self.memory.load(sender_id)
        history = user_memory.get("history", [])

        try:
            reply = await self.ai.generate_reply(
                user_text=user_text,
                history=history,
            )

            if not reply:
                print("[-] AI returned no response.")
                return

            print(f"[ANU]: {reply}")

            if self.dry_run:
                print("[DRY RUN] Message not sent.")
                return

            if message_type == "thread":

                if not message_id:
                    print("[-] Original message ID missing.")
                    return

                result = await self.api.send(
                    dataFB=self.session,
                    contentSend=reply,
                    threadID=thread_id,
                    typeChat=None,
                    replyMessage=True,
                    messageID=str(message_id),
                )

            else:

                result = await self.api.send(
                    dataFB=self.session,
                    contentSend=reply,
                    threadID=thread_id,
                    typeChat="user",
                )

            if not isinstance(result, dict) or not result.get("success"):
                print("[-] Facebook did not confirm the message.")
                return

            print("[+] AI reply sent successfully.")

            self.memory.add_exchange(
                sender_id,
                user_text,
                reply,
            )

            print("[+] User memory updated.")

        except Exception as error:
            print(
                "[-] AI message error:",
                type(error).__name__,
                str(error),
            )

    async def close(self):
        await self.ai.close()
        await self.ff_checker.close()
