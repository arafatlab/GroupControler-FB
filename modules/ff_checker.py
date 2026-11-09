
import asyncio
import json
import re
from datetime import datetime, timezone

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
                method, endpoint, **kwargs
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

        last_error = "Profile data unavailable"

        for attempt in range(1, 4):
            try:
                csrf = await self.get_csrf_token()
                session_token = await self.create_checker_session(uid, csrf)

                headers = {
                    "Content-Type": "application/json",
                    "x-api-client": "gameskinbo-web",
                    "x-csrf-token": csrf,
                    "x-ff-id-checker-token": session_token,
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                }

                data = await self._request_json(
                    "POST",
                    "/api/ff_id_checker",
                    headers=headers,
                    json={"uid": uid},
                )

                raw_data = data.get("raw_data")
                parsed = None

                if isinstance(raw_data, dict):
                    parsed = raw_data
                elif isinstance(raw_data, str):
                    try:
                        parsed = json.loads(raw_data)
                    except json.JSONDecodeError:
                        parsed = None

                data["raw_data_parsed"] = parsed

                account = (
                    parsed.get("AccountInfo", {})
                    if isinstance(parsed, dict)
                    else {}
                )

                social = (
                    parsed.get("SocialInfo", {})
                    if isinstance(parsed, dict)
                    else {}
                )

                profile_ready = (
                    isinstance(account, dict)
                    and bool(account.get("AccountName"))
                    and bool(social.get("accountId"))
                )

                print(
                    f"[FF CHECK] Attempt {attempt}/3 | "
                    f"Profile ready: {profile_ready}"
                )

                if profile_ready:
                    return data

                last_error = data.get(
                    "message",
                    "API returned incomplete profile data"
                )

            except GamesKinboError as error:
                last_error = str(error)
                print(
                    f"[FF CHECK] Attempt {attempt}/3 failed: "
                    f"{last_error}"
                )

            if attempt < 3:
                await asyncio.sleep(2)

        raise GamesKinboError(
            f"Could not retrieve complete profile after 3 attempts: "
            f"{last_error}"
        )

    async def close(self):
        await self.client.aclose()


def _normalize(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _all_dicts(obj):
    """Return all nested dictionaries."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _all_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _all_dicts(value)


def _find(player, *keys):
    """Search top-level and nested API data."""
    wanted = {_normalize(key) for key in keys}

    for obj in _all_dicts(player):
        for key, value in obj.items():
            if _normalize(key) in wanted:
                if value is not None and value != "":
                    return value

    return None


def _display(value):
    if value is None or value == "":
        return "N/A"

    if isinstance(value, (dict, list)):
        return "N/A"

    return str(value)


def _date(value):
    if value is None or value == "":
        return "N/A"

    try:
        if isinstance(value, str):
            if not value.isdigit():
                return value
            value = int(value)

        value = float(value)

        # Unix timestamp
        if value > 100000000000:
            value /= 1000

        return datetime.fromtimestamp(
            value, timezone.utc
        ).strftime("%d %b %Y")

    except (ValueError, TypeError, OverflowError, OSError):
        return str(value)


def _number(value):
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _percentage(numerator, denominator):
    a = _number(numerator)
    b = _number(denominator)

    if a is None or b is None or b <= 0:
        return None

    return f"{(a / b) * 100:.2f}%"


def format_player(player):
    from datetime import datetime, timezone

    raw = player.get("raw_data_parsed") or {}

    account = raw.get("AccountInfo") or {}
    profile = raw.get("AccountProfileInfo") or {}
    social = raw.get("SocialInfo") or {}
    guild = raw.get("GuildInfo") or {}
    leader = raw.get("GuildOwnerInfo") or {}

    def value(data, key):
        result = data.get(key)
        return result if result not in (None, "") else "N/A"

    def format_date(timestamp):
        if not timestamp:
            return "N/A"
        try:
            return datetime.fromtimestamp(
                int(timestamp), timezone.utc
            ).strftime("%d %B %Y")
        except (ValueError, TypeError, OSError):
            return "N/A"

    lines = [
        "🔥 FREE FIRE PLAYER PROFILE",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 Name: {value(account, 'AccountName')}",
        f"🆔 UID: {value(social, 'accountId')}",
        f"⭐ Level: {value(account, 'AccountLevel')}",
        f"🌍 Region: {value(account, 'AccountRegion')}",
        f"❤️ Likes: {value(account, 'AccountLikes')}",
        "",
        "🏆 RANK INFORMATION",
        f"📊 BR Points: {value(profile, 'BrRankPoint')}",
        "",
        "📊 PLAYER STATISTICS",
        "💀 KD Ratio: N/A (Statistics unavailable)",
        "🎯 Headshot Rate: N/A (Statistics unavailable)",
        "",
        "🏰 GUILD INFORMATION",
        f"🏷️ Guild: {value(guild, 'GuildName')}",
        f"👑 Guild Leader: {value(leader, 'nickname')}",
        f"🆔 Guild ID: {value(guild, 'GuildID')}",
        "",
        "📅 Account Created: "
        + format_date(account.get("AccountCreateTime")),
        f"📝 Bio: {value(social, 'signature')}",
        "━━━━━━━━━━━━━━━━━━",
    ]

    return "\n".join(lines)
