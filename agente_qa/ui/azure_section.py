"""Interfaz Azure DevOps del Agente QA."""
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
        "Steps con Action + Expected": bool(steps) and all(safe_text(s.get("Action")) and safe_text(s.get("Expected value"), s.get("Expected")) for s in steps),
    }


def _build_reference_preview_case(reference_details, generated_case):
    tc = dict(generated_case or {})
    details = reference_details if isinstance(reference_details, list) else [reference_details]
    details = [d for d in details if isinstance(d, dict)]
    section_values = {label: "" for label in _REFERENCE_LABELS}
    for detail in details:
        for label, value in _reference_description_sections(detail.get("description", "")):
            if not section_values[label] and value not in {"No encontrado en la referencia.", "Sin contenido visible."}:
                section_values[label] = value
    product = safe_text(tc.get("Product"), section_values.get("Producto:", ""), "Pendiente")
    module = safe_text(tc.get("Module"), section_values.get("Módulo:", ""), "Pendiente")
    description = safe_text(tc.get("Description"), tc.get("Scenario"), "Pendiente")
    expected = safe_text(tc.get("Expected Result"), "Pendiente")
    preconditions = safe_text(tc.get("Preconditions"), "Pendiente")
    related = safe_text(tc.get("Related Use Case"), "Pendiente")
    reference_ids = [safe_text(d.get("id")) for d in details if safe_text(d.get("id"))]
    reference_titles = [safe_text(d.get("title")) for d in details if safe_text(d.get("title"))]
    return {
        "ID": safe_text(tc.get("ID")),
        "Title": build_case_title(tc, safe_text(tc.get("ID"), "CP-PREVIEW")),
        "Product": product, "Module": module,
        "Description": build_azure_description(product, module, description, expected, preconditions, related),
        "Preconditions": preconditions, "Expected Result": expected, "Related Use Case": related,
        "Steps": safe_steps(tc), "SUITE_NAME": safe_text(tc.get("SUITE_NAME"), st.session_state.get("qa_generation_suite_name", "")),
        "reference_test_case_ids": reference_ids, "reference_test_case_titles": reference_titles,
    }


def _analyze_reference_details(details):
    valid_details = [d for d in (details or []) if isinstance(d, dict)]
    checks = [_reference_compare(detail) for detail in valid_details]
    if not checks:
        return {"count": 0, "all": {}, "common": {}}
    keys = list(checks[0].keys())
    common = {key: all(item.get(key, False) for item in checks) for key in keys}
    return {"count": len(valid_details), "all": checks, "common": common}


