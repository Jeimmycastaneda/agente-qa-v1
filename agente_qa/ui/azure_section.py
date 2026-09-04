"""Interfaz Azure DevOps del Agente QA.

La UI Azure se mantiene separada de la lógica HTTP histórica durante la
migración. Este módulo recibe las operaciones como dependencias y conserva
la regla de seguridad: las consultas y previews son GET; la creación solo
se ejecuta después de una confirmación explícita.
"""
from __future__ import annotations

import html
import os
import re

import pandas as pd
import streamlit as st

from agente_qa.utils import build_azure_description, build_case_title, safe_steps, safe_text

_REFERENCE_LABELS = ["Producto:", "Módulo:", "Descripción:", "Resultado esperado de la prueba:", "Precondiciones:", "Caso de uso relacionado:"]


def _ui(value, default=""):
    return safe_text(value, default)


def _reference_description_pretty(description):
    raw = html.unescape(safe_text(description))
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(div|p|li|ul|blockquote|strong|b)>", "\n", raw)
    raw = re.sub(r"(?i)<li[^>]*>", "• ", raw)
    raw = re.sub(r"<[^>]+>", "", raw).replace("\xa0", " ")
    raw = re.sub(r"[ \t]+", " ", raw)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", raw).strip()


def _reference_description_sections(description):
    text = _reference_description_pretty(description)
    sections = []
    for idx, label in enumerate(_REFERENCE_LABELS):
        start = re.search(re.escape(label), text, flags=re.I)
        if not start:
            sections.append((label, "No encontrado en la referencia."))
            continue
        content_start = start.end()
        positions = []
        for next_label in _REFERENCE_LABELS[idx + 1:]:
            match = re.search(re.escape(next_label), text[content_start:], flags=re.I)
            if match:
                positions.append(content_start + match.start())
        end = min(positions) if positions else len(text)
        sections.append((label, text[content_start:end].strip(" \n:-") or "Sin contenido visible."))
    return sections


def _reference_compare(detail):
    description = safe_text(detail.get("description"))
    steps = detail.get("steps") or []
    low = description.lower()
    return {
        "Producto dentro de Description": "producto:" in low,
        "Módulo dentro de Description": "módulo:" in low or "modulo:" in low,
        "Descripción dentro de Description": "descripción:" in low or "descripcion:" in low,
        "Resultado esperado dentro de Description": "resultado esperado de la prueba:" in low,
        "Precondiciones dentro de Description": "precondiciones:" in low,
        "Caso de uso relacionado dentro de Description": "caso de uso relacionado:" in low,
        "Steps con Action + Expected": bool(steps) and all(safe_text(s.get("Action")) and safe_text(s.get("Expected value")) for s in steps),
    }


def _build_reference_preview_case(reference_detail, generated_case):
    tc = dict(generated_case or {})
    sections = dict(_reference_description_sections(reference_detail.get("description", "")))
    product = safe_text(tc.get("Product"), sections.get("Producto:", ""), "Pendiente")
    module = safe_text(tc.get("Module"), sections.get("Módulo:", ""), "Pendiente")
    description = safe_text(tc.get("Description"), tc.get("Scenario"), "Pendiente")
    expected = safe_text(tc.get("Expected Result"), "Pendiente")
    preconditions = safe_text(tc.get("Preconditions"), "Pendiente")
    related = safe_text(tc.get("Related Use Case"), "Pendiente")
    return {
        "ID": safe_text(tc.get("ID")), "Title": build_case_title(tc, safe_text(tc.get("ID"), "CP-PREVIEW")),
        "Product": product, "Module": module,
        "Description": build_azure_description(product, module, description, expected, preconditions, related),
        "Preconditions": preconditions, "Expected Result": expected, "Related Use Case": related,
        "Steps": safe_steps(tc), "reference_test_case_id": reference_detail.get("id"),
        "reference_test_case_title": reference_detail.get("title"),
    }


