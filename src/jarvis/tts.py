"""Piper tabanlı akışlı TTS + konuşma sırasında sözünü kesebilme (barge-in)."""

import re
import subprocess
import threading

import numpy as np
import torch
from piper import PiperVoice
from silero_vad import load_silero_vad

_MARKDOWN_RE = re.compile(r"[*_`#]+")


def _strip_markdown(text: str) -> str:
    """LLM'e markdown kullanma dense de bazen kullanıyor — Piper '**'i 'yıldız yıldız'
    diye okur, sesli çıktıya gitmeden temizle (defense in depth)."""
    return re.sub(r"\s{2,}", " ", _MARKDOWN_RE.sub("", text)).strip()

MODEL_PATH = "models/piper/tr_TR-dfki-medium.onnx"
SINK = "jarvis_echo_cancel_sink"
SOURCE = "jarvis_echo_cancel_source"
VAD_SAMPLE_RATE = 16000
VAD_FRAME_SAMPLES = 512
BARGE_IN_THRESHOLD = 0.6
# AEC (yankı bastırma) playback başlar başlamaz henüz yakınsamamış olabiliyor — o kısa
# pencerede Jarvis'in kendi sesi mikrofona sızıp barge-in'i yanlışlıkla tetikliyordu
# (canlı testte: hiç konuşamadan hep kesiliyordu). İlk bu kadar saniyeyi göz ardı et.
BARGE_IN_GRACE_SECONDS = 0.6

_voice: PiperVoice | None = None
_vad_model = None


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(MODEL_PATH)
    return _voice


def _get_vad_model():
    global _vad_model
    if _vad_model is None:
        _vad_model = load_silero_vad()
    return _vad_model


def _watch_for_speech(interrupted: threading.Event, playback: subprocess.Popen) -> None:
    model = _get_vad_model()
    frame_bytes = VAD_FRAME_SAMPLES * 2
    rec = subprocess.Popen(
        [
            "pw-record", "--raw", "--target", SOURCE,
            "--channels", "1", "--rate", str(VAD_SAMPLE_RATE), "--format", "s16", "-",
        ],
        stdout=subprocess.PIPE,
    )
    grace_frames = int(BARGE_IN_GRACE_SECONDS * VAD_SAMPLE_RATE / VAD_FRAME_SAMPLES)
    frame_count = 0
    try:
        while playback.poll() is None:
            data = rec.stdout.read(frame_bytes)
            if len(data) < frame_bytes:
                break
            frame_count += 1
            audio = torch.from_numpy(np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0)
            prob = model(audio, VAD_SAMPLE_RATE).item()
            if frame_count <= grace_frames:
                continue
            if prob > BARGE_IN_THRESHOLD:
                interrupted.set()
                playback.terminate()
                break
    finally:
        rec.terminate()
        rec.wait()


def speak(text: str, barge_in: bool = True) -> bool:
    """Metni akış halinde sentezleyip çalar. Konuşma sırasında mikrofonda ses
    algılanırsa (barge_in=True) playback'i keser. Tamamlandıysa True, kesildiyse False döner."""
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

    interrupted = threading.Event()
    watcher = None
    if barge_in:
        watcher = threading.Thread(target=_watch_for_speech, args=(interrupted, proc), daemon=True)
        watcher.start()

    try:
        proc.stdin.write(first.audio_int16_bytes)
        for chunk in chunks:
            if interrupted.is_set():
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

    if watcher is not None:
        interrupted.set()  # izleyici thread'in çıkması için (VAD hiç tetiklenmediyse)
        watcher.join(timeout=1)

    return not interrupted.is_set()
