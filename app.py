"""Punto de entrada de Agente QA.

Migración gradual: la UI histórica se conserva en app_legacy.py, mientras los
componentes funcionales y de UI ya migrados se resuelven desde agente_qa/.

IMPORTANTE:
- Este archivo solo se modifica en organizar-main.
- app_legacy.py se conserva como respaldo durante la migración.
- mao-dev no aporta lógica funcional; solo se respeta su estructura objetivo.
"""

from __future__ import annotations

import ast
from pathlib import Path

import streamlit as st

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
from agente_qa.ui.coverage import coverage_gate_or_stop
from agente_qa.ui.generation import render_generation
from agente_qa.ui.upload import render_upload
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


def _render_modular_core_ui(api_key, selected_model, max_retries, wait_time, selected_config):
    """Ejecuta la UI ya migrada de carga + generación sin duplicarla en legacy."""
    source_text = render_upload(extract_source)
    result = render_generation(
        generate_qa_data=generate_qa_data,
        load_prompt=load_prompt,
        source_text=source_text,
        api_key=api_key,
        selected_model=selected_model,
        max_retries=max_retries,
        wait_time=wait_time,
        coverage_gate_or_stop=lambda data: coverage_gate_or_stop(
            calculate_cu_coverage,
            render_cu_coverage,
            data,
        ),
    )

    if result is not None:
        st.session_state.result_json = result
        st.session_state.azure_reference_preview = None
        st.session_state.azure_preview_edit_mode = False
        st.session_state.excel_data = create_excel(result, selected_config)
        st.session_state.pdf_data = create_pdf(
            result,
            selected_config,
            st.session_state.get("source_name", ""),
        )

    return st.session_state.get("result_json")


def _build_modular_ui_call():
    """Construye el nodo AST que reemplaza carga/generación históricas."""
    tree = ast.parse(
        "result = _render_modular_core_ui("
        "api_key, selected_model, max_retries, wait_time, selected_config"
        ")"
    )
    return tree.body[0]


def _load_legacy_without_migrated_functions() -> None:
    """Ejecuta la UI histórica excluyendo funciones y bloques ya migrados."""
    legacy_path = Path(__file__).with_name("app_legacy.py")
    source = legacy_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(legacy_path))

    # Además de quitar funciones migradas, sustituimos el bloque histórico de
    # carga + generación por los componentes ui/upload.py y ui/generation.py.
    lines = source.splitlines()
    upload_marker = 'st.subheader("📁 Carga de Documento")'
    result_marker = 'result = st.session_state.result_json'

    upload_start = next(
        (idx + 1 for idx, line in enumerate(lines) if upload_marker in line),
        None,
    )
    result_anchor = next(
        (idx + 1 for idx, line in enumerate(lines) if result_marker in line),
        None,
    )

    replacement_inserted = False
    filtered_body = []
    for node in tree.body:
        if (
            upload_start is not None
            and result_anchor is not None
            and node.lineno >= upload_start
            and node.end_lineno < result_anchor
        ):
            if not replacement_inserted:
                filtered_body.append(_build_modular_ui_call())
                replacement_inserted = True
            continue

        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in _MIGRATED_FUNCTIONS
        ):
            continue

        filtered_body.append(node)

    tree.body = filtered_body
    ast.fix_missing_locations(tree)

    code = compile(tree, str(legacy_path), "exec")
    namespace = {
        "__name__": "__main__",
        "__file__": str(legacy_path),
        "__package__": None,
        "_render_modular_core_ui": _render_modular_core_ui,
        **{name: globals()[name] for name in _MIGRATED_FUNCTIONS},
    }
    exec(code, namespace, namespace)


_load_legacy_without_migrated_functions()
