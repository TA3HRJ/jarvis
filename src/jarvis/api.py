"""Faz 6: uzaktan dispatch. Tailscale mesh üzerinden erişilecek (internete açık uç YOK),
token ile korunan tek endpoint — komutu Katman 1-3 yönlendiricisine sokar, eşleşmezse
Katman 4'e (bulut LLM) düşer. Yanıt hem HTTP cevabı hem ntfy push bildirimi olarak döner."""

import os

from fastapi import FastAPI, Header, HTTPException

from .brain import ask
from .notify import notify
from .router import route

app = FastAPI()

TOKEN_ENV = "JARVIS_API_TOKEN"


def _check_token(authorization: str | None) -> None:
    expected = os.environ.get(TOKEN_ENV)
    if not expected:
        raise HTTPException(500, "JARVIS_API_TOKEN ayarlanmamış")
    if authorization != f"Bearer {expected}":
        raise HTTPException(401, "geçersiz token")


@app.post("/command")
def command(body: dict, authorization: str | None = Header(default=None)) -> dict:
    _check_token(authorization)
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text gerekli")

    result = route(text, use_layer3=True)
    if result.intent:
        response = f"Niyet: {result.intent}, slotlar: {result.slots} (katman {result.layer})"
    else:
        response = ask(text)

    notify(response)
    return {"response": response}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
