import re

from agente_qa.utils import (
    build_azure_description,
    build_case_title,
    normalize_case_id,
    normalize_coverage,
    normalize_validation_method,
    safe_text,
)


def test_safe_text_supports_multiple_fallbacks():
    assert safe_text(None, "", "segundo respaldo") == "segundo respaldo"
    assert safe_text("", "primer respaldo", "segundo respaldo") == "primer respaldo"
    assert safe_text("valor", "respaldo", "otro") == "valor"


def test_build_azure_description_removes_trailing_pipe_and_preserves_sections():
    result = build_azure_description("Cotizadores Web |", "Cotizador Autos Colectivos |", "Validar cotización |", "La cotización queda cotizada |", "Usuario autenticado |", "CU-325 |")
    assert "Producto: Cotizadores Web" in result
    assert "Módulo: Cotizador Autos Colectivos" in result
    assert "Descripción: Validar cotización" in result
    assert "Resultado esperado de la prueba: La cotización queda cotizada" in result
    assert "Precondiciones: Usuario autenticado" in result
    assert "Caso de uso relacionado: CU-325" in result
    assert not re.search(r"\|\s*$", result)


def test_build_case_title_uses_au_and_first_three_suite_siglas():
    tc = {"Title": "Consultar cotización en estado Cotizado"}
    assert build_case_title(tc, "CP-AU-00001", suite_name="DRC") == "CP-AUDRC-00001 Consultar cotización en estado Cotizado"


def test_build_case_title_uses_ho_when_hogar_is_identified():
    tc = {"Title": "Validar cobertura de vivienda", "Module": "Hogar"}
    assert build_case_title(tc, "CP-AU-00001", suite_name="DRC", module="Hogar") == "CP-HODRC-00001 Validar cobertura de vivienda"


def test_normalize_case_id_keeps_supported_id():
    valid = "CP-AUDRC-00012"
    assert normalize_case_id(valid, "Cotizador Autos Colectivos", 99) == valid


def test_normalize_case_id_generates_legacy_default_format_when_no_suite_is_provided():
    generated = normalize_case_id("", "Cotizador Autos Colectivos", 7)
    assert generated == "CP-AU-00007"


def test_normalize_coverage_and_validation_method():
    assert normalize_coverage("completa") == "Completa"
    assert normalize_coverage("no cubierta") == "No cubierta"
    assert normalize_validation_method("interfaz de usuario") == "UI"
    assert normalize_validation_method("base de datos") == "BD"
