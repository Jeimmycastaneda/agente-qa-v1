"""Sección de generación QA, conservando el flujo visual de la aplicación aprobada."""
from __future__ import annotations

import re

import streamlit as st

from agente_qa.utils import build_case_title, safe_text


def _suite_options():
    """Obtiene las Suites consultadas para que la selección controle la generación."""
    suites = st.session_state.get("azure_reference_suites", []) or []
    valid = [s for s in suites if safe_text(s.get("name"))]
    return valid


def _apply_suite_to_result(result, suite_name):
    """Asigna la Suite seleccionada y normaliza ID/Título antes de exportar."""
    if not suite_name:
        return result

    data = dict(result)
    cases = []
    for index, original in enumerate(data.get("TEST_CASES", []) or [], start=1):
        tc = dict(original)
        raw_id = safe_text(tc.get("ID"), f"CP-AU-{index:05d}")
        title = build_case_title(tc, raw_id, suite_name=suite_name, module=safe_text(tc.get("Module")))
        match = re.search(r"^(CP-[A-Z0-9]{2,5}-\d{5})\s", title)
        if match:
            tc["ID"] = match.group(1)
        tc["Title"] = title.split(" ", 1)[1] if " " in title else title
        tc["SUITE_NAME"] = suite_name
        cases.append(tc)
    data["TEST_CASES"] = cases
    data["SUITE_NAME"] = suite_name
    return data


def render_generation_section(generate_qa_data, load_prompt, source_text, api_key, selected_model, max_retries, wait_time, coverage_gate_or_stop, create_excel, create_pdf, selected_config):
    st.divider()
    st.subheader("🧪 Generación QA")

    suites = _suite_options()
    suite_names = [safe_text(s.get("name")) for s in suites]
    if suite_names:
        selected_suite_name = st.selectbox(
            "Suite para generar los CP",
            suite_names,
            key="qa_generation_suite_name",
            help="La Suite seleccionada define las siglas del ID y la numeración de los CP exportados.",
        )
        st.caption(f"Los CP se generarán con la Suite **{selected_suite_name}**. Se usa su nombre para construir las siglas del ID.")
    else:
        selected_suite_name = ""
        st.caption("⚠️ No hay una Suite consultada. Los CP usarán la convención por defecto hasta seleccionar una Suite.")

    if st.button("🚀 Generar casos de prueba", type="primary", disabled=not bool(source_text.strip())):
        try:
            with st.spinner("Analizando documentación y generando casos..."):
                result = generate_qa_data(
                    load_prompt(), source_text, api_key, selected_model,
                    0.0, int(max_retries), int(wait_time)
                )
            result = _apply_suite_to_result(result, selected_suite_name)
            coverage_gate_or_stop(result)
            st.session_state.result_json = result
            st.session_state.azure_reference_preview = None
            st.session_state.azure_preview_edit_mode = False
            st.session_state.excel_data = create_excel(result, selected_config)
            st.session_state.pdf_data = create_pdf(result, selected_config, st.session_state.get("source_name", ""))
        except Exception as exc:
            st.error(f"❌ Error durante la generación: {exc}")
