"""Punto de entrada modular de Agente QA.

La funcionalidad e interfaz aprobadas se distribuyen por la estructura objetivo.

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
from agente_qa.ui.editor import render_azure_style_editor
from agente_qa.export.excel import create_excel
from agente_qa.export.pdf import create_pdf
from agente_qa.extraction import extract_source
from agente_qa.generation import generate_qa_data, load_prompt
from agente_qa.validation import calculate_cu_coverage, render_cu_coverage
from agente_qa.integrations.azure_runtime import (
    AzureDevOpsError,
    create_selected_cases_in_azure,
    get_test_case_detail,
    list_test_cases,
    list_test_plans,
    list_test_suites,
    test_connection,
)
from agente_qa.integrations.cotizador_browser import CotizadorBrowserError, inspect_cotizador
from config.qa_config import EXCEL_CONFIGS

FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

st.set_page_config(page_title=f"Agente QA {APP_VERSION}", layout="wide")
init_session_state()

st.title(f"🤖 Agente QA {APP_VERSION} — Generador de Casos de Prueba")
st.caption("VERSION PREVIA — DRAFT | PDF / DOCX / TXT / MD → análisis QA → Excel + PDF")

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
        delete_test_case=None,
        calculate_cu_coverage=calculate_cu_coverage,
        create_excel=create_excel,
        create_pdf=create_pdf,
        result=None,
        source_name=st.session_state.get("source_name", ""),
    )

    st.divider()
    st.subheader("🌐 Conectar cotizador web")
    st.caption("Permite iniciar sesión y obtener evidencia de las pantallas, botones y enlaces visibles para construir pasos. Las credenciales se usan solo durante la sesión y no se guardan en disco.")
    cotizador_url = st.text_input("🔗 URL del cotizador", key="cotizador_url", placeholder="https://...")
    cotizador_user = st.text_input("👤 Usuario", key="cotizador_user")
    cotizador_password = st.text_input("🔑 Contraseña", type="password", key="cotizador_password")
    cotizador_login_selector = st.text_input("Selector del botón de ingreso (opcional)", key="cotizador_login_selector", placeholder="button[type='submit']")
    if st.button("🔎 Conectar y analizar navegación", key="cotizador_inspect"):
        try:
            with st.spinner("Iniciando sesión y analizando navegación visible..."):
                inspection = inspect_cotizador(cotizador_url, cotizador_user, cotizador_password, cotizador_login_selector)
            st.session_state.cotizador_source_text = inspection.source_text
            st.session_state.cotizador_pages = inspection.pages
            st.success(f"✅ Cotizador conectado. Se identificaron {len(inspection.pages)} página(s).")
        except CotizadorBrowserError as exc:
            st.error(f"❌ {exc}")
        except Exception as exc:
            st.error(f"❌ Error inesperado al conectar el cotizador: {exc}")
    if st.session_state.get("cotizador_pages"):
        st.caption("Páginas analizadas:")
        for page_url in st.session_state.cotizador_pages:
            st.code(page_url)

source_text = render_document_section(extract_source)

# La evidencia del cotizador se agrega como contexto técnico de navegación.
# Gemini debe seguir usando la HU como fuente funcional y no inventar reglas.
cotizador_source = st.session_state.get("cotizador_source_text", "")
if cotizador_source:
    source_text = f"{source_text}\n\n{cotizador_source}".strip()

render_generation_section(
    generate_qa_data=generate_qa_data,
    load_prompt=load_prompt,
    source_text=source_text,
    api_key=sidebar_config["api_key"],
    selected_model=sidebar_config["selected_model"],
    max_retries=sidebar_config["max_retries"],
    wait_time=sidebar_config["wait_time"],
    coverage_gate_or_stop=lambda data: coverage_gate_or_stop(calculate_cu_coverage, render_cu_coverage, data),
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
    create_excel=create_excel,
    create_pdf=create_pdf,
    coverage_gate_or_stop=lambda data: coverage_gate_or_stop(calculate_cu_coverage, render_cu_coverage, data),
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
