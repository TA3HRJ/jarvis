"""Katman 4 (bulut LLM) araçlarının sağlayıcıdan bağımsız uygulamaları."""

import httpx

from . import memory
from .sandbox import run_sandboxed

WMO_CODES = {
    0: "açık", 1: "genelde açık", 2: "parçalı bulutlu", 3: "kapalı",
    45: "sisli", 48: "kırağı sisi",
    51: "hafif çisenti", 53: "çisenti", 55: "yoğun çisenti",
    61: "hafif yağmurlu", 63: "yağmurlu", 65: "şiddetli yağmurlu",
    71: "hafif kar yağışlı", 73: "kar yağışlı", 75: "yoğun kar yağışlı",
    80: "sağanak yağışlı", 81: "kuvvetli sağanak", 82: "şiddetli sağanak",
    95: "gök gürültülü fırtına", 96: "dolulu fırtına", 99: "şiddetli dolulu fırtına",
}


def run_sandboxed_command_impl(command: str) -> str:
    result = run_sandboxed(command)
    if result["timed_out"]:
        return "HATA: komut zaman aşımına uğradı."
    return f"çıkış kodu: {result['return_code']}\nstdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"


def remember_impl(text: str) -> str:
    memory.remember(text)
    return "kaydedildi"


def recall_impl(query: str) -> str:
    results = memory.recall(query, k=5)
    if not results:
        return "ilgili bir hafıza bulunamadı"
    return "\n".join(f"- {r['text']}" for r in results)


def get_weather_impl(city: str) -> str:
    city = (city or "").strip() or "İzmir"
    try:
        geo = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "tr"},
            timeout=10,
        ).json()
        results = geo.get("results")
        if not results:
            return f"{city} için bir konum bulamadım."
        loc = results[0]
        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=10,
        ).json()
        current = weather["current"]
        desc = WMO_CODES.get(current["weather_code"], "bilinmeyen hava durumu")
        return f"{loc['name']}'de şu an {current['temperature_2m']:.0f} derece, {desc}."
    except httpx.HTTPError:
        return "Hava durumu servisine ulaşamadım, internet bağlantısı olmayabilir."
    except (KeyError, IndexError):
        return "Hava durumu verisini işleyemedim."


TOOL_DESCRIPTIONS = {
    "run_sandboxed_command": "İzole bir sandbox'ta (ağ erişimi yok, salt-okunur kök dosya sistemi) bir shell komutu çalıştırır.",
    "remember": "Kullanıcı hakkında veya bağlam hakkında kalıcı olarak hatırlanması gereken bir bilgiyi kaydeder.",
    "recall": "Geçmişte kaydedilmiş, sorguyla semantik olarak ilgili bilgileri getirir.",
    "get_weather": "Bir şehrin güncel hava durumunu (sıcaklık, hava kodu) getirir.",
}

TOOL_PARAM_NAMES = {
    "run_sandboxed_command": ("command", "Çalıştırılacak shell komutu."),
    "remember": ("text", "Hatırlanacak bilgi, tam cümle halinde."),
    "recall": ("query", "Ne hakkında bilgi aranıyor."),
    "get_weather": ("city", "Hava durumu sorulan şehrin adı, örn. İzmir."),
}

TOOL_IMPLS = {
    "run_sandboxed_command": run_sandboxed_command_impl,
    "remember": remember_impl,
    "recall": recall_impl,
    "get_weather": get_weather_impl,
}

SYSTEM_PROMPT = (
    "Sen Jarvis'sin, Erhan'ın Linux masaüstünde çalışan sesli asistanısın. "
    "Türkçe konuş. Kısa ve net cevaplar ver, sesli okunacak şekilde yaz "
    "(markdown biçimlendirme, kod bloğu gibi sesli okunamayacak şeyler kullanma). "
    "Kod çalıştırman gerekirse run_sandboxed_command aracını kullan — izole, "
    "ağsız bir sandbox'ta çalışır. Kalıcı olarak hatırlanması gereken bir şey "
    "öğrendiğinde remember aracıyla kaydet, geçmiş bağlam gerektiğinde recall ile ara. "
    "Hava durumu sorulursa get_weather aracını kullan, şehir belirtilmezse İzmir varsay."
)
