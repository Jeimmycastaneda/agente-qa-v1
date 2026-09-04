"""Componente Streamlit para disparar la generación QA."""
from __future__ import annotations

import streamlit as st


def render_generation(generate_qa_data, load_prompt, source_text, api_key, selected_model, max_retries, wait_time, coverage_gate_or_stop):
    """Ejecuta la generación cuando el usuario la solicita y devuelve el resultado."""
    st.divider()
    st.subheader("🧪 Generación QA")
    if st.button("🚀 Generar casos de prueba", type="primary", disabled=not bool(source_text.strip())):
        try:
            with st.spinner("Analizando documentación y generando casos..."):
                result = generate_qa_data(load_prompt(), source_text, api_key, selected_model, 0.0, int(max_retries), int(wait_time))
            coverage_gate_or_stop(result)
            return result
        except Exception as exc:
            st.error(f"❌ Error durante la generación: {exc}")
    return None
