"""Katman 4: bulut LLM. Sadece Katman 1-3 bir niyete karar veremediğinde çağrılır —
muhakeme, kod yazma, çok adımlı görevler için.

Sağlayıcı `JARVIS_LLM_PROVIDER` ortam değişkeniyle seçilir ("deepseek" | "claude",
varsayılan "deepseek"). DeepSeek kredisi bitince tek satır değişiklikle Claude'a
geçilebilir — TTS motoru gibi bir soyutlama arkasında."""

import json
import os

from .tools import SYSTEM_PROMPT, TOOL_DESCRIPTIONS, TOOL_IMPLS, TOOL_PARAM_NAMES

DEEPSEEK_MODEL = "deepseek-v4-pro"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
CLAUDE_MODEL = "claude-opus-5"


def _ask_deepseek(user_message: str, model: str = DEEPSEEK_MODEL) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=DEEPSEEK_BASE_URL)

    tools = []
    for name, (param, param_desc) in TOOL_PARAM_NAMES.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": TOOL_DESCRIPTIONS[name],
                "parameters": {
                    "type": "object",
                    "properties": {param: {"type": "string", "description": param_desc}},
                    "required": [param],
                },
            },
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for _ in range(10):
        response = client.chat.completions.create(model=model, messages=messages, tools=tools)
        msg = response.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""

        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            arg_value = next(iter(args.values())) if args else ""
            result = TOOL_IMPLS[call.function.name](arg_value)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    return "çok adımlı araç kullanımı tamamlanamadı (limit aşıldı)"


def _ask_claude(user_message: str, model: str = CLAUDE_MODEL, effort: str = "medium") -> str:
    import anthropic
    from anthropic import beta_tool

    @beta_tool
    def run_sandboxed_command(command: str) -> str:
        """İzole bir sandbox'ta (ağ erişimi yok, salt-okunur kök dosya sistemi) bir shell komutu çalıştırır.

        Args:
            command: Çalıştırılacak shell komutu.
        """
        return TOOL_IMPLS["run_sandboxed_command"](command)

    @beta_tool
    def remember(text: str) -> str:
        """Kullanıcı hakkında veya bağlam hakkında kalıcı olarak hatırlanması gereken bir bilgiyi kaydeder.

        Args:
            text: Hatırlanacak bilgi, tam cümle halinde.
        """
        return TOOL_IMPLS["remember"](text)

    @beta_tool
    def recall(query: str) -> str:
        """Geçmişte kaydedilmiş, sorguyla semantik olarak ilgili bilgileri getirir.

        Args:
            query: Ne hakkında bilgi aranıyor.
        """
        return TOOL_IMPLS["recall"](query)

    @beta_tool
    def get_weather(city: str) -> str:
        """Bir şehrin güncel hava durumunu (sıcaklık, hava kodu) getirir.

        Args:
            city: Hava durumu sorulan şehrin adı, örn. İzmir.
        """
        return TOOL_IMPLS["get_weather"](city)

    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        tools=[run_sandboxed_command, remember, recall, get_weather],
        messages=[{"role": "user", "content": user_message}],
    )
    last_text = ""
    for message in runner:
        for block in message.content:
            if block.type == "text":
                last_text = block.text
    return last_text


def ask(user_message: str, provider: str | None = None) -> str:
    provider = provider or os.environ.get("JARVIS_LLM_PROVIDER", "deepseek")
    if provider == "deepseek":
        return _ask_deepseek(user_message)
    elif provider == "claude":
        return _ask_claude(user_message)
    raise ValueError(f"bilinmeyen sağlayıcı: {provider}")
