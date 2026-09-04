"""Punto de entrada de Agente QA.

Migración gradual: la UI histórica se conserva en app_legacy.py, mientras las
funciones migradas se resuelven desde los módulos de agente_qa/.

IMPORTANTE:
- Este archivo solo se modifica en organizar-main.
- app_legacy.py se conserva como respaldo durante la migración.
- mao-dev no aporta lógica funcional; solo se respeta su estructura objetivo.
"""

from __future__ import annotations

import ast
from pathlib import Path

from agente_qa.extraction import (
    extract_csv,
    extract_docx,
    extract_pdf,
    extract_source,
    extract_txt,
    extract_xlsx,
)
from agente_qa.generation import (
    generate_qa_data,
    load_prompt,
    validate_qa_structure,
)
from agente_qa.providers.gemini import get_valid_models
from agente_qa.export.excel import create_excel
from agente_qa.export.pdf import create_pdf
from agente_qa.utils import (
    _remove_trailing_pipe,
    _ui_text,
    aggregate_case_alerts,
    build_azure_description,
    build_case_title,
    find_coverage,
    format_description_for_azure,
    module_token,
    normalize_case_id,
    normalize_coverage,
    normalize_validation_method,
    safe_steps,
    safe_text,
)
from agente_qa.validation import (
    _extract_related_cu,
    _normalize_cu,
    calculate_cu_coverage,
    render_cu_coverage,
    validate_minimum_cu_coverage,
)


# Funciones ya centralizadas que no deben volver a ejecutarse desde
# app_legacy.py. La lista permite continuar la migración por etapas.
_MIGRATED_FUNCTIONS = {
    "_ui_text", "safe_text", "safe_steps", "normalize_coverage",
    "normalize_validation_method", "_remove_trailing_pipe",
    "build_azure_description", "format_description_for_azure", "module_token",
    "build_case_title", "normalize_case_id", "find_coverage",
    "aggregate_case_alerts", "_normalize_cu", "_extract_related_cu",
    "calculate_cu_coverage", "validate_minimum_cu_coverage", "render_cu_coverage",
    "extract_txt", "extract_pdf", "extract_docx", "extract_xlsx", "extract_csv",
    "extract_source", "load_prompt", "get_valid_models", "validate_qa_structure",
    "generate_qa_data", "create_excel", "create_pdf",
}


def _load_legacy_without_migrated_functions() -> None:
    """Ejecuta la UI histórica excluyendo funciones ya centralizadas."""
    legacy_path = Path(__file__).with_name("app_legacy.py")
    source = legacy_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(legacy_path))

    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in _MIGRATED_FUNCTIONS
        )
    ]

    code = compile(tree, str(legacy_path), "exec")
    namespace = {
        "__name__": "__main__",
        "__file__": str(legacy_path),
        "__package__": None,
        **{name: globals()[name] for name in _MIGRATED_FUNCTIONS},
    }
    exec(code, namespace, namespace)


_load_legacy_without_migrated_functions()
