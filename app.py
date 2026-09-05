"""Punto de entrada modular de Agente QA.

La funcionalidad e interfaz aprobadas se distribuyen por la estructura objetivo.
``app_legacy.py`` se conserva como fuente transitoria de funciones que aún no
han sido migradas; su interfaz no se ejecuta desde este archivo.

Reglas:
- Solo se modifica ``organizar-main``.
- ``main`` es fuente funcional/visual y nunca se modifica.
- ``mao-dev-branch`` es referencia estructural y nunca se modifica.
"""
from __future__ import annotations

import ast
from pathlib import Path

import streamlit as st

from agente_qa.ui.document import render_document_section
from agente_qa.ui.generation_section import render_generation_section
from agente_qa.ui.results import render_results_section
from agente_qa.ui.azure_section import render_azure_publish, render_azure_sidebar
from agente_qa.ui.state import init_session_state
from agente_qa.ui.coverage import coverage_gate_or_stop
from agente_qa.ui.editor import render_azure_style_editor, delete_test_case
from agente_qa.export.excel import create_excel
from agente_qa.export.pdf import create_pdf
from agente_qa.extraction import extract_source
from agente_qa.generation import generate_qa_data, load_prompt, validate_qa_structure
from agente_qa.providers.gemini import get_valid_models
from agente_qa.utils import (
    _remove_trailing_pipe, _ui_text, aggregate_case_alerts, build_azure_description,
    build_case_title, find_coverage, format_description_for_azure, module_token,
    normalize_case_id, normalize_coverage, normalize_validation_method, safe_steps, safe_text,
)
from agente_qa.validation import (
    _extract_related_cu, _normalize_cu, calculate_cu_coverage,
    render_cu_coverage, validate_minimum_cu_coverage,
)


def _load_legacy_functions():
    """Carga imports, constantes y funciones de app_legacy sin ejecutar su UI."""
    legacy_path = Path(__file__).with_name("app_legacy.py")
    source = legacy_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(legacy_path))

    # La interfaz histórica comienza en el primer st.set_page_config().
    # Todo lo anterior contiene dependencias, configuración y funciones que
    # todavía sirven como puente durante la migración modular.
    interface_index = None
    for index, node in enumerate(tree.body):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "st"
            and call.func.attr == "set_page_config"
        ):
            interface_index = index
            break

    if interface_index is None:
        raise RuntimeError("No se encontró st.set_page_config() en app_legacy.py")

    tree.body = tree.body[:interface_index]
    ast.fix_missing_locations(tree)
    namespace = {
        "__name__": "agente_qa_legacy_functions",
        "__file__": str(legacy_path),
        "__package__": None,
    }
    exec(compile(tree, str(legacy_path), "exec"), namespace, namespace)
    return namespace


LEGACY = _load_legacy_functions()

AzureDevOpsError = LEGACY["AzureDevOpsError"]
test_connection = LEGACY["test_connection"]
list_test_plans = LEGACY["list_test_plans"]
list_test_suites = LEGACY["list_test_suites"]
list_test_cases = LEGACY["list_test_cases"]
get_test_case_detail = LEGACY["get_test_case_detail"]
create_selected_cases_in_azure = LEGACY["create_selected_cases_in_azure"]

APP_VERSION = LEGACY["APP_VERSION"]
FALLBACK_MODELS = LEGACY["FALLBACK_MODELS"]
EXCEL_CONFIGS = LEGACY["EXCEL_CONFIGS"]

st.set_page_config(
    page_title=f"Agente QA {APP_VERSION}",
    layout="wide",
)

init_session_state()

st.title(f"🤖 Agente QA {APP_VERSION} — Generador de Casos de Prueba")
st.caption(
    "VERSION PREVIA — DRAFT | PDF / DOCX / TXT / MD → análisis QA → Excel + PDF"
)

sidebar_config = render_azure_sidebar(
    fallback_models=FALLBACK_MODELS,
    excel_configs=EXCEL_CONFIGS,
    test_connection=test_connection,
    azure_error_type=AzureDevOpsError,
    list_test_plans=list_test_plans,
    list_test_suites=list_test_suites,
    list_test_cases=list_test_cases,
    get_test_case_detail=get_test_case_detail,
    delete_test_case=delete_test_case,
    calculate_cu_coverage=calculate_cu_coverage,
    create_excel=create_excel,
    create_pdf=create_pdf,
    result=st.session_state.get("result_json"),
    source_name=st.session_state.get("source_name", ""),
)

source_text = render_document_section(extract_source)

render_generation_section(
    generate_qa_data=generate_qa_data,
    load_prompt=load_prompt,
    source_text=source_text,
    api_key=sidebar_config["api_key"],
    selected_model=sidebar_config["selected_model"],
    max_retries=sidebar_config["max_retries"],
    wait_time=sidebar_config["wait_time"],
    coverage_gate_or_stop=lambda data: coverage_gate_or_stop(
        calculate_cu_coverage, render_cu_coverage, data
    ),
    create_excel=create_excel,
    create_pdf=create_pdf,
    selected_config=sidebar_config["selected_config"],
)

render_results_section(
    result=st.session_state.get("result_json"),
    selected_config=sidebar_config["selected_config"],
    excel_configs=EXCEL_CONFIGS,
    calculate_cu_coverage=calculate_cu_coverage,
    render_cu_coverage=render_cu_coverage,
    render_editor=render_azure_style_editor,
    delete_test_case=delete_test_case,
    create_excel=create_excel,
    create_pdf=create_pdf,
    coverage_gate_or_stop=lambda data: coverage_gate_or_stop(
        calculate_cu_coverage, render_cu_coverage, data
    ),
)

result = st.session_state.get("result_json")
if result:
    render_azure_publish(
        result=result,
        selected_config=sidebar_config["selected_config"],
        list_test_suites=list_test_suites,
        list_test_cases=list_test_cases,
        create_selected_cases_in_azure=create_selected_cases_in_azure,
    )
