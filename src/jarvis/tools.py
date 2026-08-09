"""Katman 4 (bulut LLM) araçlarının sağlayıcıdan bağımsız uygulamaları."""

from . import memory
from .sandbox import run_sandboxed


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


TOOL_DESCRIPTIONS = {
    "run_sandboxed_command": "İzole bir sandbox'ta (ağ erişimi yok, salt-okunur kök dosya sistemi) bir shell komutu çalıştırır.",
    "remember": "Kullanıcı hakkında veya bağlam hakkında kalıcı olarak hatırlanması gereken bir bilgiyi kaydeder.",
    "recall": "Geçmişte kaydedilmiş, sorguyla semantik olarak ilgili bilgileri getirir.",
}

TOOL_PARAM_NAMES = {
    "run_sandboxed_command": ("command", "Çalıştırılacak shell komutu."),
    "remember": ("text", "Hatırlanacak bilgi, tam cümle halinde."),
    "recall": ("query", "Ne hakkında bilgi aranıyor."),
}

TOOL_IMPLS = {
    "run_sandboxed_command": run_sandboxed_command_impl,
    "remember": remember_impl,
    "recall": recall_impl,
}

SYSTEM_PROMPT = (
    "Sen Jarvis'sin, Erhan'ın Linux masaüstünde çalışan sesli asistanısın. "
    "Türkçe konuş. Kısa ve net cevaplar ver, sesli okunacak şekilde yaz "
    "(markdown biçimlendirme, kod bloğu gibi sesli okunamayacak şeyler kullanma). "
    "Kod çalıştırman gerekirse run_sandboxed_command aracını kullan — izole, "
    "ağsız bir sandbox'ta çalışır. Kalıcı olarak hatırlanması gereken bir şey "
    "öğrendiğinde remember aracıyla kaydet, geçmiş bağlam gerektiğinde recall ile ara."
)
