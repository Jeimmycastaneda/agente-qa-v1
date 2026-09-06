import pytest

from agente_qa.providers.gemini import validate_qa_structure


def test_validate_qa_structure_rejects_non_object_response():
    with pytest.raises(ValueError, match="no es un objeto JSON"):
        validate_qa_structure([])


def test_validate_qa_structure_requires_all_top_level_keys():
    data = {
        "USE_CASES": [],
        "TEST_CASES": [],
    }

    with pytest.raises(ValueError, match="Falta la clave requerida: ALERTS"):
        validate_qa_structure(data)


def test_validate_qa_structure_rejects_empty_use_cases():
    data = {
        "USE_CASES": [],
        "TEST_CASES": [{"ID": "CP-AC-CAC-00001"}],
        "ALERTS": [],
        "COVERAGE": [],
    }

    with pytest.raises(ValueError, match="Casos de Uso identificados"):
        validate_qa_structure(data)


def test_validate_qa_structure_rejects_empty_test_cases():
    data = {
        "USE_CASES": [{"ID": "CU-325", "Name": "Generar liquidación"}],
        "TEST_CASES": [],
        "ALERTS": [],
        "COVERAGE": [],
    }

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
