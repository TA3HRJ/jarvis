"""Katman 3: küçük yerel model (3B Q4). SADECE niyet sınıflandırma + slot çıkarımı yapar, beyin değil —
çıktısı JSON şemasıyla kısıtlanır, serbest metin üretemez."""

import json
import threading

from .catalog import CATALOG

IDLE_UNLOAD_SECONDS = 60

MODEL_PATH = "models/llm/qwen2.5-3b-instruct-q4_k_m.gguf"

INTENT_NAMES = [i.name for i in CATALOG] + ["belirsiz"]

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENT_NAMES},
        "slots": {"type": "object"},
    },
    "required": ["intent", "slots"],
}

SYSTEM_PROMPT = (
    "Sen bir niyet sınıflandırıcısın, asistan değilsin. Kullanıcının Türkçe cümlesini "
    "aşağıdaki niyet kataloğundan birine ata ve varsa slot değerlerini çıkar. "
    'Hiçbiri uymuyorsa intent alanını "belirsiz" yap. Sadece JSON döndür, başka hiçbir şey yazma.\n\n'
    "Niyet kataloğu:\n"
    + "\n".join(
        f"- {i.name} (örnekler: {', '.join(i.example_phrases)}) slotlar: {i.slots or 'yok'}"
        for i in CATALOG
    )
)

_llm = None
_grammar = None
_unload_timer = None


def _get_llm():
    global _llm
    if _llm is None:
        from llama_cpp import Llama

        _llm = Llama(model_path=MODEL_PATH, n_gpu_layers=-1, n_ctx=2048, verbose=False)
    return _llm


def _get_grammar():
    global _grammar
    if _grammar is None:
        from llama_cpp import LlamaGrammar

        _grammar = LlamaGrammar.from_json_schema(json.dumps(JSON_SCHEMA))
    return _grammar


def _unload_llm() -> None:
    """Idle unload (CLAUDE.md bağlayıcı kural #5): Whisper zaten GPU'da yüklüyse Katman 3'ün
    3B modeliyle aynı anda kalmak 6GB VRAM'i aşabiliyor (canlı testte OOM'a yol açtı) —
    ama HER kullanımdan hemen sonra boşaltmak "her seferinde yeniden yükle"ye dönüşüp
    route()'u 11+ saniyeye çıkardı (canlı testte ölçüldü). Doğrusu: gerçekten BOŞTA
    kalınca (IDLE_UNLOAD_SECONDS) boşalt, ardışık hızlı kullanımlarda sıcak tut."""
    global _llm
    if _llm is not None:
        del _llm
        _llm = None
        import gc

        gc.collect()


def _schedule_idle_unload() -> None:
    global _unload_timer
    if _unload_timer is not None:
        _unload_timer.cancel()
    _unload_timer = threading.Timer(IDLE_UNLOAD_SECONDS, _unload_llm)
    _unload_timer.daemon = True
    _unload_timer.start()


def layer3_match(text: str):
    from .router import RouteResult

    llm = _get_llm()
    grammar = _get_grammar()
    try:
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            grammar=grammar,
            temperature=0,
        )
    finally:
        _schedule_idle_unload()

    content = out["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    intent = parsed.get("intent")
    if intent == "belirsiz" or intent not in INTENT_NAMES:
        return None
    return RouteResult(intent=intent, slots=parsed.get("slots", {}), layer=3, confidence=0.5)
