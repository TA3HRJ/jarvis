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


def _check_token(authorization: str | None, token_param: str | None) -> None:
    """Authorization header VEYA ?token= sorgu parametresi kabul edilir — iOS Shortcuts'ta
    header ayarlamak zahmetli olduğu için query param olarak da izin veriliyor. Güvenlik
    sınırı zaten Tailscale mesh'i (bu uç genel internete açık değil)."""
    expected = os.environ.get(TOKEN_ENV)
    if not expected:
        raise HTTPException(500, "JARVIS_API_TOKEN ayarlanmamış")
    got = token_param or (authorization[7:] if authorization and authorization.startswith("Bearer ") else None)
    if got != expected:
        raise HTTPException(401, "geçersiz token")


def _handle(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "text gerekli")

    result = route(text, use_layer3=True)
    if result.intent:
        response = f"Niyet: {result.intent}, slotlar: {result.slots} (katman {result.layer})"
    else:
        response = ask(text)

    notify(response)
    return {"response": response}


@app.get("/command")
def command_get(
    text: str = "",
    token: str | None = None,
    authorization: str | None = Header(default=None),
) -> dict:
    """iOS Shortcuts için en basit yol: tek bir GET isteği, başlık/gövde ayarı gerekmez.
    Örnek: /command?text=saat+kaç&token=..."""
    _check_token(authorization, token)
    return _handle(text)


@app.post("/command")
def command_post(
    body: dict,
    token: str | None = None,
    authorization: str | None = Header(default=None),
) -> dict:
    _check_token(authorization, token)
    return _handle(body.get("text", ""))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
