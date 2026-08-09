"""Ortak log yapılandırması. journald zaten kalıcı/aranabilir tutuyor (systemd servisi
olarak çalışıyoruz) — burada sadece seviye + zaman damgası + modül adı ekliyoruz."""

import logging
import os

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=os.environ.get("JARVIS_LOG_LEVEL", "INFO"),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
        _configured = True
    return logging.getLogger(name)
