"""Bir metin komutunu Katman 1-3 yönlendiricisine sokar, eşleşmezse Katman 4'e (bulut LLM)
düşer. Hem yerel sesli döngü (main.py) hem uzaktan API (api.py) bunu paylaşır."""

from . import actions
from .brain import ask
from .logsetup import get_logger
from .router import route

logger = get_logger("jarvis.dispatch")


def handle_command(text: str, source: str = "local") -> str:
    """source: "local" (mikrofon) veya "remote" (Faz 6 API) — denetim logu için."""
    result = route(text, use_layer3=True)
    if result.intent:
        response = actions.execute(result.intent, result.slots)
        logger.info(
            "kaynak=%s metin=%r niyet=%s slotlar=%s katman=%s -> %r",
            source, text, result.intent, result.slots, result.layer, response,
        )
        return response
    response = ask(text)
    logger.info("kaynak=%s metin=%r niyet=yok (katman4/bulut) -> %r", source, text, response)
    return response