def _init_state():
    defaults = {
        "azure_reference_plans": [], "azure_reference_plan_id": None, "azure_reference_suites": [], "azure_reference_suite_id": None,
        "azure_reference_cases": [], "azure_reference_case_id": None, "azure_reference_case_ids": [], "azure_reference_detail": None,
        "azure_reference_details": [], "azure_reference_analysis": None, "azure_reference_preview": None, "azure_preview_edit_mode": False,
        "azure_target_plan_id": None, "azure_target_suite_id": None, "azure_target_suites": [], "azure_publish_selection": "Un solo CP", "azure_publish_results": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_azure_sidebar(*, fallback_models, excel_configs, test_connection, azure_error_type, list_test_plans, list_test_suites, list_test_cases, get_test_case_detail, delete_test_case, calculate_cu_coverage, create_excel, create_pdf, result, source_name):
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
            for key in ("azure_reference_plan_id", "azure_reference_suite_id", "azure_reference_case_id", "azure_reference_detail", "azure_reference_details", "azure_reference_analysis", "azure_reference_preview"):
                st.session_state[key] = None
            st.session_state.azure_reference_case_ids = []; st.session_state.azure_reference_suites = []; st.session_state.azure_reference_cases = []
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
                st.session_state.azure_reference_plan_id = selected_plan_id; st.session_state.azure_reference_suites = suites; st.session_state.azure_reference_suite_id = None; st.session_state.azure_reference_cases = []; st.session_state.azure_reference_case_id = None; st.session_state.azure_reference_case_ids = []; st.session_state.azure_reference_detail = None; st.session_state.azure_reference_details = []; st.session_state.azure_reference_analysis = None; st.session_state.azure_reference_preview = None
                st.success(f"✅ {len(suites)} Suite(s) encontradas.")
            except Exception as exc:
                st.error(f"❌ No se pudieron consultar las Suites: {exc}")
    suites = st.session_state.azure_reference_suites
    if suites:
        suite_options = [f"{_ui(s.get('id'), 'SIN ID')} — {_ui(s.get('name'), 'Suite sin nombre')}" for s in suites]
        selected_suite_label = st.selectbox("2️⃣ Suite", suite_options, key="azure_reference_suite_select")
        selected_suite = suites[suite_options.index(selected_suite_label)]
        selected_suite_id = selected_suite.get("id")
        st.session_state.azure_generation_suite_id = selected_suite_id
        st.session_state.azure_generation_suite_name = safe_text(selected_suite.get("name"))
        if st.button("🔎 Consultar Test Cases", key="azure_reference_get_cases"):
            try:
                plan_id = st.session_state.azure_reference_plan_id or selected_plan_id
                with st.spinner("Consultando Test Cases de la Suite seleccionada..."):
                    cases = list_test_cases(plan_id, selected_suite_id)
                st.session_state.azure_reference_suite_id = selected_suite_id; st.session_state.azure_reference_cases = cases; st.session_state.azure_reference_case_id = None; st.session_state.azure_reference_case_ids = []; st.session_state.azure_reference_detail = None; st.session_state.azure_reference_details = []; st.session_state.azure_reference_analysis = None; st.session_state.azure_reference_preview = None
                st.success(f"✅ {len(cases)} Test Case(s) encontrados.")
            except Exception as exc:
                st.error(f"❌ No se pudieron consultar los Test Cases: {exc}")
    cases = [c for c in st.session_state.azure_reference_cases if c.get("id") is not None and str(c.get("id")).strip()]
    st.markdown("### 3️⃣ Test Cases de referencia de la Suite")
    if not cases and st.session_state.azure_reference_suite_id:
        st.warning("⚠️ La Suite seleccionada no tiene Test Cases consultables.")
    if cases:
        st.info(f"Se analizarán los {len(cases)} Test Case(s) encontrados en la Suite seleccionada como referencia estructural conjunta.")
        if st.button("🔬 Consultar y analizar todos los Test Cases", key="azure_reference_compare_all"):
            try:
                details = []; errors = []
                with st.spinner(f"Leyendo {len(cases)} Test Case(s) reales de Azure..."):
                    for case in cases:
                        case_id = case.get("id")
                        try: details.append(get_test_case_detail(case_id))
                        except Exception as exc: errors.append(f"{case_id}: {exc}")
                st.session_state.azure_reference_case_ids = [safe_text(d.get("id")) for d in details if safe_text(d.get("id"))]; st.session_state.azure_reference_details = details; st.session_state.azure_reference_case_id = None; st.session_state.azure_reference_detail = None; st.session_state.azure_reference_analysis = _analyze_reference_details(details); st.session_state.azure_reference_preview = None
                if errors: st.warning(f"⚠️ Se consultaron {len(details)} de {len(cases)} CP. Algunos no pudieron leerse: {' | '.join(errors)}")
                else: st.success(f"✅ Se analizaron {len(details)} Test Case(s) de la Suite. Solo se ejecutaron consultas GET.")
            except Exception as exc: st.error(f"❌ No se pudieron analizar los Test Cases de la Suite: {exc}")
    details = st.session_state.get("azure_reference_details", []) or []; analysis = st.session_state.get("azure_reference_analysis")
    if details:
        st.markdown("## 📌 Referencia conjunta de la Suite")
        st.caption(f"CP analizados: {len(details)}. Los datos funcionales del nuevo CP siguen proviniendo de la HU; Azure se utiliza únicamente como referencia estructural.")
        common = (analysis or {}).get("common", {})
        if common: st.dataframe(pd.DataFrame([{"Elemento": key, "Cumplimiento común": "✅" if value else "⚠️"} for key, value in common.items()]), width="stretch", hide_index=True)
        st.markdown("### 🧪 Test Cases consultados")
        st.dataframe(pd.DataFrame([{"ID": d.get("id"), "Título": d.get("title"), "Estado": d.get("state"), "Steps": len(d.get("steps") or [])} for d in details]), width="stretch", hide_index=True)
        st.markdown("### 📝 Estructura de Description observada")
        for label in _REFERENCE_LABELS:
            values = []
            for detail in details:
                section_map = dict(_reference_description_sections(detail.get("description", ""))); value = section_map.get(label, "")
                if value and value not in {"No encontrado en la referencia.", "Sin contenido visible."}: values.append(value)
            with st.container(border=True): st.markdown(f"**{label}**"); st.write(values[0] if values else "No encontrado en las referencias consultadas.")
        st.markdown("### 🧪 Steps de los CP de referencia")
        for detail in details:
            st.markdown(f"**{safe_text(detail.get('id'))} — {safe_text(detail.get('title'))}**")
            steps_df = pd.DataFrame(detail.get("steps") or [])
            if not steps_df.empty:
                display_cols = [c for c in ["Step #", "Action", "Expected value", "Expected"] if c in steps_df.columns]; st.dataframe(steps_df[display_cols], width="stretch", hide_index=True)
            else: st.warning("⚠️ Este Test Case de referencia no tiene Steps legibles.")
        current_result = st.session_state.get("result_json")
        if current_result:
            st.markdown("### 4️⃣ Generar CP nuevo con base en la HU + referencia Azure — PREVIEW")
            st.caption("Los datos funcionales se toman de la HU. Todos los CP de la Suite se usan solo para estructura visual y nivel de detalle. No se copian reglas funcionales de Azure.")
            if st.button("🧩 Generar CP nuevo para revisión funcional", key="azure_prepare_new_cp_preview"):
                generated_cases = current_result.get("TEST_CASES", []) or []
                if not generated_cases: st.error("❌ No hay Test Cases generados a partir de la HU.")
                else:
                    previews = [_build_reference_preview_case(details, tc) for tc in generated_cases]; st.session_state.azure_reference_preview = previews; st.session_state.azure_preview_edit_mode = True; result_for_preview = dict(current_result); result_for_preview["TEST_CASES"] = previews; st.session_state.result_json = result_for_preview; st.success(f"✅ {len(previews)} CP(s) preparados para revisión funcional."); st.rerun()
    return {"api_key": api_key, "selected_model": selected_model, "selected_config": selected_config, "max_retries": max_retries, "wait_time": wait_time}


def render_azure_publish(*, result, selected_config, list_test_suites, list_test_cases, create_selected_cases_in_azure):
    if not result: return
    st.divider(); st.subheader("🚀 Cargar CP en Azure DevOps")
    st.caption("La creación real ocurre únicamente después de seleccionar CP, Test Plan y Suite y confirmar explícitamente el resumen.")
    publish_cases = result.get("TEST_CASES", []) or []; publish_case_map = {safe_text(tc.get("ID")): tc for tc in publish_cases if safe_text(tc.get("ID"))}
    st.markdown("### 1️⃣ Seleccionar CP y destino")
    selection_mode = st.radio("Casos a cargar", ["Un solo CP", "Seleccionar varios CP", "Todos los CP"], horizontal=True, key="azure_publish_selection")
    labels = list(publish_case_map.keys())
    if selection_mode == "Un solo CP": selected_publish_ids = [st.selectbox("CP a cargar", labels, format_func=lambda x: f"{x} — {build_case_title(publish_case_map[x], x, suite_name=safe_text(publish_case_map[x].get('SUITE_NAME'), st.session_state.get('qa_generation_suite_name', '')))[:100]}", key="azure_publish_single_case")] if labels else []
    elif selection_mode == "Seleccionar varios CP": selected_publish_ids = st.multiselect("Selecciona los CP que deseas cargar", labels, format_func=lambda x: f"{x} — {build_case_title(publish_case_map[x], x, suite_name=safe_text(publish_case_map[x].get('SUITE_NAME'), st.session_state.get('qa_generation_suite_name', '')))[:100]}", key="azure_publish_multi_cases")
    else: selected_publish_ids = labels; st.info(f"Se cargarán los {len(selected_publish_ids)} CP generados actualmente.")
    target_plans = st.session_state.get("azure_reference_plans", []) or []
    if not target_plans: st.warning("⚠️ Primero consulta los 10 Test Plans más recientes para seleccionar el destino."); return
    plan_labels = [f"{p.get('id')} — {_ui(p.get('name'), 'Sin nombre')}" for p in target_plans]; target_plan = target_plans[plan_labels.index(st.selectbox("Test Plan destino", plan_labels, key="azure_publish_target_plan"))]; target_plan_id = str(target_plan.get("id"))
    if st.session_state.get("azure_target_plan_id") != target_plan_id:
        st.session_state.azure_target_plan_id = target_plan_id; st.session_state.azure_target_suite_id = None
        try:
            with st.spinner("Consultando Suites del Test Plan destino..."): st.session_state.azure_target_suites = list_test_suites(target_plan_id)
        except Exception as exc: st.session_state.azure_target_suites = []; st.error(f"❌ No se pudieron consultar las Suites del destino: {exc}")
    target_suites = st.session_state.get("azure_target_suites", []) or []
    if not target_suites: st.warning("⚠️ El Test Plan seleccionado no tiene Suites consultables."); return
    suite_labels = [f"{s.get('id')} — {_ui(s.get('name'), 'Suite sin nombre')}" for s in target_suites]; target_suite = target_suites[suite_labels.index(st.selectbox("Suite destino", suite_labels, key="azure_publish_target_suite"))]; st.session_state.azure_target_suite_id = str(target_suite.get("id"))
    st.markdown("### Datos obligatorios del proyecto para crear el Test Case")
    st.caption("IDPadre debe corresponder al CU relacionado y se ingresa desde la interfaz; no se sustituye por el Test Plan ni por la Suite.")
    inferred_parent = ""
    if selected_publish_ids:
        first_case = publish_case_map[selected_publish_ids[0]]
        for key in ("IDPadre", "ID Padre", "Parent ID", "ParentId", "parent_id", "id_padre"):
            if safe_text(first_case.get(key)): inferred_parent = safe_text(first_case.get(key)); break
    id_padre = st.text_input("IDPadre (ID del CU relacionado)", value=safe_text(st.session_state.get("azure_id_padre"), inferred_parent), placeholder="Ej. 12345", key="azure_id_padre_input"); st.session_state.azure_id_padre = id_padre.strip()
    tipo_origen = st.text_input("Tipo Origen Proyecto", value=safe_text(st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto"), key="azure_tipo_origen_input"); st.session_state.azure_tipo_origen_proyecto = tipo_origen.strip() or "Proyecto"
    suite_name = safe_text(target_suite.get("name"), publish_case_map[selected_publish_ids[0]].get("SUITE_NAME") if selected_publish_ids else st.session_state.get("qa_generation_suite_name", ""))
    duplicate_titles = []
    if target_suite and selected_publish_ids:
        try:
            existing = list_test_cases(target_plan_id, target_suite.get("id")); existing_titles = {re.sub(r"\s+", " ", safe_text(row.get("title"))).strip().casefold() for row in existing}
            for cp_id in selected_publish_ids:
                title = build_case_title(publish_case_map[cp_id], cp_id, suite_name=suite_name)
                if re.sub(r"\s+", " ", title).strip().casefold() in existing_titles: duplicate_titles.append(cp_id)
        except Exception as exc: st.warning(f"⚠️ No fue posible validar duplicados antes de la creación: {exc}")
    if duplicate_titles: st.error("🚫 Se detectaron títulos que ya existen en la Suite destino: " + ", ".join(duplicate_titles) + ". La creación queda bloqueada.")
    ready = bool(selected_publish_ids and target_plan and target_suite and not duplicate_titles and safe_text(st.session_state.get("azure_id_padre")) and safe_text(st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto"))
    if not safe_text(st.session_state.get("azure_id_padre")): st.warning("⚠️ Falta IDPadre. La creación queda bloqueada porque Azure lo exige.")
    st.markdown("### 2️⃣ Revisar y confirmar creación")
    st.dataframe(pd.DataFrame([{"CP": cp_id, "Título": build_case_title(publish_case_map[cp_id], cp_id, suite_name=suite_name), "Caso de Uso": safe_text(publish_case_map[cp_id].get("Related Use Case"), "Pendiente"), "Steps": len(safe_steps(publish_case_map[cp_id]))} for cp_id in selected_publish_ids]), width="stretch", hide_index=True)
    st.warning("⚠️ La sincronización modifica Azure DevOps: crea los Test Cases y los asocia a la Suite seleccionada.")
    confirm = st.checkbox("Confirmo que los CP, Test Plan, Suite, IDPadre y Tipo Origen Proyecto son correctos y autorizo la creación en Azure.", key="azure_publish_confirm")
    if st.button("🔄 Sincronizar con Azure DevOps", type="primary", disabled=not (ready and confirm), key="azure_publish_execute"):
        try:
            selected_cases = []
            for cp_id in selected_publish_ids:
                tc = dict(publish_case_map[cp_id]); tc["IDPadre"] = safe_text(st.session_state.get("azure_id_padre")); tc["Tipo Origen Proyecto"] = safe_text(st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto"); tc["SUITE_NAME"] = suite_name; selected_cases.append(tc)
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
