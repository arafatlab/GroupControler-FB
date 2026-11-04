import asyncio

from core.connection import MessengerConnection
from modules.messages import AIMessageHandler
from utils.formatter import format_message


class Messenger:

    def __init__(self, session):
        self.connection = MessengerConnection(session)
        self.ai_handler = AIMessageHandler(session)
        self._running = False
        self._closed = False

    async def start(self):
        self._running = True

        print("[+] Messenger listener initialized.")
        print(f"[AI] DRY RUN: {self.ai_handler.dry_run}")

        connection_task = asyncio.create_task(
            self.connection.connect()
        )

        previous_state = None

        try:
            while self._running and not connection_task.done():

                state = self.connection.state

                if state != previous_state:
                    print(f"[CONNECTION] {state}")
                    previous_state = state

                message = await self.connection.receive(timeout=1)

                if message is not None:
                    print(format_message(message))
                    await self.ai_handler.handle(message)

            await connection_task

        finally:
            self._running = False

            if not connection_task.done():
                connection_task.cancel()

                await asyncio.gather(
                    connection_task,
                    return_exceptions=True
                )

            await self.connection.disconnect()

    async def stop(self):
        self._running = False

        await self.connection.disconnect()

        if not self._closed:
            await self.ai_handler.close()
            self._closed = True
