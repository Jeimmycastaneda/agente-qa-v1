"""Sección de administración de Test Plans y Test Suites de Azure DevOps."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def _text(value, default=""):
    if value is None:
        return default
    result = str(value).strip()
    return result or default


def render_azure_plan_suite_admin(
    *,
    list_test_plans,
    list_test_suites,
    create_test_plan,
    create_test_suite,
):
    """Renderiza una sección separada para crear planes y suites con confirmación."""
    st.divider()
    st.header("🗂️ Administración de Test Plans y Test Suites")
    st.caption(
        "Gestiona recursos únicamente en la organización y el proyecto configurados "
        "en Azure DevOps. Las escrituras requieren confirmación y se bloquean si "
        "se detecta un nombre duplicado."
    )

    if "azure_admin_plans" not in st.session_state:
        st.session_state.azure_admin_plans = []
    if "azure_admin_suites" not in st.session_state:
        st.session_state.azure_admin_suites = []

    with st.expander("➕ Crear Test Plan", expanded=False):
        st.write(
            "El Test Plan se creará en el proyecto configurado. El Area Path y el "
            "Iteration Path deben existir en Azure DevOps."
        )
        with st.form("azure_admin_create_plan_form"):
            plan_name = st.text_input(
                "Nombre del Test Plan",
                placeholder="Ej. Colectivos Autos - Pruebas funcionales 2026",
            )
            area_path = st.text_input(
                "Area Path",
                value="COTIZADORES WEB\\DESARROLLO",
            )
            iteration_path = st.text_input(
                "Iteration Path",
                value="COTIZADORES WEB",
            )
            plan_description = st.text_area(
                "Descripción (opcional)",
                placeholder="Objetivo y alcance del plan",
            )
            confirm_plan = st.checkbox(
                "Confirmo que deseo crear este Test Plan en Azure DevOps.",
                key="azure_admin_confirm_create_plan",
            )
            submit_plan = st.form_submit_button("Crear Test Plan")

        if submit_plan:
            if not confirm_plan:
                st.error("Marca la confirmación explícita antes de crear el Test Plan.")
            elif not plan_name.strip() or not area_path.strip() or not iteration_path.strip():
                st.error("Nombre, Area Path e Iteration Path son obligatorios.")
            else:
                try:
                    with st.spinner("Validando duplicados y creando Test Plan..."):
                        created_plan = create_test_plan(
                            plan_name, area_path, iteration_path, plan_description
                        )
                    st.session_state.azure_admin_last_plan = created_plan
                    st.success(
                        f"Test Plan creado: {created_plan['name']} "
                        f"(ID {created_plan['id']})."
                    )
                    st.info(created_plan.get("message", "Creación completada."))
                    try:
                        plans_result = list_test_plans(limit=100)
                        st.session_state.azure_admin_plans = plans_result.get("plans", [])
                    except Exception as refresh_error:
                        st.warning(
                            "El Test Plan se creó, pero no se pudo actualizar el listado: "
                            f"{refresh_error}"
                        )
                except Exception as exc:
                    st.error(f"No se pudo crear el Test Plan: {exc}")

    st.markdown("### Test Plans disponibles")
    col_refresh, col_count = st.columns([1, 2])
    with col_refresh:
        refresh_plans = st.button(
            "🔄 Consultar Test Plans",
            key="azure_admin_refresh_plans",
        )
    with col_count:
        st.caption(
            "La consulta es de solo lectura. Usa la lista actualizada para elegir "
            "el plan padre de la Suite."
        )
    if refresh_plans:
        try:
            with st.spinner("Consultando Test Plans del proyecto configurado..."):
                plans_result = list_test_plans(limit=100)
            st.session_state.azure_admin_plans = plans_result.get("plans", [])
            st.success(
                f"Se consultaron {len(st.session_state.azure_admin_plans)} Test Plan(s)."
            )
        except Exception as exc:
            st.error(f"No se pudieron consultar los Test Plans: {exc}")

    plans = st.session_state.get("azure_admin_plans", []) or []
    if plans:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": plan.get("id"),
                        "Test Plan": plan.get("name"),
                        "Estado": plan.get("state"),
                        "Area Path": plan.get("area_path"),
                        "Iteration Path": plan.get("iteration"),
                    }
                    for plan in plans
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Consulta los Test Plans para habilitar la creación de una Suite.")

    with st.expander("➕ Crear Test Suite", expanded=False):
        if not plans:
            st.warning("Primero consulta los Test Plans o crea uno nuevo.")
        else:
            plan_options = [
                f"{plan.get('id')} — {_text(plan.get('name'), 'Test Plan sin nombre')}"
                for plan in plans
                if _text(plan.get("id"))
            ]
            plan_by_label = {
                f"{plan.get('id')} — {_text(plan.get('name'), 'Test Plan sin nombre')}": plan
                for plan in plans
                if _text(plan.get("id"))
            }
            with st.form("azure_admin_create_suite_form"):
                selected_label = st.selectbox(
                    "Test Plan padre",
                    plan_options,
                    key="azure_admin_suite_plan",
                )
                suite_name = st.text_input(
                    "Nombre de la Test Suite",
                    placeholder="Ej. Validaciones funcionales",
                )
                confirm_suite = st.checkbox(
                    "Confirmo que deseo crear esta Test Suite dentro del Test Plan seleccionado.",
                    key="azure_admin_confirm_create_suite",
                )
                submit_suite = st.form_submit_button("Crear Test Suite")

            if submit_suite:
                if not confirm_suite:
                    st.error("Marca la confirmación explícita antes de crear la Suite.")
                elif not suite_name.strip():
                    st.error("El nombre de la Test Suite es obligatorio.")
                elif selected_label not in plan_by_label:
                    st.error("Selecciona un Test Plan válido.")
                else:
                    selected_plan = plan_by_label[selected_label]
                    try:
                        with st.spinner("Validando duplicados y creando Test Suite..."):
                            created_suite = create_test_suite(
                                selected_plan.get("id"), suite_name
                            )
                        st.session_state.azure_admin_last_suite = created_suite
                        st.success(
                            f"Test Suite creada: {created_suite['name']} "
                            f"(ID {created_suite['id']}) dentro del Test Plan "
                            f"{selected_plan.get('name')}."
                        )
                        st.info(created_suite.get("message", "Creación completada."))
                        try:
                            st.session_state.azure_admin_suites = list_test_suites(
                                selected_plan.get("id")
                            )
                        except Exception as refresh_error:
                            st.warning(
                                "La Suite se creó, pero no se pudo actualizar el listado: "
                                f"{refresh_error}"
                            )
                    except Exception as exc:
                        st.error(f"No se pudo crear la Test Suite: {exc}")

            last_suite = st.session_state.get("azure_admin_last_suite")
            if last_suite:
                st.caption(
                    f"Última Suite creada: {last_suite.get('name')} "
                    f"(ID {last_suite.get('id')}; Plan {last_suite.get('plan_id')})."
                )
