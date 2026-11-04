
from collections import deque

from fbchat_v2 import SendAPI

from modules.ai_engine import AIEngine
from modules.memory import MemoryStore
from config import DRY_RUN, GROUP_COMMAND, GROUP_COMMAND


class AIMessageHandler:

    def __init__(self, session):
        self.session = session
        self.sender_id = str(session.get("FacebookID") or "")

        self.api = SendAPI()
        self.ai = AIEngine()
        self.memory = MemoryStore()

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

        # Group: only /noun command
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

        user_text = self.get_user_text(message)

        if not user_text:
            return

        thread_id = message.get("replyToID")
        message_type = message.get("type")

        if not thread_id:
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
                history=history
            )

            if not reply:
                print("[-] AI returned no response.")
                return

            print(f"[ANU]: {reply}")

            if self.dry_run:
                print("[DRY RUN] Message not sent.")
                return

            # Native Messenger reply for group messages
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

            # Normal send for personal chat
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
                reply
            )

            print("[+] User memory updated.")

        except Exception as error:
            print(
                f"[-] AI message error: "
                f"{type(error).__name__}: {error}"
            )

    async def close(self):
        await self.ai.close()
