import pytest

from agente_qa.validation import calculate_cu_coverage, validate_minimum_cu_coverage


def test_calculate_cu_coverage_requires_at_least_one_cp_per_cu():
    cases = [
        {"ID": "CP-AC-CAC-00001", "Related Use Case": "CU-325"},
    ]
    use_cases = [
        {"ID": "CU-325", "Name": "Generar liquidación"},
        {"ID": "CU-363", "Name": "Recotizar"},
    ]

    metrics = calculate_cu_coverage(cases, use_cases)

    assert metrics["total_cu"] == 2
    assert metrics["covered_cu"] == 1
    assert metrics["missing_cu"][0]["id"] == "CU-363"
    assert metrics["valid"] is False


def test_calculate_cu_coverage_rejects_cp_related_to_more_than_one_cu():
    cases = [
        {"ID": "CP-AC-CAC-00001", "Related Use Case": "CU-325; CU-363"},
    ]
    use_cases = ["CU-325", "CU-363"]

    metrics = calculate_cu_coverage(cases, use_cases)

    assert metrics["cp_multiple_cu"] == ["CP-AC-CAC-00001"]
    assert metrics["valid"] is False


def test_validate_minimum_cu_coverage_accepts_complete_coverage():
    data = {
        "TEST_CASES": [
            {"ID": "CP-AC-CAC-00001", "Related Use Case": "CU-325"},
            {"ID": "CP-AC-CAC-00002", "Related Use Case": "CU-363"},
        ],
        "USE_CASES": [
            {"ID": "CU-325", "Name": "Generar liquidación"},
            {"ID": "CU-363", "Name": "Recotizar"},
        ],
    }

    metrics = validate_minimum_cu_coverage(data)

    assert metrics["valid"] is True
    assert metrics["percentage"] == 100.0


def test_validate_minimum_cu_coverage_blocks_missing_cu():
    data = {
        "TEST_CASES": [
            {"ID": "CP-AC-CAC-00001", "Related Use Case": "CU-325"},
        ],
        "USE_CASES": [
            {"ID": "CU-325", "Name": "Generar liquidación"},
            {"ID": "CU-363", "Name": "Recotizar"},
        ],
    }

    with pytest.raises(ValueError, match="COBERTURA INCOMPLETA"):
        validate_minimum_cu_coverage(data)
