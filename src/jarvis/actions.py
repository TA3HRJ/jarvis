"""Katman 1-3'ün eşleştirdiği niyetleri gerçek sistem eylemlerine bağlar.
Elde olmayan bir eylem için sahte bir "yapıldı" cevabı vermek yerine dürüstçe
henüz uygulanmadığını söyler."""

import datetime
import subprocess


def _saat_kac(slots: dict) -> str:
    now = datetime.datetime.now()
    return f"Saat {now.hour}:{now.minute:02d}."


def _ekrani_kilitle(slots: dict) -> str:
    subprocess.run(["loginctl", "lock-session"], check=False)
    return "Ekranı kilitledim."


def _sesi_kis(slots: dict) -> str:
    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "10%-"], check=False)
    return "Sesi kıstım."


def _sesi_ac(slots: dict) -> str:
    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "10%+"], check=False)
    return "Sesi açtım."


def _ses_ayarla(slots: dict) -> str:
    seviye = slots.get("seviye")
    if not seviye:
        return "Kaça ayarlayacağımı anlayamadım."
    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{seviye}%"], check=False)
    return f"Sesi yüzde {seviye}'e ayarladım."


def _henuz_yok(slots: dict) -> str:
    return "Bu özelliği henüz uygulamadım."


HANDLERS = {
    "saat_kac": _saat_kac,
    "ekrani_kilitle": _ekrani_kilitle,
    "sesi_kis": _sesi_kis,
    "sesi_ac": _sesi_ac,
    "ses_ayarla": _ses_ayarla,
    "hava_durumu": _henuz_yok,
    "alarm_kur": _henuz_yok,
}


def execute(intent: str, slots: dict) -> str:
    handler = HANDLERS.get(intent, _henuz_yok)
    return handler(slots)
