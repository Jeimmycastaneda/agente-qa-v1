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

from agente_qa.extraction import extract_csv, extract_docx, extract_pdf, extract_source, extract_txt, extract_xlsx
from agente_qa.generation import generate_qa_data, load_prompt, validate_qa_structure
from agente_qa.providers.gemini import get_valid_models
from agente_qa.export.excel import create_excel
from agente_qa.export.pdf import create_pdf
from agente_qa.ui.azure_section import render_azure_publish, render_azure_sidebar
from agente_qa.ui.coverage import coverage_gate_or_stop
from agente_qa.ui.generation import render_generation
from agente_qa.ui.upload import render_upload
from agente_qa.utils import (
    _remove_trailing_pipe, _ui_text, aggregate_case_alerts, build_azure_description,
    build_case_title, find_coverage, format_description_for_azure, module_token,
    normalize_case_id, normalize_coverage, normalize_validation_method, safe_steps, safe_text,
)
from agente_qa.validation import _extract_related_cu, _normalize_cu, calculate_cu_coverage, render_cu_coverage, validate_minimum_cu_coverage

_MIGRATED_FUNCTIONS = {
    "_ui_text", "safe_text", "safe_steps", "normalize_coverage", "normalize_validation_method",
    "_remove_trailing_pipe", "build_azure_description", "format_description_for_azure", "module_token",
    "build_case_title", "normalize_case_id", "find_coverage", "aggregate_case_alerts", "_normalize_cu",
    "_extract_related_cu", "calculate_cu_coverage", "validate_minimum_cu_coverage", "render_cu_coverage",
    "extract_txt", "extract_pdf", "extract_docx", "extract_xlsx", "extract_csv", "extract_source",
    "load_prompt", "get_valid_models", "validate_qa_structure", "generate_qa_data", "create_excel", "create_pdf",
}


def _render_modular_core_ui(api_key, selected_model, max_retries, wait_time, selected_config):
    source_text = render_upload(extract_source)
    result = render_generation(
        generate_qa_data=generate_qa_data,
        load_prompt=load_prompt,
        source_text=source_text,
        api_key=api_key,
        selected_model=selected_model,
        max_retries=max_retries,
        wait_time=wait_time,
        coverage_gate_or_stop=lambda data: coverage_gate_or_stop(calculate_cu_coverage, render_cu_coverage, data),
    )
    if result is not None:
        st.session_state.result_json = result
        st.session_state.azure_reference_preview = None
        st.session_state.azure_preview_edit_mode = False
        st.session_state.excel_data = create_excel(result, selected_config)
        st.session_state.pdf_data = create_pdf(result, selected_config, st.session_state.get("source_name", ""))
    return st.session_state.get("result_json")


def _build_core_call():
    return ast.parse("result = _render_modular_core_ui(api_key, selected_model, max_retries, wait_time, selected_config)").body[0]


def _build_sidebar_call():
    return ast.parse(
        "_sidebar_cfg = _render_modular_sidebar("
        "fallback_models=FALLBACK_MODELS, excel_configs=EXCEL_CONFIGS, "
        "test_connection=test_connection, azure_error_type=AzureDevOpsError, "
        "list_test_plans=list_test_plans, list_test_suites=list_test_suites, "
        "list_test_cases=list_test_cases, get_test_case_detail=get_test_case_detail, "
        "delete_test_case=delete_test_case, calculate_cu_coverage=calculate_cu_coverage, "
        "create_excel=create_excel, create_pdf=create_pdf, "
        "result=st.session_state.get('result_json'), source_name=st.session_state.get('source_name', '')"
        ")\n"
        "api_key = _sidebar_cfg['api_key']\n"
        "selected_model = _sidebar_cfg['selected_model']\n"
        "selected_config = _sidebar_cfg['selected_config']\n"
        "max_retries = _sidebar_cfg['max_retries']\n"
        "wait_time = _sidebar_cfg['wait_time']"
    ).body


def _build_publish_call():
    return ast.parse(
        "render_azure_publish("
        "result=result, selected_config=selected_config, "
        "list_test_suites=list_test_suites, list_test_cases=list_test_cases, "
        "create_selected_cases_in_azure=create_selected_cases_in_azure)"
    ).body[0]


def _load_legacy_without_migrated_functions() -> None:
    legacy_path = Path(__file__).with_name("app_legacy.py")
    source = legacy_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(legacy_path))
    lines = source.splitlines()

    upload_marker = 'st.subheader("📁 Carga de Documento")'
    result_marker = 'result = st.session_state.result_json'
    publish_marker = '# CARGA CONTROLADA EN AZURE — DOS PASOS'
    excel_marker = 'current_excel_data = create_excel(result, selected_config)'

    upload_start = next((i + 1 for i, line in enumerate(lines) if upload_marker in line), None)
    result_anchor = next((i + 1 for i, line in enumerate(lines) if result_marker in line), None)
    publish_start = next((i + 1 for i, line in enumerate(lines) if publish_marker in line), None)
    excel_anchor = next((i + 1 for i, line in enumerate(lines) if excel_marker in line), None)

    filtered_body = []
    core_inserted = False
    sidebar_inserted = False
    publish_inserted = False

    for node in tree.body:
        # La barra lateral completa se sustituye por ui/azure_section.py.
        is_sidebar = isinstance(node, ast.With) and any(
            isinstance(item.context_expr, ast.Attribute)
            and item.context_expr.attr == "sidebar"
            for item in node.items
        )
        if is_sidebar:
            if not sidebar_inserted:
                filtered_body.extend(_build_sidebar_call())
                sidebar_inserted = True
            continue

        # Carga + generación ya están en componentes modulares.
        if upload_start and result_anchor and node.lineno >= upload_start and node.end_lineno < result_anchor:
            if not core_inserted:
                filtered_body.append(_build_core_call())
                core_inserted = True
            continue

        # Flujo completo de publicación Azure ya está en ui/azure_section.py.
        if publish_start and excel_anchor and node.lineno >= publish_start and node.end_lineno < excel_anchor:
            if not publish_inserted:
                filtered_body.append(_build_publish_call())
                publish_inserted = True
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _MIGRATED_FUNCTIONS:
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
        "_render_modular_sidebar": render_azure_sidebar,
        "render_azure_publish": render_azure_publish,
        **{name: globals()[name] for name in _MIGRATED_FUNCTIONS},
    }
    exec(code, namespace, namespace)


_load_legacy_without_migrated_functions()
