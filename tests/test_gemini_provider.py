import json
import pytest

import agente_qa.providers.gemini as gemini
from agente_qa.providers.gemini import validate_qa_structure


def test_validate_qa_structure_rejects_non_object_response():
    with pytest.raises(ValueError, match="no es un objeto JSON"):
        validate_qa_structure([])


def test_validate_qa_structure_requires_all_top_level_keys():
    data = {"USE_CASES": [], "TEST_CASES": []}
    with pytest.raises(ValueError, match="Falta la clave requerida: ALERTS"):
        validate_qa_structure(data)


def test_validate_qa_structure_rejects_empty_use_cases():
    data = {"USE_CASES": [], "TEST_CASES": [{"ID": "CP-AC-CAC-00001"}], "ALERTS": [], "COVERAGE": []}
    with pytest.raises(ValueError, match="Casos de Uso identificados"):
        validate_qa_structure(data)


def test_validate_qa_structure_rejects_empty_test_cases():
    data = {"USE_CASES": [{"ID": "CU-325", "Name": "Generar liquidación"}], "TEST_CASES": [], "ALERTS": [], "COVERAGE": []}
    with pytest.raises(ValueError, match="No se generaron casos de prueba"):
        validate_qa_structure(data)


def test_validate_qa_structure_normalizes_invalid_optional_collections():
    data = {
        "USE_CASES": [{
                    "ID": "CU-325",
                    "Name": "Generar liquidación",
                    "INTERFACE_STATUS": "UI_VERIFICABLE",
                    "INTERFACE_EVIDENCE": "Interfaz verificable según la fuente.",
                    "CP_ELIGIBLE": True,
                }],
        "TEST_CASES": [{"ID": "CP-AC-CAC-00001"}],
        "ALERTS": None,
        "COVERAGE": None,
    }
    result = validate_qa_structure(data)
    assert result["ALERTS"] == []
    assert result["COVERAGE"] == []


def test_generate_once_passes_temperature_to_gemini_config(monkeypatch):
    captured = {}

    class FakeConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeTypes:
        GenerateContentConfig = FakeConfig

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return "response"

    monkeypatch.setattr(gemini, "types", FakeTypes)
    gemini._generate_once(FakeModels(), "gemini-test", "prompt", temperature=0.35)

    assert captured["temperature"] == 0.35
    assert captured["request"]["model"] == "gemini-test"


