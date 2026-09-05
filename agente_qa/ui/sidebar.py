"""Barra lateral: conserva la configuración y las consultas Azure de la interfaz aprobada."""
from __future__ import annotations

from agente_qa.ui.azure_section import render_azure_sidebar


def render_sidebar(**kwargs):
    return render_azure_sidebar(**kwargs)
