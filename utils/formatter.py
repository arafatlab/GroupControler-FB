from datetime import datetime, timezone


def format_message(message):
    timestamp = message.get("timestamp")

    try:
        timestamp = int(timestamp)
        if timestamp > 10**12:
            timestamp //= 1000

        time_text = datetime.fromtimestamp(
            timestamp / 1000 if timestamp > 10**10 else timestamp,
            tz=timezone.utc,
        ).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    except (TypeError, ValueError, OSError, OverflowError):
        time_text = "Unknown"

    body = message.get("body")

    return (
        "\n"
        "==========================================\n"
        "             MESSENGER EVENT\n"
        "==========================================\n"
        f"Sender ID : {message.get('userID')}\n"
        f"Thread ID : {message.get('replyToID')}\n"
        f"Type      : {message.get('type')}\n"
        f"Time      : {time_text}\n"
        f"Message   : {body if body is not None else '[Non-text event]'}\n"
        "=========================================="
    )
