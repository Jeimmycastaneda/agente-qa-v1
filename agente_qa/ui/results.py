"""Resultados, editor y descargas; migrado del flujo visual aprobado."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from agente_qa.utils import build_case_title, normalize_case_id, safe_steps, safe_text


def render_results_section(result, selected_config, excel_configs, calculate_cu_coverage,
                           render_cu_coverage, render_editor, create_excel, create_pdf, coverage_gate_or_stop):
    if not result:
        return

    st.divider()
    st.subheader("📊 Resultados")

    c1, c2, c3 = st.columns(3)
    c1.metric("Casos", len(result.get("TEST_CASES", [])))
    c2.metric("Alertas", len(result.get("ALERTS", [])))
    c3.metric("CUs", len(result.get("USE_CASES", [])))

    current_coverage = calculate_cu_coverage(
        result.get("TEST_CASES", []), result.get("USE_CASES", [])
    )
    render_cu_coverage(current_coverage)

    st.subheader("✏️ Editar caso de prueba")
    if st.session_state.get("azure_reference_preview"):
        st.info(
            "🔎 Revisión funcional: los CP generados desde la HU se muestran aquí mismo. "
            "Usa el selector para revisar y ajustar uno por uno todos los CP generados. "
            "La estructura se basa en el Test Case de referencia de Azure. "
            "Los cambios quedan en PREVIEW y todavía NO modifican Azure."
        )
    else:
        st.caption(
            "Revisa y ajusta el caso antes de descargar Excel/PDF. "
            "Cada Test Case debe conservar un único Caso de Uso relacionado."
        )

    cases = result.get("TEST_CASES", []) or []
    case_options = []
    for idx, tc in enumerate(cases):
        case_id = safe_text(tc.get("ID"), f"CASO-{idx + 1:05d}")
        case_options.append(f"{case_id} — {build_case_title(tc, case_id)[:100]}")

    if case_options:
        selected_case_label = st.selectbox(
            "Selecciona el caso que deseas editar", case_options,
            key="qa_editor_selected_case",
        )
        selected_index = case_options.index(selected_case_label)
        selected_case = cases[selected_index]
        selected_case_id = safe_text(selected_case.get("ID"), f"CASO-{selected_index + 1:05d}")
        st.markdown(f"### {selected_case_id}")
        st.info(
            "El ID no se puede modificar. La relación funcional del caso "
            "debe corresponder a un solo Caso de Uso."
        )

        editor_result = render_editor(selected_case, selected_index)
        if editor_result == "saved":
            coverage_after_edit = calculate_cu_coverage(
                result.get("TEST_CASES", []), result.get("USE_CASES", [])
            )
            if not coverage_after_edit["valid"]:
                st.error("🚫 El cambio dejaría un CU sin CP. Corrige la relación antes de exportar.")
            else:
                st.session_state.excel_data = create_excel(result, selected_config)
                st.session_state.pdf_data = create_pdf(result, selected_config, st.session_state.get("source_name", ""))
                st.success(f"✅ {selected_case_id} actualizado. Excel y PDF regenerados.")
                st.rerun()
    else:
        st.info("No hay Test Cases para editar.")

    config = excel_configs[selected_config]
    if not safe_text(config.get("area_path")) or not safe_text(config.get("assigned_to")):
        st.warning(
            "⚠️ El Excel conserva la estructura Azure y agrega Tipo Origen Proyecto = Proyecto. "
            "Antes de importar, verifica Assigned To en EXCEL_CONFIGS con valores reales de tu proyecto/organización; no se inventan automáticamente."
        )

    coverage_ok = calculate_cu_coverage(
        result.get("TEST_CASES", []), result.get("USE_CASES", [])
    )["valid"]
    if not coverage_ok:
        st.error("🚫 Descargas deshabilitadas: la cobertura mínima por CU no se cumple.")

    current_excel_data = create_excel(result, selected_config)
    st.session_state.excel_data = current_excel_data
    st.download_button(
        "📊 Descargar Excel", data=current_excel_data,
        file_name=f"QA_DRAFT_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=not coverage_ok,
    )
    st.download_button(
        "📄 Descargar PDF", data=st.session_state.pdf_data,
        file_name=f"QA_DRAFT_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf", disabled=not coverage_ok,
    )

    with st.expander("🔎 Ver JSON generado", expanded=False):
        st.json(result)

    st.subheader("🧪 Casos generados")
    preview_rows = []
    for tc in cases:
        preview_rows.append({
            "ID": safe_text(tc.get("ID")),
            "Title": build_case_title(tc, normalize_case_id(
                tc.get("ID"), safe_text(tc.get("Module"), "GENERAL"),
                len(preview_rows) + 1, config["title_prefix"])),
            "Module": safe_text(tc.get("Module")),
            "Scenario Type": safe_text(tc.get("Scenario Type")),
            "Steps": len(safe_steps(tc)),
        })
    st.dataframe(pd.DataFrame(preview_rows), width="stretch")
