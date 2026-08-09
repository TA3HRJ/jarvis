"""Ana orkestratör (tek süreç): mikrofon -> wake word -> VAD -> STT -> yönlendirici -> TTS.
CLAUDE.md bağlayıcı kural #2: mikroservis sprawl yok, tek süreç."""

import os
import re
import subprocess
import tempfile
import threading
import wave

import numpy as np
import torch

from .dispatch import handle_command
from .logsetup import get_logger
from .tts import speak

logger = get_logger("jarvis.main")

API_HOST = "100.100.59.67"
API_PORT = 8765

SOURCE = "jarvis_echo_cancel_source"
SAMPLE_RATE = 16000
WAKE_FRAME_SAMPLES = 1280  # openWakeWord: 80ms katları
VAD_FRAME_SAMPLES = 512  # Silero VAD
WAKE_THRESHOLD = 0.6  # arka plan gürültüsünde yanlış tetiklenmeyi azaltmak için 0.5'ten yükseltildi
VAD_THRESHOLD = 0.5
MAX_UTTERANCE_SECONDS = 8  # gürültüde VAD yanlışlıkla "hâlâ konuşuyor" diyebiliyor, en kötü senaryoyu kısalt
SILENCE_END_SECONDS = 0.7
MIN_UTTERANCE_SECONDS = 0.3
POST_WAKE_DISCARD_SECONDS = 0.7  # "Hey Jarvis"in kuyruğu komuta karışmasın diye kısa bir atlama
WAKE_MODEL_NAME = "hey_jarvis_v0.1"

# 0.4sn atlama bazen yetmiyor, Whisper "Hey Jarvis"i de transkribe edip komuta ekliyor
# (örn. "H.A.R.V.I.S Sesi Kıs", "Hey Jarvis, bilgisayarın sesini kıs") — metinden de temizle.
_WAKE_PREFIX_RE = re.compile(
    r"^\s*(hey[,.]?\s*)?(jarvis|charles|travis|yarvis|harvis|h\.?a\.?r\.?v\.?i\.?s\.?)[,.]?\s*",
    re.IGNORECASE,
)


def _strip_wake_prefix(text: str) -> str:
    stripped = _WAKE_PREFIX_RE.sub("", text, count=1).strip()
    return stripped if stripped else text

_whisper_model = None


def _find_wake_model_path() -> str:
    import openwakeword

    return os.path.join(
        os.path.dirname(openwakeword.__file__), "resources", "models", "hey_jarvis_v0.1.onnx"
    )


def _set_ctranslate2_cuda_libpath() -> None:
    """faster-whisper'ın arka ucu (ctranslate2) CUDA 12 ABI istiyor, sistem CUDA'sı 13 —
    proje bağımlılığı olarak eklenen nvidia-cublas-cu12/cudnn-cu12'nin yolunu göster.
    nvidia.cublas.lib bir namespace package, __file__'ı yok — sysconfig üzerinden bul."""
    import sysconfig

    site_packages = sysconfig.get_path("purelib")
    paths = [
        os.path.join(site_packages, "nvidia", "cublas", "lib"),
        os.path.join(site_packages, "nvidia", "cudnn", "lib"),
    ]
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = ":".join(paths + ([existing] if existing else []))


def _open_audio_stream() -> subprocess.Popen:
    return subprocess.Popen(
        [
            "pw-record", "--raw", "--target", SOURCE,
            "--channels", "1", "--rate", str(SAMPLE_RATE), "--format", "s16", "-",
        ],
        stdout=subprocess.PIPE,
    )


def _read_frame(proc: subprocess.Popen, n_samples: int) -> np.ndarray | None:
    data = proc.stdout.read(n_samples * 2)
    if len(data) < n_samples * 2:
        return None
    return np.frombuffer(data, dtype=np.int16)


def _capture_utterance(proc: subprocess.Popen, vad_model) -> np.ndarray:
    chunks = []
    silence_frames = 0
    silence_limit = int(SILENCE_END_SECONDS * SAMPLE_RATE / VAD_FRAME_SAMPLES)
    max_frames = int(MAX_UTTERANCE_SECONDS * SAMPLE_RATE / VAD_FRAME_SAMPLES)
    speech_started = False
    discard_frames = int(POST_WAKE_DISCARD_SECONDS * SAMPLE_RATE / VAD_FRAME_SAMPLES)
    for _ in range(discard_frames):
        if _read_frame(proc, VAD_FRAME_SAMPLES) is None:
            break

    for _ in range(max_frames):
        frame = _read_frame(proc, VAD_FRAME_SAMPLES)
        if frame is None:
            break
        chunks.append(frame)
        audio_f = torch.from_numpy(frame.astype(np.float32) / 32768.0)
        prob = vad_model(audio_f, SAMPLE_RATE).item()
        if prob > VAD_THRESHOLD:
            speech_started = True
            silence_frames = 0
        elif speech_started:
            silence_frames += 1
            if silence_frames >= silence_limit:
                break
    return np.concatenate(chunks) if chunks else np.array([], dtype=np.int16)


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _set_ctranslate2_cuda_libpath()
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel("medium", device="cuda", compute_type="int8")
    return _whisper_model


NO_SPEECH_THRESHOLD = 0.6  # bu üstündeki segmentler gürültü/sessizlik sayılır, atılır


def _transcribe(audio: np.ndarray) -> str:
    model = _get_whisper_model()
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        with wave.open(f.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(audio.tobytes())
        segments, _ = model.transcribe(f.name, language="tr")
        kept = [s for s in segments if s.no_speech_prob < NO_SPEECH_THRESHOLD]
        return " ".join(s.text.strip() for s in kept).strip()


def _run_api_server() -> None:
    """Uzaktan dispatch API'sini (Faz 6) aynı süreç içinde, arka plan thread'inde çalıştırır —
    ayrı bir süreç olarak çalıştırmak router/brain modellerini iki kere yükletiyordu (CUDA OOM'a
    yol açtı) — CLAUDE.md kural #2: tek süreç orkestratör."""
    import uvicorn

    from .api import app

    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="warning")


def run() -> None:
    from openwakeword.model import Model as WakeModel
    from silero_vad import load_silero_vad

    threading.Thread(target=_run_api_server, daemon=True).start()

    wake_model = WakeModel(wakeword_model_paths=[_find_wake_model_path()])
    vad_model = load_silero_vad()
    proc = _open_audio_stream()

    logger.info('Jarvis dinliyor... ("hey jarvis" bekleniyor)')
    try:
        while True:
            frame = _read_frame(proc, WAKE_FRAME_SAMPLES)
            if frame is None:
                logger.warning("mikrofon akışı kesildi (pw-record EOF), döngü sonlanıyor")
                break
            prediction = wake_model.predict(frame)
            score = prediction.get(WAKE_MODEL_NAME, 0.0)
            if os.environ.get("JARVIS_DEBUG_WAKE") and score > 0.02:
                logger.debug("wake skoru: %.3f", score)
            if score > WAKE_THRESHOLD:
                logger.info("wake word algılandı (skor=%.3f), dinleniyor...", score)
                utterance = _capture_utterance(proc, vad_model)
                if len(utterance) < SAMPLE_RATE * MIN_UTTERANCE_SECONDS:
                    logger.info("çok kısa/boş konuşma, atlanıyor")
                    continue
                text = _strip_wake_prefix(_transcribe(utterance))
                logger.info("duyulan: %r", text)
                if text:
                    response = handle_command(text, source="local")
                    speak(response, barge_in=False)
    finally:
        proc.terminate()


if __name__ == "__main__":
    run()
