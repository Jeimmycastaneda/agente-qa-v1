"""Compatibilidad del conector Azure DevOps.

La implementación activa vive en ``azure_runtime.py``. Este módulo no mantiene
una segunda implementación HTTP: expone únicamente aliases compatibles para
código legado y pruebas existentes.
"""
from __future__ import annotations

from agente_qa.integrations.azure_runtime import (
    AzureDevOpsError,
    _azure_description_html,
    _azure_steps_xml,
    _az_config,
    _az_validate,
    _az_auth_header,
    add_test_cases_to_suite,
    create_azure_test_case_work_item,
    create_selected_cases_in_azure,
    get_test_case_detail,
    list_test_cases,
    list_test_plans,
    list_test_suites,
    test_connection,
)


# Aliases históricos: la lógica real permanece centralizada en azure_runtime.
AzureDevOpsApiError = AzureDevOpsError


def build_description_html(test_case: dict) -> str:
    """Alias compatible para el generador de Description de Azure."""
    return _azure_description_html(
        "Producto: " + str(test_case.get("Product", ""))
        + "\n\nMódulo: " + str(test_case.get("Module", ""))
        + "\n\nDescripción: " + str(test_case.get("Description", ""))
        + "\n\nResultado esperado de la prueba: " + str(test_case.get("Expected Result", ""))
        + "\n\nPrecondiciones: " + str(test_case.get("Preconditions", ""))
        + "\n\nCaso de uso relacionado: " + str(test_case.get("Related Use Case", ""))
    )


def build_steps_xml(test_case: dict) -> str:
    """Alias compatible para el XML de Steps de Azure."""
    return _azure_steps_xml(test_case.get("Steps") or [])


__all__ = [
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
