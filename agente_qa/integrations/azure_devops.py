"""Compatibilidad del conector Azure DevOps.

La implementación activa vive en ``azure_runtime.py``. Este módulo no mantiene
una segunda implementación HTTP: expone únicamente aliases compatibles para
código legado y pruebas existentes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from agente_qa.integrations.azure_runtime import (
    AzureDevOpsError,
    _azure_description_html,
    _azure_steps_xml,
    add_test_cases_to_suite,
    create_azure_test_case_work_item,
    create_selected_cases_in_azure,
    get_test_case_detail,
    list_test_cases,
    list_test_plans,
    list_test_suites,
    test_connection,
)

AzureDevOpsApiError = AzureDevOpsError


@dataclass(frozen=True)
class AzureDevOpsConfig:
    """Configuración legacy compatible con consumidores y pruebas previas."""

    enabled: bool = False
    organization: str = ""
    project: str = ""
    pat: str = ""

    @classmethod
    def from_env(cls):
        enabled = os.getenv("AZDO_ENABLED", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        return cls(
            enabled=enabled,
            organization=os.getenv("AZDO_ORGANIZATION", "").strip(),
            project=os.getenv("AZDO_PROJECT", "").strip(),
            pat=os.getenv("AZDO_PAT", "").strip(),
        )


def _clean_azure_text(value):
    """Normaliza texto heredado antes de enviarlo al formato de Azure."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("|", "")
        .replace("\\r\\n", " ")
        .replace("\\n", " ")
        .replace("\\r", " ")
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def build_description_html(test_case: dict) -> str:
    """Alias compatible para el generador de Description de Azure."""
    return _azure_description_html(
        "Producto: " + _clean_azure_text(test_case.get("Product", ""))
        + "\n\nMódulo: " + _clean_azure_text(test_case.get("Module", ""))
        + "\n\nDescripción: " + _clean_azure_text(test_case.get("Description", ""))
        + "\n\nResultado esperado de la prueba: " + _clean_azure_text(test_case.get("Expected Result", ""))
        + "\n\nPrecondiciones: " + _clean_azure_text(test_case.get("Preconditions", ""))
        + "\n\nCaso de uso relacionado: " + _clean_azure_text(test_case.get("Related Use Case", ""))
    )


def build_steps_xml(test_case: dict) -> str:
    """Alias compatible para el XML de Steps de Azure."""
    steps = []
    for step in test_case.get("Steps") or []:
        if not isinstance(step, dict):
            continue
        clean = dict(step)
        for key in ("Action", "action", "Step", "Expected", "expected", "Expected value"):
            if key in clean:
                clean[key] = _clean_azure_text(clean[key])
        steps.append(clean)
    return _azure_steps_xml(steps)


__all__ = [
    "AzureDevOpsConfig",
    "AzureDevOpsError",
    "AzureDevOpsApiError",
    "add_test_cases_to_suite",
    "build_description_html",
    "build_steps_xml",
    "create_azure_test_case_work_item",
    "create_selected_cases_in_azure",
    "get_test_case_detail",
    "list_test_cases",
    "list_test_plans",
    "list_test_suites",
    "test_connection",
]
