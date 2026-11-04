import httpx

from config import GROQ_API_KEY, GROQ_MODEL
from modules.role import SYSTEM_PROMPT


class AIEngine:

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self):

        self.api_key = GROQ_API_KEY
        self.model = GROQ_MODEL

        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing in config.py"
            )

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    async def generate_reply(self, user_text, history=None):

        if not isinstance(user_text, str):
            return None

        user_text = user_text.strip()

        if not user_text:
            return None

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        # Load previous conversation history
        if isinstance(history, list):

            for item in history[-20:]:

                if not isinstance(item, dict):
                    continue

                role = item.get("role")
                content = item.get("content")

                if role not in ("user", "assistant"):
                    continue

                if not isinstance(content, str):
                    continue

                content = content.strip()

                if not content:
                    continue

                messages.append({
                    "role": role,
                    "content": content
                })

        # Current user message
        messages.append({
            "role": "user",
            "content": user_text
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.8,
        }

        try:

            response = await self.client.post(
                self.API_URL,
                json=payload
            )

            if response.status_code != 200:

                try:
                    error_data = response.json()
                    error_message = error_data.get(
                        "error", {}
                    ).get(
                        "message",
                        "Unknown API error"
                    )

                except (ValueError, AttributeError):
                    error_message = response.text[:300]

                raise RuntimeError(
                    f"Groq API HTTP {response.status_code}: "
                    f"{error_message}"
                )

            data = response.json()

            choices = data.get("choices", [])

            if not choices:
                raise RuntimeError(
                    "Groq returned no choices."
                )

            reply = (
                choices[0]
                .get("message", {})
                .get("content")
            )

            if not isinstance(reply, str) or not reply.strip():
                raise RuntimeError(
                    "Groq returned an empty response."
                )

            return reply.strip()

        except httpx.TimeoutException as error:

            raise RuntimeError(
                "Groq API request timed out."
            ) from error

        except httpx.RequestError as error:

            raise RuntimeError(
                f"Network error: {type(error).__name__}"
            ) from error

    async def close(self):

        await self.client.aclose()