def _init_state():
    defaults = {
        "azure_reference_plans": [], "azure_reference_plan_id": None, "azure_reference_suites": [],
        "azure_reference_suite_id": None, "azure_reference_cases": [], "azure_reference_case_id": None,
        "azure_reference_detail": None, "azure_reference_preview": None, "azure_preview_edit_mode": False,
        "azure_target_plan_id": None, "azure_target_suite_id": None, "azure_target_suites": [],
        "azure_publish_selection": "Un solo CP", "azure_publish_results": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_azure_sidebar(*, fallback_models, excel_configs, test_connection, azure_error_type,
                        list_test_plans, list_test_suites, list_test_cases, get_test_case_detail,
                        delete_test_case, calculate_cu_coverage, create_excel, create_pdf,
                        result, source_name):
    """Renderiza configuración + referencia Azure en la barra lateral."""
    _init_state()
    st.header("⚙️ Configuración")
    try:
        secrets = st.secrets
    except Exception:
        secrets = {}
    api_key = secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if api_key:
        st.success("✅ GEMINI_API_KEY configurada")
    else:
        api_key = st.text_input("🔑 Google Gemini API Key", type="password")
    selected_model = st.selectbox("Modelo", fallback_models, index=0)
    selected_config = st.selectbox("Formato de Excel", list(excel_configs.keys()), index=0)
    max_retries = st.number_input("Máximo de reintentos", min_value=0, max_value=5, value=2)
    wait_time = st.number_input("Espera inicial (segundos)", min_value=1, max_value=60, value=10)

    st.divider(); st.subheader("🔐 Azure DevOps")
    st.caption("Prueba de conexión y consultas de referencia en modo solo lectura. No crean ni modifican CP.")
    if st.button("🔌 Probar conexión con Azure DevOps", key="azure_test_connection"):
        try:
            with st.spinner("Verificando conexión con Azure DevOps..."):
                azure_result = test_connection()
            st.success("✅ Conexión con Azure DevOps correcta.")
            st.caption(f"Organización: {azure_result['organization']} | Proyecto: {azure_result['project']} | Work Item: {azure_result['work_item_type']}")
            st.info(azure_result["message"])
        except azure_error_type as exc:
            st.error(f"❌ No se pudo conectar con Azure DevOps: {exc}")
        except Exception as exc:
            st.error(f"❌ Error inesperado al probar Azure DevOps: {exc}")

    st.markdown("### 📋 Test Plans")
    st.caption("Consulta de solo lectura. Solo se muestran los 10 Test Plans más recientes.")
    if st.button("📋 Consultar 10 Test Plans", key="azure_list_test_plans"):
        try:
            with st.spinner("Consultando los 10 Test Plans más recientes..."):
                plans_result = list_test_plans(limit=10)
            st.session_state.azure_reference_plans = plans_result.get("plans", [])
            for key in ("azure_reference_plan_id", "azure_reference_suite_id", "azure_reference_case_id", "azure_reference_detail", "azure_reference_preview"):
                st.session_state[key] = None
            st.session_state.azure_reference_suites = []; st.session_state.azure_reference_cases = []
            st.success(f"✅ Consulta correcta: {len(st.session_state.azure_reference_plans)} Test Plan(s) más recientes.")
            st.info(plans_result.get("message", "Consulta completada."))
        except Exception as exc:
            st.error(f"❌ No se pudieron consultar los Test Plans: {exc}")

    plans = st.session_state.azure_reference_plans
    if plans:
        plan_options = [f"{_ui(p.get('id'), 'SIN ID')} — {_ui(p.get('name'), 'Test Plan sin nombre')}" for p in plans]
        selected_plan_label = st.selectbox("1️⃣ Test Plan", plan_options, key="azure_reference_plan_select")
        selected_plan_id = plans[plan_options.index(selected_plan_label)].get("id")
        if st.button("🔎 Consultar Suites", key="azure_reference_get_suites"):
            try:
                with st.spinner("Consultando Suites del Test Plan seleccionado..."):
                    suites = list_test_suites(selected_plan_id)
                st.session_state.azure_reference_plan_id = selected_plan_id; st.session_state.azure_reference_suites = suites
                st.session_state.azure_reference_suite_id = None; st.session_state.azure_reference_cases = []
                st.session_state.azure_reference_case_id = None; st.session_state.azure_reference_detail = None; st.session_state.azure_reference_preview = None
                st.success(f"✅ {len(suites)} Suite(s) encontradas.")
            except Exception as exc:
                st.error(f"❌ No se pudieron consultar las Suites: {exc}")

    if result and result.get("TEST_CASES"):
        st.markdown("### 🗑️ Eliminar caso de prueba")
        st.caption("Esta acción elimina el CP solo de la generación actual y de COVERAGE; no elimina recursos de Azure DevOps.")
        delete_cases = result.get("TEST_CASES", []) or []
        delete_options = [f"{safe_text(tc.get('ID'), f'CASO-{idx + 1:05d}')} — {build_case_title(tc, safe_text(tc.get('ID'), f'CASO-{idx + 1:05d}'))[:100]}" for idx, tc in enumerate(delete_cases)]
        delete_label = st.selectbox("Selecciona el CP que deseas eliminar", delete_options, key="v44_delete_case_select")
        delete_index = delete_options.index(delete_label); delete_case_id = safe_text(delete_cases[delete_index].get("ID"), f"CASO-{delete_index + 1:05d}")
        confirm_delete = st.checkbox(f"Confirmo que quiero eliminar {delete_case_id}", key=f"v44_confirm_delete_{delete_index}")
        if st.button("🗑️ Eliminar CP seleccionado", disabled=not confirm_delete, key="v44_delete_cp"):
            candidate_cases = [tc for idx, tc in enumerate(delete_cases) if idx != delete_index]
            if not calculate_cu_coverage(candidate_cases, result.get("USE_CASES", []))["valid"]:
                st.error("🚫 No se puede eliminar este CP porque dejaría al menos un CU sin cobertura.")
            elif delete_test_case(result, delete_index):
                st.session_state.excel_data = create_excel(result, selected_config); st.session_state.pdf_data = create_pdf(result, selected_config, source_name)
                st.success(f"✅ {delete_case_id} eliminado."); st.rerun()

    suites = st.session_state.azure_reference_suites
    if suites:
        suite_options = [f"{_ui(s.get('id'), 'SIN ID')} — {_ui(s.get('name'), 'Suite sin nombre')}" for s in suites]
        selected_suite_label = st.selectbox("2️⃣ Suite", suite_options, key="azure_reference_suite_select")
        selected_suite_id = suites[suite_options.index(selected_suite_label)].get("id")
        if st.button("🔎 Consultar Test Cases", key="azure_reference_get_cases"):
            try:
                plan_id = st.session_state.azure_reference_plan_id or selected_plan_id
                with st.spinner("Consultando Test Cases de la Suite seleccionada..."):
                    cases = list_test_cases(plan_id, selected_suite_id)
                st.session_state.azure_reference_suite_id = selected_suite_id; st.session_state.azure_reference_cases = cases
                st.session_state.azure_reference_case_id = None; st.session_state.pop("azure_reference_case_select", None)
                st.session_state.azure_reference_detail = None; st.session_state.azure_reference_preview = None
                st.success(f"✅ {len(cases)} Test Case(s) encontrados.")
            except Exception as exc:
                st.error(f"❌ No se pudieron consultar los Test Cases: {exc}")

    cases = [c for c in st.session_state.azure_reference_cases if c.get("id") is not None and str(c.get("id")).strip()]
    st.markdown("### 3️⃣ Test Case de referencia")
    if not cases and st.session_state.azure_reference_suite_id:
        st.warning("⚠️ La Suite seleccionada no tiene Test Cases consultables.")
    if cases:
        case_options = [f"{_ui(c.get('id'), 'SIN ID')} — {_ui(c.get('title'), 'Test Case sin título')}" for c in cases]
        selected_case_label = st.selectbox("Selecciona un Test Case real de Azure para comparar su estructura", case_options, key="azure_reference_case_select")
        selected_case_id = cases[case_options.index(selected_case_label)].get("id")
        if st.button("🔬 Consultar y comparar", key="azure_reference_compare"):
            try:
                with st.spinner("Leyendo el Test Case real de Azure..."):
                    detail = get_test_case_detail(selected_case_id)
                st.session_state.azure_reference_case_id = selected_case_id; st.session_state.azure_reference_detail = detail; st.session_state.azure_reference_preview = None
                st.success("✅ Comparación realizada. Solo se ejecutaron consultas GET.")
            except Exception as exc:
                st.error(f"❌ No se pudo consultar el Test Case de referencia: {exc}")

    detail = st.session_state.azure_reference_detail
    if detail:
        st.markdown("## 📌 Test Case de referencia")
        st.markdown(f"**ID:** {safe_text(detail.get('id'))}  \n**Título:** {safe_text(detail.get('title'))}  \n**Estado:** {safe_text(detail.get('state'))}  \n**Area Path:** {safe_text(detail.get('area_path'))}")
        st.markdown("### 📝 Description real de Azure")
        for label, value in _reference_description_sections(detail.get("description", "")):
            with st.container(border=True): st.markdown(f"**{label}**"); st.write(value)
        st.markdown("### 🧪 Steps reales de Azure")
        steps_df = pd.DataFrame(detail.get("steps") or [])
        if not steps_df.empty:
            display_cols = [c for c in ["Step #", "Action", "Expected value"] if c in steps_df.columns]; st.dataframe(steps_df[display_cols], width="stretch", hide_index=True)
        else: st.warning("⚠️ El Test Case de referencia no tiene Steps legibles.")
        checks = _reference_compare(detail)
        st.markdown("### 🔎 Comparación contra nuestra estructura aprobada")
        st.dataframe(pd.DataFrame([{"Elemento": k, "Cumple": "✅" if v else "⚠️"} for k, v in checks.items()]), width="stretch", hide_index=True)
        if all(checks.values()): st.success("✅ La referencia contiene la estructura aprobada.")
        else: st.warning("⚠️ La referencia no contiene todos los elementos esperados. Se conserva solo como referencia estructural.")
        current_result = st.session_state.get("result_json")
        if current_result:
            st.markdown("### 4️⃣ Generar CP nuevo con base en la HU + referencia Azure — PREVIEW")
            st.caption("Los datos funcionales se toman de la HU. La referencia Azure se usa solo para estructura visual. No se crea ni modifica Azure.")
            if st.button("🧩 Generar CP nuevo para revisión funcional", key="azure_prepare_new_cp_preview"):
                generated_cases = current_result.get("TEST_CASES", []) or []
                if not generated_cases: st.error("❌ No hay Test Cases generados a partir de la HU.")
                else:
                    previews = [_build_reference_preview_case(detail, tc) for tc in generated_cases]
                    st.session_state.azure_reference_preview = previews; st.session_state.azure_preview_edit_mode = True
                    result_for_preview = dict(current_result); result_for_preview["TEST_CASES"] = previews; st.session_state.result_json = result_for_preview
                    st.success(f"✅ {len(previews)} CP(s) preparados para revisión funcional."); st.rerun()

    return {"api_key": api_key, "selected_model": selected_model, "selected_config": selected_config, "max_retries": max_retries, "wait_time": wait_time}


def render_azure_publish(*, result, selected_config, list_test_suites, list_test_cases, create_selected_cases_in_azure):
    """Renderiza selección/destino/confirmación. La escritura requiere confirmación explícita."""
    if not result: return
    st.divider(); st.subheader("🚀 Cargar CP en Azure DevOps")
    st.caption("La creación real ocurre únicamente después de seleccionar CP, Test Plan y Suite y confirmar explícitamente el resumen.")
    publish_cases = result.get("TEST_CASES", []) or []
    publish_case_map = {safe_text(tc.get("ID")): tc for tc in publish_cases if safe_text(tc.get("ID"))}
    st.markdown("### 1️⃣ Seleccionar CP y destino")
    selection_mode = st.radio("Casos a cargar", ["Un solo CP", "Seleccionar varios CP", "Todos los CP"], horizontal=True, key="azure_publish_selection")
    labels = list(publish_case_map.keys())
    if selection_mode == "Un solo CP":
        selected_publish_ids = [st.selectbox("CP a cargar", labels, format_func=lambda x: f"{x} — {build_case_title(publish_case_map[x], x)[:100]}", key="azure_publish_single_case")] if labels else []
    elif selection_mode == "Seleccionar varios CP":
        selected_publish_ids = st.multiselect("Selecciona los CP que deseas cargar", labels, format_func=lambda x: f"{x} — {build_case_title(publish_case_map[x], x)[:100]}", key="azure_publish_multi_cases")
    else:
        selected_publish_ids = labels; st.info(f"Se cargarán los {len(selected_publish_ids)} CP generados actualmente.")
    target_plans = st.session_state.get("azure_reference_plans", []) or []
    if not target_plans: st.warning("⚠️ Primero consulta los 10 Test Plans más recientes para seleccionar el destino."); return
    plan_labels = [f"{p.get('id')} — {_ui(p.get('name'), 'Sin nombre')}" for p in target_plans]
    target_plan = target_plans[plan_labels.index(st.selectbox("Test Plan destino", plan_labels, key="azure_publish_target_plan"))]
    target_plan_id = str(target_plan.get("id"))
    if st.session_state.get("azure_target_plan_id") != target_plan_id:
        st.session_state.azure_target_plan_id = target_plan_id; st.session_state.azure_target_suite_id = None
        try:
            with st.spinner("Consultando Suites del Test Plan destino..."): st.session_state.azure_target_suites = list_test_suites(target_plan_id)
        except Exception as exc: st.session_state.azure_target_suites = []; st.error(f"❌ No se pudieron consultar las Suites del destino: {exc}")
    target_suites = st.session_state.get("azure_target_suites", []) or []
    if not target_suites: st.warning("⚠️ El Test Plan seleccionado no tiene Suites consultables."); return
    suite_labels = [f"{s.get('id')} — {_ui(s.get('name'), 'Suite sin nombre')}" for s in target_suites]
    target_suite = target_suites[suite_labels.index(st.selectbox("Suite destino", suite_labels, key="azure_publish_target_suite"))]
    st.session_state.azure_target_suite_id = str(target_suite.get("id"))
    st.markdown("### Datos obligatorios del proyecto para crear el Test Case")
    st.caption("IDPadre debe corresponder al Work Item padre real; no se sustituye por el Test Plan ni por la Suite.")
    inferred_parent = ""
    if selected_publish_ids:
        first_case = publish_case_map[selected_publish_ids[0]]
        for key in ("IDPadre", "ID Padre", "Parent ID", "ParentId", "parent_id", "id_padre"):
            if safe_text(first_case.get(key)): inferred_parent = safe_text(first_case.get(key)); break
    id_padre = st.text_input("IDPadre (Work Item padre / HU)", value=safe_text(st.session_state.get("azure_id_padre"), inferred_parent), placeholder="Ej. 12345", key="azure_id_padre_input")
    st.session_state.azure_id_padre = id_padre.strip()
    tipo_origen = st.text_input("Tipo Origen Proyecto", value=safe_text(st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto"), key="azure_tipo_origen_input")
    st.session_state.azure_tipo_origen_proyecto = tipo_origen.strip() or "Proyecto"
    duplicate_titles = []
    if target_suite and selected_publish_ids:
        try:
            existing = list_test_cases(target_plan_id, target_suite.get("id")); existing_titles = {re.sub(r"\s+", " ", safe_text(row.get("title"))).strip().casefold() for row in existing}
            for cp_id in selected_publish_ids:
                if re.sub(r"\s+", " ", build_case_title(publish_case_map[cp_id], cp_id)).strip().casefold() in existing_titles: duplicate_titles.append(cp_id)
        except Exception as exc: st.warning(f"⚠️ No fue posible validar duplicados antes de la creación: {exc}")
    if duplicate_titles: st.error("🚫 Se detectaron títulos que ya existen en la Suite destino: " + ", ".join(duplicate_titles) + ". La creación queda bloqueada.")
    ready = bool(selected_publish_ids and target_plan and target_suite and not duplicate_titles and safe_text(st.session_state.get("azure_id_padre")) and safe_text(st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto"))
    if not safe_text(st.session_state.get("azure_id_padre")): st.warning("⚠️ Falta IDPadre. La creación queda bloqueada porque Azure lo exige.")
    st.markdown("### 2️⃣ Revisar y confirmar creación")
    st.dataframe(pd.DataFrame([{"CP": cp_id, "Título": build_case_title(publish_case_map[cp_id], cp_id), "Caso de Uso": safe_text(publish_case_map[cp_id].get("Related Use Case"), "Pendiente"), "Steps": len(safe_steps(publish_case_map[cp_id]))} for cp_id in selected_publish_ids]), width="stretch", hide_index=True)
    st.warning("⚠️ La sincronización modifica Azure DevOps: crea los Test Cases y los asocia a la Suite seleccionada.")
    confirm = st.checkbox("Confirmo que los CP, Test Plan, Suite, IDPadre y Tipo Origen Proyecto son correctos y autorizo la creación en Azure.", key="azure_publish_confirm")
    if st.button("🔄 Sincronizar con Azure DevOps", type="primary", disabled=not (ready and confirm), key="azure_publish_execute"):
        try:
            selected_cases = []
            for cp_id in selected_publish_ids:
                tc = dict(publish_case_map[cp_id]); tc["IDPadre"] = safe_text(st.session_state.get("azure_id_padre")); tc["Tipo Origen Proyecto"] = safe_text(st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto"); selected_cases.append(tc)
            with st.spinner(f"Sincronizando {len(selected_cases)} Test Case(s) con Azure DevOps..."):
                st.session_state.azure_publish_results = create_selected_cases_in_azure(selected_cases, target_plan, target_suite)
            st.rerun()
        except Exception as exc: st.error(f"❌ No se pudo completar la sincronización con Azure: {exc}")
    publish_result = st.session_state.get("azure_publish_results")
    if publish_result:
        st.markdown("### 📌 Resultado de la creación en Azure")
        if publish_result.get("created"):
            st.dataframe(pd.DataFrame([{"CP generado": r.get("cp_id"), "Azure ID": r.get("azure_id"), "Estado": r.get("status")} for r in publish_result["created"]]), width="stretch", hide_index=True)
            st.success(f"✅ {len(publish_result['created'])} CP procesados en Azure.")
        for err in publish_result.get("errors", []): st.error(f"❌ {err.get('cp_id')}: {err.get('error')}")
