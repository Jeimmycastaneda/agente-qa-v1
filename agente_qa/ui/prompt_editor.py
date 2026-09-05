"""Punto de extensión para edición de prompt.

La interfaz aprobada actual no muestra un editor de prompt; por eso esta pieza
se mantiene disponible por arquitectura, pero no se renderiza en app.py.
"""
from __future__ import annotations
import streamlit as st


def render_prompt_section(load_prompt=None):
    return load_prompt() if load_prompt else ""
