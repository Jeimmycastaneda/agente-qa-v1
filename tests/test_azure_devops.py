import xml.etree.ElementTree as ET

from agente_qa.integrations.azure_devops import (
    AzureDevOpsConfig,
    build_description_html,
    build_steps_xml,
)
import agente_qa.integrations.azure_runtime as azure_runtime


def test_azure_config_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AZDO_ENABLED", raising=False)
    monkeypatch.delenv("AZDO_ORGANIZATION", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    config = AzureDevOpsConfig.from_env()

    assert config.enabled is False


def test_runtime_azure_config_uses_central_secret_resolver(monkeypatch):
    values = {
        "AZURE_DEVOPS_ORG": "org-demo",
        "AZURE_DEVOPS_PROJECT": "proyecto-demo",
        "AZURE_DEVOPS_PAT": "pat-demo",
    }
    requested = []

    def fake_resolve_secret(name):
        requested.append(name)
        return values[name]

    monkeypatch.setattr(azure_runtime, "resolve_secret", fake_resolve_secret)

    config = azure_runtime._az_config()

    assert config == {
        "org": "org-demo",
        "project": "proyecto-demo",
        "pat": "pat-demo",
    }
    assert requested == [
        "AZURE_DEVOPS_ORG",
        "AZURE_DEVOPS_PROJECT",
        "AZURE_DEVOPS_PAT",
    ]


def test_build_description_html_preserves_sections_and_removes_pipes():
    test_case = {
        "Product": "Cotizadores Web |",
        "Module": "Cotizador Autos Colectivos",
        "Description": "Validar generación de liquidación",
        "Expected Result": "La información se presenta correctamente",
        "Preconditions": "Usuario autenticado",
        "Related Use Case": "CU-325",
    }

    result = build_description_html(test_case)

    assert "<strong>Producto:</strong>" in result
    assert "<strong>Módulo:</strong>" in result
    assert "<strong>Descripción:</strong>" in result
    assert "CU-325" in result
    assert "|" not in result
    assert "**" not in result


def test_build_steps_xml_has_action_and_expected_without_pipes_or_literal_newlines():
    test_case = {
        "Steps": [
            {
                "Step #": 1,
                "Action": "Ingresar al módulo | Autos Colectivos",
                "Expected": "Se muestra el formulario\\nprincipal",
            },
            {
                "Step #": 2,
                "Action": "Consultar cotización",
                "Expected": "Se muestran los datos",
            },
        ]
    }

    result = build_steps_xml(test_case)
    root = ET.fromstring(result)

    steps = root.findall("step")
    assert len(steps) == 2
    assert root.attrib["last"] == "2"
    assert "|" not in result
    assert "\\n" not in result
    assert steps[0].findall("parameterizedString")[0].text == "Ingresar al módulo  Autos Colectivos"
    assert "principal" in (steps[0].findall("parameterizedString")[1].text or "")
