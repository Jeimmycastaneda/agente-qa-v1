"""Compatibilidad para el antiguo punto de importación del editor.

La implementación real vive ahora en ``agente_qa.ui.editor``.
"""
from agente_qa.ui.editor import delete_test_case, render_azure_style_editor

__all__ = ["render_azure_style_editor", "delete_test_case"]
