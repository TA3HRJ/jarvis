"""Katman 4: bulut LLM (Claude). Sadece Katman 1-3 bir niyete karar veremediğinde
çağrılır — muhakeme, kod yazma, çok adımlı görevler için."""

import anthropic
from anthropic import beta_tool

from . import memory
from .sandbox import run_sandboxed

MODEL = "claude-opus-5"

SYSTEM_PROMPT = (
    "Sen Jarvis'sin, Erhan'ın Linux masaüstünde çalışan sesli asistanısın. "
    "Türkçe konuş. Kısa ve net cevaplar ver, sesli okunacak şekilde yaz "
    "(markdown biçimlendirme, kod bloğu gibi sesli okunamayacak şeyler kullanma). "
    "Kod çalıştırman gerekirse run_sandboxed_command aracını kullan — izole, "
    "ağsız bir sandbox'ta çalışır. Kalıcı olarak hatırlanması gereken bir şey "
    "öğrendiğinde remember aracıyla kaydet, geçmiş bağlam gerektiğinde recall ile ara."
)


@beta_tool
def run_sandboxed_command(command: str) -> str:
    """İzole bir sandbox'ta (ağ erişimi yok, salt-okunur kök dosya sistemi) bir shell komutu çalıştırır.

    Args:
        command: Çalıştırılacak shell komutu.
    """
    result = run_sandboxed(command)
    if result["timed_out"]:
        return "HATA: komut zaman aşımına uğradı."
    return f"çıkış kodu: {result['return_code']}\nstdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"


@beta_tool
def remember(text: str) -> str:
    """Kullanıcı hakkında veya bağlam hakkında kalıcı olarak hatırlanması gereken bir bilgiyi kaydeder.

    Args:
        text: Hatırlanacak bilgi, tam cümle halinde.
    """
    memory.remember(text)
    return "kaydedildi"


@beta_tool
def recall(query: str) -> str:
    """Geçmişte kaydedilmiş, sorguyla semantik olarak ilgili bilgileri getirir.

    Args:
        query: Ne hakkında bilgi aranıyor.
    """
    results = memory.recall(query, k=5)
    if not results:
        return "ilgili bir hafıza bulunamadı"
    return "\n".join(f"- {r['text']}" for r in results)


def ask(user_message: str, model: str = MODEL, effort: str = "medium") -> str:
    """Kullanıcının isteğini bulut LLM'e (Katman 4) yönlendirir, araç döngüsünü çalıştırır."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        tools=[run_sandboxed_command, remember, recall],
        messages=[{"role": "user", "content": user_message}],
    )
    last_text = ""
    for message in runner:
        for block in message.content:
            if block.type == "text":
                last_text = block.text
    return last_text
