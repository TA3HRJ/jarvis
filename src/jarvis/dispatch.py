"""Bir metin komutunu Katman 1-3 yönlendiricisine sokar, eşleşmezse Katman 4'e (bulut LLM)
düşer. Hem yerel sesli döngü (main.py) hem uzaktan API (api.py) bunu paylaşır."""

from . import actions
from .brain import ask
from .router import route


def handle_command(text: str) -> str:
    result = route(text, use_layer3=True)
    if result.intent:
        return actions.execute(result.intent, result.slots)
    return ask(text)
