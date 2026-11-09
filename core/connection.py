import asyncio
import json
from typing import Any

from fbchat_v2 import listeningEvent
from config import MESSAGE_QUEUE_SIZE


class GroupAwareListener(listeningEvent):
    """Detect bot membership changes and newly added group participants."""

    def configure_group_events(self, bot_id, loop, event_queue):
        self.bot_id = str(bot_id)
        self.event_loop = loop
        self.group_event_queue = event_queue

    def _queue_group_event(self, event):
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.call_soon_threadsafe(
                self.group_event_queue.put_nowait, event
            )

    def _body_from_delta(self, delta: Any):
        # Facebook sends swipe replies inside a ClientPayload.
        if isinstance(delta, dict) and delta.get("class") == "ClientPayload":
            try:
                raw_payload = bytes(delta.get("payload", []))
                payload = json.loads(raw_payload.decode("utf-8"))

                for item in payload.get("deltas", []):
                    if not isinstance(item, dict):
                        continue

                    reply_event = item.get("deltaMessageReply")
                    if not isinstance(reply_event, dict):
                        continue

                    target = reply_event.get("repliedToMessage")
                    new_message = reply_event.get("message")

                    if not isinstance(target, dict) or not isinstance(new_message, dict):
                        continue

                    target_metadata = target.get("messageMetadata")
                    if not isinstance(target_metadata, dict):
                        continue

                    new_metadata = new_message.get("messageMetadata")
                    if not isinstance(new_metadata, dict):
                        continue

                    thread_key = new_metadata.get("threadKey")
                    if not isinstance(thread_key, dict) or not thread_key.get("threadFbId"):
                        continue

                    normalized = super()._body_from_delta(new_message)
                    if normalized is None:
                        continue

                    normalized["is_swipe_reply"] = True
                    normalized["replied_to_user_id"] = str(
                        target_metadata.get("actorFbId") or ""
                    )
                    normalized["replied_to_message_id"] = target_metadata.get("messageId")

                    print(
                        "[SWIPE REPLY DETECTED] sender:",
                        normalized.get("userID"),
                        "| replied-to:",
                        normalized["replied_to_user_id"],
                        "| message:",
                        normalized.get("body"),
                        flush=True,
                    )
                    return normalized

            except Exception as error:
                print("[SWIPE REPLY PARSE ERROR]", repr(error), flush=True)

            return None
        if isinstance(delta, dict) and not isinstance(delta.get("messageMetadata"), dict):
            return None

        body = super()._body_from_delta(delta)

        if not isinstance(delta, dict):
            return body

        event_class = delta.get("class")

        if event_class not in {
            "ParticipantsAddedToGroupThread",
            "ParticipantLeftGroupThread",
        }:
            return body

        metadata = delta.get("messageMetadata")

        if not isinstance(metadata, dict):
            return None

        thread_key = metadata.get("threadKey")

        if not isinstance(thread_key, dict):
            return None

        group_id = thread_key.get("threadFbId")
        actor_id = metadata.get("actorFbId")

        if not group_id:
            return None

        actor_id = str(actor_id) if actor_id is not None else "unknown"

        if event_class == "ParticipantsAddedToGroupThread":
            participants = delta.get("addedParticipants")

            if not isinstance(participants, list):
                return None

            added_ids = [
                str(item.get("userFbId"))
                for item in participants
                if isinstance(item, dict)
                and item.get("userFbId") is not None
            ]

            # Preserve the existing bot-added notification.
            if self.bot_id and self.bot_id in added_ids:
                self._queue_group_event({
                    "type": "added",
                    "group_id": str(group_id),
                    "actor_id": actor_id,
                })

            # Welcome every newly added participant except the bot itself.
            for member_id in added_ids:
                if member_id == self.bot_id:
                    continue

                self._queue_group_event({
                    "type": "member_added",
                    "group_id": str(group_id),
                    "member_id": member_id,
                    "actor_id": actor_id,
                })

        else:
            left_id = delta.get("leftParticipantFbId")

            if left_id is None:
                return None

            left_id = str(left_id)

            if self.bot_id and left_id == self.bot_id:
                self._queue_group_event({
                    "type": "removed",
                    "group_id": str(group_id),
                    "actor_id": actor_id,
                })
            elif actor_id == left_id:
                self._queue_group_event({
                    "type": "member_left",
                    "group_id": str(group_id),
                    "member_id": left_id,
                    "actor_id": actor_id,
                })
            else:
                self._queue_group_event({
                    "type": "member_removed",
                    "group_id": str(group_id),
                    "member_id": left_id,
                    "actor_id": actor_id,
                })

        return None


class MessengerConnection:
    def __init__(self, session):
        self.session = session
        self.loop = None
        self.state_queue = asyncio.Queue()
        self.group_event_queue = asyncio.Queue()

        self.listener = GroupAwareListener(
            session,
            message_queue_maxsize=MESSAGE_QUEUE_SIZE,
            on_connection_state=self._on_connection_state,
        )

    def _on_connection_state(self, status: dict):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(
                self.state_queue.put_nowait, status
            )

    async def get_state_event(self, timeout=1):
        try:
            return await asyncio.wait_for(
                self.state_queue.get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    async def get_group_event(self, timeout=0.1):
        try:
            return await asyncio.wait_for(
                self.group_event_queue.get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    @property
    def state(self):
        return self.listener.connection_state

    @property
    def status(self):
        return self.listener.connection_status

    def get_group_name(self, group_id: str) -> str | None:
        """Get a group name from the listener's cached thread list."""
        thread_data = getattr(self.listener, "fbt", None)

        if not isinstance(thread_data, dict):
            return None

        all_threads = thread_data.get("dataAllThread", {})

        if not isinstance(all_threads, dict):
            return None

        thread_ids = all_threads.get("threadIDList", [])
        thread_names = all_threads.get("threadNameList", [])

        for thread_id, thread_name in zip(thread_ids, thread_names):
            if str(thread_id) == str(group_id) and thread_name:
                return str(thread_name)

        return None

    async def connect(self):
        self.loop = asyncio.get_running_loop()

        self.listener.configure_group_events(
            self.session.get("FacebookID", ""),
            self.loop,
            self.group_event_queue,
        )

        await self.listener.connect_mqtt()

    async def receive(self, timeout=1):
        return await self.listener.get_message(timeout=timeout)

    async def disconnect(self):
        await self.listener.disconnect()
