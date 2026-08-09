"""ntfy.sh üzerinden telefona push bildirimi gönderir."""

import os

import httpx

NTFY_TOPIC_ENV = "JARVIS_NTFY_TOPIC"
NTFY_URL = "https://ntfy.sh"


def notify(message: str, title: str = "Jarvis") -> bool:
    topic = os.environ.get(NTFY_TOPIC_ENV)
    if not topic:
        return False
    try:
        httpx.post(
            f"{NTFY_URL}/{topic}",
            content=message.encode("utf-8"),
            headers={"Title": title},
            timeout=10,
        )
        return True
    except httpx.HTTPError:
        return False
