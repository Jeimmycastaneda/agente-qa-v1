"""Punto de entrada modular de Agente QA.

La funcionalidad e interfaz aprobadas se distribuyen por la estructura objetivo.
``app_legacy.py`` se conserva temporalmente como respaldo, pero ya no es
necesario para ejecutar la aplicación.

Reglas:
- Solo se modifica ``organizar-main``.
- ``main`` es fuente funcional/visual y nunca se modifica.
- ``mao-dev-branch`` es referencia estructural y nunca se modifica.
"""
from __future__ import annotations

import streamlit as st

from agente_qa.config import APP_VERSION
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
from agente_qa.integrations.azure_runtime import (
    AzureDevOpsError,
    create_selected_cases_in_azure,
    get_test_case_detail,
    list_test_cases,
    list_test_plans,
    list_test_suites,
    test_connection,
)
from config.qa_config import EXCEL_CONFIGS


FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

st.set_page_config(
    page_title=f"Agente QA {APP_VERSION}",
    layout="wide",
)

init_session_state()

st.title(f"🤖 Agente QA {APP_VERSION} — Generador de Casos de Prueba")
st.caption(
    "VERSION PREVIA — DRAFT | PDF / DOCX / TXT / MD → análisis QA → Excel + PDF"
)

# IMPORTANTE: en main toda esta sección vive dentro de st.sidebar.
# El módulo conserva el contenido aprobado, pero app.py debe mantener su
# ubicación visual en la barra lateral.
with st.sidebar:
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
