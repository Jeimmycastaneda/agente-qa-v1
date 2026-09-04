"""Componentes de presentación de cobertura QA."""
from __future__ import annotations

import streamlit as st


def render_coverage(calculate_cu_coverage, render_cu_coverage, result):
    """Calcula y presenta cobertura sin modificar los datos funcionales."""
    metrics = calculate_cu_coverage(result.get("TEST_CASES", []), result.get("USE_CASES", []))
    render_cu_coverage(metrics)
    return metrics


def coverage_gate_or_stop(calculate_cu_coverage, render_cu_coverage, result):
    """Bloquea la exportación cuando algún CU no tiene CP."""
    metrics = render_coverage(calculate_cu_coverage, render_cu_coverage, result)
    if not metrics["valid"]:
        st.error("🚫 EXPORTACIÓN BLOQUEADA: cada Caso de Uso debe tener mínimo un Caso de Prueba.")
        st.stop()
    return metrics
