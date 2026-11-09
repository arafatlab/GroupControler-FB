import asyncio

from core.connection import MessengerConnection
from modules.messages import AIMessageHandler
from utils.formatter import format_message
from watchdog.telegram import send_telegram
from watchdog.facebook import send_facebook, send_group_welcome, send_group_goodbye, send_group_removal_question


class Messenger:
    def __init__(self, session):
        self.session = session
        self.connection = MessengerConnection(session)
        self.ai_handler = AIMessageHandler(session)
        self._running = False
        self._closed = False
        self._notification_tasks = set()

    async def _handle_connection_event(self, status):
        state = status.get("state", "unknown")
        reason = status.get("reason", "")
        attempt = status.get("attempt", 0)

        print(
            f"[CONNECTION] {state} | "
            f"reason={reason} | attempt={attempt}"
        )

        messages = {
            "connected": (
                "✅ Facebook Messenger connected successfully."
            ),
            "reconnecting": (
                f"⚠️ Facebook connection lost.\n"
                f"Reason: {reason or 'unknown'}\n"
                f"Attempt: {attempt}"
            ),
            "auth_required": (
                f"🔒 Facebook authentication required.\n"
                f"Reason: {reason or 'unknown'}"
            ),
            "fatal": (
                f"🚨 Facebook connection failed permanently.\n"
                f"Reason: {reason or 'unknown'}"
            ),
        }

        message = messages.get(state)

        if message:
            task = asyncio.create_task(send_telegram(message))
            self._notification_tasks.add(task)
            task.add_done_callback(self._notification_tasks.discard)

    async def _handle_group_event(self, event):
        event_type = event.get("type")
        group_id = event.get("group_id", "unknown")

        # A new member was added to a group.
        if event_type == "member_added":
            task = asyncio.create_task(
                send_group_welcome(
                    group_id=str(group_id),
                    member_id=str(event.get("member_id", "")),
                    session=self.session,
                )
            )

            self._notification_tasks.add(task)
            task.add_done_callback(self._notification_tasks.discard)
            return

        if event_type == "member_left":
            task = asyncio.create_task(
                send_group_goodbye(
                    group_id=str(group_id),
                    member_id=str(event.get("member_id", "")),
                    session=self.session,
                )
            )

            self._notification_tasks.add(task)
            task.add_done_callback(self._notification_tasks.discard)
            return

        if event_type == "member_removed":
            task = asyncio.create_task(
                send_group_removal_question(
                    group_id=str(group_id),
                    member_id=str(event.get("member_id", "")),
                    session=self.session,
                )
            )
            self._notification_tasks.add(task)
            task.add_done_callback(self._notification_tasks.discard)
            return

        # Existing bot membership notifications remain unchanged.
        actor_id = event.get("actor_id", "unknown")

        if event_type == "added":
            status = "🟢 Bot account was ADDED to a group."
        elif event_type == "removed":
            status = "🔴 Bot account was REMOVED from a group."
        else:
            return

        group_name = (
            self.connection.get_group_name(str(group_id))
            or "Unknown Group"
        )

        message = (
            f"🤖 Facebook Group Update\n"
            f"\n"
            f"{status}\n"
            f"\n"
            f"Group: {group_name}\n"
            f"Group ID: {group_id}\n"
            f"Action by: {actor_id}"
        )

        task = asyncio.create_task(
            send_facebook(message, session=self.session)
        )

        self._notification_tasks.add(task)
        task.add_done_callback(self._notification_tasks.discard)

    async def start(self):
        self._running = True

        print("[+] Messenger listener initialized.")
        print(f"[AI] DRY RUN: {self.ai_handler.dry_run}")

        connection_task = asyncio.create_task(
            self.connection.connect()
        )

        try:
            while self._running and not connection_task.done():
                message = await self.connection.receive(timeout=1)

                if message is not None:
                    print(format_message(message))
                    await self.ai_handler.handle(message)

                while True:
                    event = await self.connection.get_state_event(
                        timeout=0.01
                    )

                    if event is None:
                        break

                    await self._handle_connection_event(event)

                while True:
                    group_event = await self.connection.get_group_event(
                        timeout=0.01
                    )

                    if group_event is None:
                        break

                    await self._handle_group_event(group_event)

            await connection_task

        finally:
            self._running = False

            if not connection_task.done():
                connection_task.cancel()

                await asyncio.gather(
                    connection_task,
                    return_exceptions=True,
                )

            await self.connection.disconnect()

    async def stop(self):
        self._running = False
        await self.connection.disconnect()

        if not self._closed:
            await self.ai_handler.close()
            self._closed = True

        if self._notification_tasks:
            await asyncio.gather(
                *self._notification_tasks,
                return_exceptions=True,
            )
