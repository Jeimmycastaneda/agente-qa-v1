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
        "USE_CASES": [{"ID": "CU-325", "Name": "Generar liquidación"}],
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
        "USE_CASES": [{"ID": "CU-325", "Name": "Generar liquidación"}],
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