def test_generate_qa_data_retries_internal_error(monkeypatch):
    result = {
        "USE_CASES": [{
                        "ID": "CU-325",
                        "Name": "Generar liquidación",
                        "INTERFACE_STATUS": "UI_VERIFICABLE",
                        "INTERFACE_EVIDENCE": "Interfaz verificable según la fuente.",
                        "CP_ELIGIBLE": True,
                    }],
        "TEST_CASES": [{"ID": "CP-AC-CAC-00001", "Title": "Generar liquidación", "Description": "OK", "Preconditions": "OK", "Steps": []}],
        "ALERTS": [],
        "COVERAGE": [],
    }
    calls = []
    responses = iter([RuntimeError("503 service unavailable"), type("Response", (), {"text": json.dumps(result)})()])

    def fake_generate_once(client, model, prompt, temperature):
        calls.append((model, temperature))
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value

    class FakeGenAI:
        @staticmethod
        def Client(**kwargs):
            return object()

    monkeypatch.setattr(gemini, "genai", FakeGenAI)
    monkeypatch.setattr(gemini, "_generate_once", fake_generate_once)
    monkeypatch.setattr(gemini, "validate_minimum_cu_coverage", lambda data: None)
    monkeypatch.setattr(gemini.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(gemini.st, "session_state", {})

    output = gemini.generate_qa_data("prompt", "source", "api-key", "gemini-test", temperature=0.25, max_retries=1, initial_wait=0)

    assert output == result
    assert calls == [("gemini-test", 0.25), ("gemini-test", 0.25)]


def test_merge_repaired_cases_preserves_original_and_adds_missing_cu():
    original_case = {
        "ID": "CP-AC-CAC-00001",
        "Title": "Generar liquidación",
        "Related Use Case": "CU-325",
    }
    original = {
        "USE_CASES": [],
        "TEST_CASES": [original_case],
        "ALERTS": [],
        "COVERAGE": [],
    }
    repair = {
        "TEST_CASES": [{
            "ID": "CP-AC-CAC-00002",
            "Title": "Modificar plantilla de cargue",
            "Related Use Case": "CU-353",
        }]
    }

    merged = gemini._merge_repaired_cases(
        original,
        repair,
        [{"id": "CU-353", "name": "Modificar plantilla de cargue"}],
    )

    assert len(merged["TEST_CASES"]) == 2
    assert merged["TEST_CASES"][0] == original_case
    assert merged["TEST_CASES"][1]["Related Use Case"] == "CU-353"
    assert len(original["TEST_CASES"]) == 1


def test_merge_repaired_cases_rejects_duplicate_id():
    original = {
        "TEST_CASES": [{
            "ID": "CP-AC-CAC-00001",
            "Title": "Generar liquidación",
            "Related Use Case": "CU-325",
        }]
    }
    repair = {
        "TEST_CASES": [{
            "ID": "CP-AC-CAC-00001",
            "Title": "Recuperar plantilla",
            "Related Use Case": "CU-353",
        }]
    }

    with pytest.raises(ValueError, match="ID de CP duplicado"):
        gemini._merge_repaired_cases(
            original,
            repair,
            [{"id": "CU-353", "name": "Modificar plantilla de cargue"}],
        )

def test_generate_qa_data_recovers_missing_cu(monkeypatch):
    use_cases = [
        {
            "ID": "CU-325",
            "Name": "Generar liquidación",
            "INTERFACE_STATUS": "UI_VERIFICABLE",
            "INTERFACE_EVIDENCE": "La fuente describe una interfaz.",
            "CP_ELIGIBLE": True,
        },
        {
            "ID": "CU-353",
            "Name": "Modificar plantilla de cargue del parque automotor",
            "INTERFACE_STATUS": "UI_VERIFICABLE",
            "INTERFACE_EVIDENCE": "La fuente describe una interfaz.",
            "CP_ELIGIBLE": True,
        },
    ]

    first_result = {
        "USE_CASES": use_cases,
        "TEST_CASES": [{
            "ID": "CP-AC-CAC-00001",
            "Title": "Generar liquidación",
            "Description": "Validar la liquidación.",
            "Preconditions": "Información requerida disponible.",
            "Related Use Case": "CU-325",
            "Steps": [],
        }],
        "ALERTS": [],
        "COVERAGE": [],
    }

    repair_result = {
        "USE_CASES": use_cases,
        "TEST_CASES": [{
            "ID": "CP-AC-CAC-00002",
            "Title": "Modificar plantilla de cargue",
            "Description": "Validar la modificación de la plantilla.",
            "Preconditions": "Información requerida disponible.",
            "Related Use Case": "CU-353",
            "Steps": [],
        }],
        "ALERTS": [],
        "COVERAGE": [],
    }

    responses = iter([
        json.dumps(first_result),
        json.dumps(repair_result),
    ])
    prompts = []

    def fake_generate_once(client, model, prompt, temperature):
        prompts.append(prompt)
        return type("Response", (), {"text": next(responses)})()

    class FakeGenAI:
        @staticmethod
        def Client(**kwargs):
            return object()

    monkeypatch.setattr(gemini, "genai", FakeGenAI)
    monkeypatch.setattr(gemini, "_generate_once", fake_generate_once)
    monkeypatch.setattr(gemini.st, "session_state", {})

    output = gemini.generate_qa_data(
        "prompt",
        "source",
        "api-key",
        "gemini-test",
        max_retries=0,
        initial_wait=0,
    )

    assert len(prompts) == 2
    assert "RECUPERACIÓN CONTROLADA DE COBERTURA" in prompts[1]
    assert len(output["TEST_CASES"]) == 2
    assert [
        tc["Related Use Case"] for tc in output["TEST_CASES"]
    ] == ["CU-325", "CU-353"]