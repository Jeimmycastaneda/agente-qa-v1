"""Sección de carga de documentación, migrada desde la interfaz funcional aprobada."""
from __future__ import annotations

import streamlit as st


def render_document_section(extract_source):
    st.subheader("📁 Carga de Documento")
    st.info(
        "Formatos de HU: TXT, MD, PDF, DOCX, XLSX/CSV. "
        "Para PDF escaneado se requiere OCR; esta versión no inventa "
        "texto que no pueda extraer."
    )
    uploaded = st.file_uploader(
        "Arrastra o selecciona un documento",
        type=["txt", "md", "pdf", "docx", "xlsx", "xls", "csv"],
    )
    source_text = st.session_state.get("source_content", "")

    if uploaded:
        if st.session_state.get("source_name", "") != uploaded.name:
            try:
                with st.spinner(f"Procesando {uploaded.name}..."):
                    source_text = extract_source(uploaded)
                st.session_state.source_content = source_text
                st.session_state.source_name = uploaded.name
                st.session_state.result_json = None
                st.session_state.excel_data = None
                st.session_state.pdf_data = None
                st.success(f"✅ {uploaded.name} procesado correctamente.")
            except Exception as exc:
                st.session_state.source_content = ""
                st.session_state.source_name = ""
                st.session_state.result_json = None
                st.session_state.excel_data = None
                st.session_state.pdf_data = None
                st.error(f"❌ No se pudo procesar el archivo: {exc}")

    if source_text:
        with st.expander("📄 Vista previa del contenido", expanded=True):
            st.text_area("Contenido", source_text[:5000], height=250, disabled=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Caracteres", len(source_text))
            c2.metric("Líneas", len(source_text.splitlines()))
            c3.metric("Palabras", len(source_text.split()))
    else:
        source_text = st.text_area(
            "✏️ O ingresa el texto manualmente",
            height=220,
            placeholder="Pega aquí la Historia de Usuario o documentación fuente...",
        )
        if source_text:
            st.session_state.source_content = source_text

    return source_text
