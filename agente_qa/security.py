"""Utilidades de seguridad para mensajes técnicos y trazas."""
from __future__ import annotations
import re


def redact(value):
    text = str(value or "")
    return re.sub(r"(?i)(api[_ -]?key|pat|token|authorization)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
