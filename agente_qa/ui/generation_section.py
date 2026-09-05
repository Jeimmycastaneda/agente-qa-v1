"""Sección de generación QA, conservando el flujo visual de la aplicación aprobada."""
from __future__ import annotations

import streamlit as st


def render_generation_section(generate_qa_data, load_prompt, source_text, api_key, selected_model, max_retries, wait_time, coverage_gate_or_stop, create_excel, create_pdf, selected_config):
    st.divider()
    st.subheader("🧪 Generación QA")
    if st.button("🚀 Generar casos de prueba", type="primary", disabled=not bool(source_text.strip())):
        try:
            with st.spinner("Analizando documentación y generando casos..."):
                result = generate_qa_data(
                    load_prompt(), source_text, api_key, selected_model,
                    0.0, int(max_retries), int(wait_time)
                )
            coverage_gate_or_stop(result)
            st.session_state.result_json = result
            st.session_state.azure_reference_preview = None
            st.session_state.azure_preview_edit_mode = False
            st.session_state.excel_data = create_excel(result, selected_config)
            st.session_state.pdf_data = create_pdf(result, selected_config, st.session_state.get("source_name", ""))
        except Exception as exc:
            st.error(f"❌ Error durante la generación: {exc}")
