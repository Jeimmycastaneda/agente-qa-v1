"""Resolución de secretos sin almacenarlos en el código fuente."""
from __future__ import annotations
import os
import streamlit as st


def resolve_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, "")).strip()
