"""Punto de entrada de Agente QA.

Migración gradual: la UI histórica se conserva en app_legacy.py, pero las
funciones de Utils y Validación se resuelven desde agente_qa/ durante la
runtime. Esto permite retirar duplicados sin alterar la lógica de negocio.

IMPORTANTE:
- Este archivo solo trabaja con organizar-main.
- app_legacy.py se conserva como fuente de respaldo durante la migración.
- mao-dev no aporta lógica.
"""

from __future__ import annotations

import ast
from pathlib import Path

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


# Estas son las funciones que ya tienen módulo propio y no deben volver a
# definirse dentro de la aplicación histórica.
_MIGRATED_FUNCTIONS = {
    "_ui_text",
    "safe_text",
    "safe_steps",
    "normalize_coverage",
    "normalize_validation_method",
    "_remove_trailing_pipe",
    "build_azure_description",
    "format_description_for_azure",
    "module_token",
    "build_case_title",
    "normalize_case_id",
    "find_coverage",
    "aggregate_case_alerts",
    "_normalize_cu",
    "_extract_related_cu",
    "calculate_cu_coverage",
    "validate_minimum_cu_coverage",
    "render_cu_coverage",
}


def _load_legacy_without_migrated_functions() -> None:
    """Ejecuta la UI histórica excluyendo Utils y Validación duplicadas.

    Se usa AST para eliminar únicamente las definiciones de funciones ya
    centralizadas. El resto de app_legacy.py permanece intacto y sigue siendo
    el comportamiento funcional de la aplicación durante esta fase.
    """
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
        # Inyectamos explícitamente las implementaciones centralizadas.
        **{name: globals()[name] for name in _MIGRATED_FUNCTIONS},
    }
    exec(code, namespace, namespace)


_load_legacy_without_migrated_functions()
