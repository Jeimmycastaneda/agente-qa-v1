"""Punto de extensión para la sección Azure DevOps de la UI.

La lógica actual de Azure permanece en la orquestación histórica durante la
migración. Este módulo define la frontera de UI sin introducir escrituras
nuevas ni cambiar el comportamiento existente.
"""
from __future__ import annotations


def azure_ui_available():
    """Indica que la frontera modular de UI Azure está disponible."""
    return True
