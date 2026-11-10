import asyncio

from core.connection import MessengerConnection
from modules.messages import AIMessageHandler
from modules.groups import HELP_TEXT
from fbchat_v2 import SendAPI
from config import BOT_NICKNAME, DRY_RUN
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
        self._reminder_task = None
        self._member_sync_task = None
        self._known_group_ids = set()
        self._member_sync_locks = {}

    async def _reminder_loop(self):
        handler = self.ai_handler.group_handler
        store = handler.store

        while self._running:
            try:
                reminders = store.get_due_reminders()

                for reminder in reminders:
                    reminder_id = reminder["id"]
                    thread_id = str(reminder["thread_id"])

                    message = (
                        f"⏰ REMINDER #{reminder_id}\\n"
                        f"{reminder['message']}"
                    )

                    try:
                        sent = await handler.send(thread_id, message)

                        if sent:
                            store.mark_reminder_delivered(reminder_id)
                            print(f"[REMINDER] Delivered #{reminder_id}")

                    except Exception as error:
                        print(
                            "[REMINDER ERROR]",
                            reminder_id,
                            type(error).__name__,
                            str(error),
                        )

            except Exception as error:
                print(
                    "[REMINDER SCHEDULER ERROR]",
                    type(error).__name__,
                    str(error),
                )

            await asyncio.sleep(15)

    async def _handle_bot_added(self, group_id):
        group_id = str(group_id)

        handler = self.ai_handler.group_handler
        group_api = handler.groups
        store = handler.store

        if DRY_RUN:
            print(
                f"[DRY RUN] Bot onboarding skipped for group {group_id}"
            )
            return

        try:
            # Set bot nickname.
            try:
                await group_api.set_nickname(
                    group_id,
                    handler.bot_id,
                    BOT_NICKNAME,
                )

                print(
                    f"[ONBOARDING] Nickname updated in group {group_id}"
                )

            except Exception as error:
                print(
                    "[ONBOARDING] Nickname update failed:",
                    type(error).__name__,
                    str(error),
                )

            # Retrieve group administrators.
            admins = await group_api.get_admin_ids(group_id)
            api = SendAPI()

            intro = (
                "🌸 Hello! I'm HINATA, your group assistant.\\n\\n"
                "Thank you for adding me to your group!\\n\\n"
                "Please make me a group Admin so my admin commands "
                "can work. Open Group Info → Admins → Add Admin "
                "and select my account.\\n\\n"
                "Here is my command guide:\\n\\n"
                f"{HELP_TEXT}"
            )

            for admin_id in admins:
                admin_id = str(admin_id)

                if store.onboarding_was_sent(group_id, admin_id):
                    continue

                try:
                    result = await api.send(
                        dataFB=self.session,
                        contentSend=intro,
                        threadID=admin_id,
                        typeChat="user",
                    )

                    if (
                        isinstance(result, dict)
                        and result.get("success")
                    ):
                        store.mark_onboarding_sent(group_id, admin_id)

                        print(
                            "[ONBOARDING] Introduction sent to admin",
                            admin_id,
                        )
                    else:
                        print(
                            "[ONBOARDING] Facebook did not confirm DM:",
                            admin_id,
                        )

                except Exception as error:
                    print(
                        "[ONBOARDING DM ERROR]",
                        admin_id,
                        type(error).__name__,
                        str(error),
                    )

        except Exception as error:
            print(
                "[ONBOARDING ERROR]",
                group_id,
                type(error).__name__,
                str(error),
            )

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

    async def _sync_group_members(self, group_id):
        group_id = str(group_id)
        lock = self._member_sync_locks.setdefault(
            group_id, asyncio.Lock()
        )

        async with lock:
            try:
                handler = self.ai_handler.group_handler
                changes = await handler.groups.sync_group_members(
                    group_id, handler.store
                )

                for member in changes.get("promoted", []):
                    name = member.get("name") or member["user_id"]
                    await handler.send(
                        group_id,
                        f"🎉 অভিনন্দন {name}! আপনাকে Group Admin করা হয়েছে।"
                    )

                for member in changes.get("demoted", []):
                    name = member.get("name") or member["user_id"]
                    await handler.send(
                        group_id,
                        f"ℹ️ {name}-এর Group Admin দায়িত্ব পরিবর্তন হয়েছে।"
                    )

                counts = {
                    key: len(changes.get(key, []))
                    for key in ("joined", "left", "promoted", "demoted")
                }
                if any(counts.values()):
                    print(f"[MEMBER SYNC] Group {group_id}: {counts}")

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[MEMBER SYNC] Group {group_id} failed: {exc}")

    async def _member_sync_loop(self):
        while self._running:
            for group_id in list(self._known_group_ids):
                if not self._running:
                    break
                await self._sync_group_members(group_id)

            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise

    async def _handle_group_event(self, event):
        event_type = event.get("type")
        group_id = event.get("group_id", "unknown")

        if group_id != "unknown":
            group_id = str(group_id)
            self._known_group_ids.add(group_id)
            sync_task = asyncio.create_task(
                self._sync_group_members(group_id)
            )
            self._notification_tasks.add(sync_task)
            sync_task.add_done_callback(
                self._notification_tasks.discard
            )

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
            onboarding_task = asyncio.create_task(
                self._handle_bot_added(str(group_id))
            )

            self._notification_tasks.add(onboarding_task)
            onboarding_task.add_done_callback(
                self._notification_tasks.discard
            )

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

        if self._member_sync_task is None or self._member_sync_task.done():
            self._member_sync_task = asyncio.create_task(
                self._member_sync_loop()
            )

        if self._reminder_task is None or self._reminder_task.done():
            self._reminder_task = asyncio.create_task(
                self._reminder_loop()
            )

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

            if self._reminder_task and not self._reminder_task.done():
                self._reminder_task.cancel()
                await asyncio.gather(
                    self._reminder_task,
                    return_exceptions=True,
                )

            self._reminder_task = None

            if self._member_sync_task and not self._member_sync_task.done():
                self._member_sync_task.cancel()
                await asyncio.gather(
                    self._member_sync_task,
                    return_exceptions=True,
                )
            self._member_sync_task = None

            if not connection_task.done():
                connection_task.cancel()

                await asyncio.gather(
                    connection_task,
                    return_exceptions=True,
                )

            await self.connection.disconnect()

    async def stop(self):
        self._running = False

        if self._reminder_task and not self._reminder_task.done():
            self._reminder_task.cancel()
            await asyncio.gather(
                self._reminder_task,
                return_exceptions=True,
            )

        self._reminder_task = None

        if self._member_sync_task and not self._member_sync_task.done():
            self._member_sync_task.cancel()
            await asyncio.gather(
                self._member_sync_task,
                return_exceptions=True,
            )
        self._member_sync_task = None

        await self.connection.disconnect()

        if not self._closed:
            await self.ai_handler.close()
            self._closed = True

        if self._notification_tasks:
            await asyncio.gather(
                *self._notification_tasks,
                return_exceptions=True,
            )
