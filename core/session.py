import json

from config import COOKIE_FILE
from fbchat_v2 import dataGetHome


def load_cookies() -> str:
    if not COOKIE_FILE.exists():
        raise FileNotFoundError("cookies.json not found")

    with COOKIE_FILE.open("r", encoding="utf-8") as file:
        cookies = json.load(file)

    if not isinstance(cookies, list):
        raise ValueError("Invalid cookies.json format")

    cookie_string = "; ".join(
        f"{item['name']}={item['value']}"
        for item in cookies
        if isinstance(item, dict)
        and item.get("name")
        and item.get("value") is not None
    )

    if not cookie_string:
        raise ValueError("No valid cookies found")

    return cookie_string


async def create_session():
    cookies = load_cookies()
    return await dataGetHome(setCookies=cookies)
