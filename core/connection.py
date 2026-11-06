import asyncio
from typing import Any

from fbchat_v2 import listeningEvent
from config import MESSAGE_QUEUE_SIZE


class GroupAwareListener(listeningEvent):
    """Detect when the bot account joins or leaves a Facebook group."""

    def configure_group_events(self, bot_id, loop, event_queue):
        self.bot_id = str(bot_id)
        self.event_loop = loop
        self.group_event_queue = event_queue

    def _body_from_delta(self, delta: Any):
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

        if event_class == "ParticipantsAddedToGroupThread":
            participants = delta.get("addedParticipants")
            if not isinstance(participants, list):
                return None

            bot_affected = bool(self.bot_id) and any(
                isinstance(item, dict)
                and str(item.get("userFbId", "")) == self.bot_id
                for item in participants
            )
            event_type = "added"

        else:
            bot_affected = bool(self.bot_id) and (
                str(delta.get("leftParticipantFbId", "")) == self.bot_id
            )
            event_type = "removed"

        if bot_affected and group_id and self.event_loop.is_running():
            event = {
                "type": event_type,
                "group_id": str(group_id),
                "actor_id": str(actor_id) if actor_id is not None else "unknown",
            }
            self.event_loop.call_soon_threadsafe(
                self.group_event_queue.put_nowait, event
            )

        # Membership events are not ordinary chat messages.
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
