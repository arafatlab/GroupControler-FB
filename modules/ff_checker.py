import json
import re

import httpx


class GamesKinboError(Exception):
    pass


class GamesKinbo:

    BASE_URL = "https://gameskinbo.com"

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=50,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Origin": self.BASE_URL,
                "Referer": self.BASE_URL + "/free_fire_id_checker",
            },
        )

    async def _request_json(self, method, endpoint, **kwargs):
        try:
            response = await self.client.request(
                method,
                endpoint,
                **kwargs
            )
        except httpx.RequestError as error:
            raise GamesKinboError(
                f"Network error: {type(error).__name__}"
            ) from error

        try:
            data = response.json()
        except ValueError:
            raise GamesKinboError(
                f"Invalid server response (HTTP {response.status_code})"
            )

        if not response.is_success:
            message = (
                data.get("error", "Request failed")
                if isinstance(data, dict)
                else "Request failed"
            )
            raise GamesKinboError(
                f"HTTP {response.status_code}: {message}"
            )

        if not isinstance(data, dict):
            raise GamesKinboError("Unexpected API response format")

        return data

    async def get_csrf_token(self):

        data = await self._request_json(
            "GET",
            "/api/csrf-token",
            headers={"Cache-Control": "no-cache"},
        )

        if not data.get("success") or not data.get("csrfToken"):
            raise GamesKinboError("Could not obtain CSRF token")

        return data["csrfToken"]

    async def create_checker_session(self, uid, csrf):

        headers = {
            "Content-Type": "application/json",
            "x-api-client": "gameskinbo-web",
            "x-csrf-token": csrf,
        }

        data = await self._request_json(
            "POST",
            "/api/ff_id_checker/session",
            headers=headers,
            json={"uid": uid},
        )

        token = data.get("token")

        if not token:
            raise GamesKinboError(
                "Checker session token was not returned"
            )

        return token

    async def check_player(self, uid):

        uid = str(uid).strip()

        if not re.fullmatch(r"\d+", uid):
            raise ValueError("UID must contain numbers only")

        csrf = await self.get_csrf_token()

        session_token = await self.create_checker_session(
            uid,
            csrf,
        )

        headers = {
            "Content-Type": "application/json",
            "x-api-client": "gameskinbo-web",
            "x-csrf-token": csrf,
            "x-ff-id-checker-token": session_token,
        }

        data = await self._request_json(
            "POST",
            "/api/ff_id_checker",
            headers=headers,
            json={"uid": uid},
        )

        raw_data = data.get("raw_data")

        if isinstance(raw_data, str):
            try:
                data["raw_data_parsed"] = json.loads(raw_data)
            except json.JSONDecodeError:
                data["raw_data_parsed"] = None

        return data

    async def close(self):
        await self.client.aclose()


def format_player(player):

    fields = [
        ("UID", "uid"),
        ("Name", "name"),
        ("Level", "level"),
        ("Region", "region"),
        ("Likes", "likes"),
        ("Prime Level", "prime_level"),
        ("Guild", "guild_name"),
        ("Guild ID", "guild_id"),
        ("Guild Leader", "guild_leader_name"),
        ("Pet Level", "pet_level"),
        ("Credit Score", "credit_score"),
    ]

    lines = ["🔥 FREE FIRE PLAYER PROFILE", ""]

    for label, key in fields:
        value = player.get(key)

        if value is not None and value != "":
            lines.append(f"{label}: {value}")

    return "\n".join(lines)
