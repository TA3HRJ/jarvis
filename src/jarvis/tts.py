"""Piper tabanlı akışlı TTS. Konuşmayı kesme (barge-in) kararı burada verilmez — çağıran
bir `interrupt` Event'i verir, set edilince playback kesilir (bkz. main.py: TTS sırasında
wake word dinleme)."""

import re
import subprocess
import threading

from piper import PiperVoice

_MARKDOWN_RE = re.compile(r"[*_`#]+")


def _strip_markdown(text: str) -> str:
    """LLM'e markdown kullanma dense de bazen kullanıyor — Piper '**'i 'yıldız yıldız'
    diye okur, sesli çıktıya gitmeden temizle (defense in depth)."""
    return re.sub(r"\s{2,}", " ", _MARKDOWN_RE.sub("", text)).strip()

MODEL_PATH = "models/piper/tr_TR-dfki-medium.onnx"
SINK = "jarvis_echo_cancel_sink"
INTERRUPT_POLL_SECONDS = 0.05

_voice: PiperVoice | None = None


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(MODEL_PATH)
    return _voice


def speak(text: str, interrupt: threading.Event | None = None) -> bool:
    """Metni akış halinde sentezleyip çalar. `interrupt` set edilirse playback'i hemen keser.
    Tamamlandıysa True, kesildiyse False döner."""
    voice = _get_voice()
    chunks = voice.synthesize(_strip_markdown(text))
    try:
        first = next(chunks)
    except StopIteration:
        return True

    proc = subprocess.Popen(
        [
            "pw-cat", "--raw", "--playback", "--target", SINK,
            "--format", "s16", "--rate", str(first.sample_rate),
            "--channels", str(first.sample_channels), "-",
        ],
        stdin=subprocess.PIPE,
    )

    done = threading.Event()
    watcher = None
    if interrupt is not None:
        # Yazma döngüsü Piper'ın sonraki cümleyi sentezlemesini beklerken bloke olabilir —
        # kesme anında sesi durdurmak için playback'i ayrı bir thread'den sonlandır.
        def _watch() -> None:
            while not done.is_set():
                if interrupt.wait(INTERRUPT_POLL_SECONDS):
                    proc.terminate()
                    return

        watcher = threading.Thread(target=_watch, daemon=True)
        watcher.start()

    try:
        proc.stdin.write(first.audio_int16_bytes)
        for chunk in chunks:
            if interrupt is not None and interrupt.is_set():
                break
            proc.stdin.write(chunk.audio_int16_bytes)
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait()
        done.set()

    if watcher is not None:
        watcher.join(timeout=1)

    return not (interrupt is not None and interrupt.is_set())
