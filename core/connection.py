import asyncio

from fbchat_v2 import listeningEvent

from config import MESSAGE_QUEUE_SIZE


class MessengerConnection:
    def __init__(self, session):
        self.session = session
        self.listener = listeningEvent(
            session,
            message_queue_maxsize=MESSAGE_QUEUE_SIZE,
        )

    @property
    def state(self):
        return self.listener.connection_state

    @property
    def status(self):
        return self.listener.connection_status

    async def connect(self):
        await self.listener.connect_mqtt()

    async def receive(self, timeout=1):
        return await self.listener.get_message(timeout=timeout)

    async def disconnect(self):
        await self.listener.disconnect()
