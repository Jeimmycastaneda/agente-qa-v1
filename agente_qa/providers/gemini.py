"""Proveedor Gemini y generación estructurada de datos QA.

La fuente funcional de reglas de generación es únicamente prompts/prompt_qa.txt.
Este módulo contiene solo integración con Gemini, esquema técnico y validación.
"""

import json
import os
import re
import time
import streamlit as st

from agente_qa.utils import safe_text
from agente_qa.validation import (
    calculate_cu_coverage,
    validate_minimum_cu_coverage,
)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

MODEL = "gemini-3.6-flash"
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

SCHEMA = {
    "type": "object",
    "properties": {
        "USE_CASES": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "ID": {"type": "string"}, "Name": {"type": "string"},
                "INTERFACE_STATUS": {"type": "string", "enum": ["UI_VERIFICABLE", "TECNICO_VERIFICABLE", "NO_UI", "AMBIGUA"]},
                "INTERFACE_EVIDENCE": {"type": "string"},
                "CP_ELIGIBLE": {"type": "boolean"}
            }, "required": ["ID", "Name", "INTERFACE_STATUS", "INTERFACE_EVIDENCE", "CP_ELIGIBLE"]}
        },
        "TEST_CASES": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "ID": {"type": "string"}, "Title": {"type": "string"},
                "Description": {"type": "string"}, "Expected Result": {"type": "string"},
                "Preconditions": {"type": "string"}, "Product": {"type": "string"},
                "Module": {"type": "string"}, "Related Use Case": {"type": "string"},
                "Criterion": {"type": "string"}, "Scenario": {"type": "string"},
                "Scenario Type": {"type": "string"}, "Effort": {"type": "string"},
                "Coverage": {"type": "string"}, "Validation Method": {"type": "string"},
                "Steps": {"type": "array", "items": {"type": "object", "properties": {
                    "Step #": {"type": "integer"}, "Action": {"type": "string"},
                    "Expected value": {"type": "string"}
                }, "required": ["Step #", "Action", "Expected value"]}},
                "Alerts": {"type": "array", "items": {"type": "object", "properties": {
                    "Alert": {"type": "string"}, "Reason": {"type": "string"},
                    "Validation Required": {"type": "string"}
                }, "required": ["Alert", "Reason", "Validation Required"]}}
            }, "required": ["ID", "Title", "Description", "Preconditions", "Steps"]}
        },
        "ALERTS": {"type": "array", "items": {"type": "object", "properties": {
            "Alert": {"type": "string"}, "Reason": {"type": "string"},
            "Validation Required": {"type": "string"}
        }, "required": ["Alert", "Reason", "Validation Required"]}},
        "COVERAGE": {"type": "array", "items": {"type": "object", "properties": {
            "Requirement / Use Case": {"type": "string"}, "Criterion": {"type": "string"},
            "Scenario": {"type": "string"}, "Test Case": {"type": "string"},
            "Validation Method": {"type": "string"}, "Coverage": {"type": "string"},
            "Alerts": {"type": "string"}
        }, "required": ["Requirement / Use Case", "Criterion", "Scenario", "Test Case"]}}
    },
    "required": ["USE_CASES", "TEST_CASES", "ALERTS", "COVERAGE"]
}


def load_prompt():
    path = os.path.join("prompts", "prompt_qa.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(
            "No se encontró la única fuente de reglas QA: prompts/prompt_qa.txt"
        )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        raise ValueError("La única fuente de reglas QA está vacía: prompts/prompt_qa.txt")
    return content


@st.cache_data(ttl=3600)
def get_valid_models(api_key):
    if genai is None:
        return FALLBACK_MODELS
    try:
        client = genai.Client(api_key=api_key)
        names = []
        for model in client.models.list():
            name = model.name.split("/")[-1]
            if "gemini" in name.lower():
                names.append(name)
        return sorted(set(names)) or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS


def validate_qa_structure(data):
    if not isinstance(data, dict):
        raise ValueError("La respuesta de Gemini no es un objeto JSON.")
    for key in ("USE_CASES", "TEST_CASES", "ALERTS", "COVERAGE"):
        if key not in data:
            raise ValueError(f"Falta la clave requerida: {key}")
    if not isinstance(data["USE_CASES"], list) or not data["USE_CASES"]:
        raise ValueError("Gemini no devolvió los Casos de Uso identificados.")
    if not isinstance(data["TEST_CASES"], list) or not data["TEST_CASES"]:
        raise ValueError("No se generaron casos de prueba.")
    if not isinstance(data["ALERTS"], list):
        data["ALERTS"] = []
    if not isinstance(data["COVERAGE"], list):
        data["COVERAGE"] = []

    allowed_status = {"UI_VERIFICABLE", "TECNICO_VERIFICABLE", "NO_UI", "AMBIGUA"}
    for cu in data["USE_CASES"]:
        status = cu.get("INTERFACE_STATUS")
        if status not in allowed_status:
            raise ValueError(f"CU {cu.get('ID', '')}: INTERFACE_STATUS inválido: {status}")
        eligible = cu.get("CP_ELIGIBLE")
        expected = status in {"UI_VERIFICABLE", "TECNICO_VERIFICABLE"}
        if eligible is not expected:
            raise ValueError(
                f"CU {cu.get('ID', '')}: CP_ELIGIBLE no coincide con INTERFACE_STATUS."
            )
        if not isinstance(cu.get("INTERFACE_EVIDENCE"), str):
            raise ValueError(f"CU {cu.get('ID', '')}: INTERFACE_EVIDENCE debe ser texto.")

    return data


def _is_gemini_3x(model_name):
    return safe_text(model_name).lower().startswith(("gemini-3.", "gemini-3"))


def _extract_error_detail(exc):
    return str(exc)[:1800]


def _set_session_state(key, value):
    """Actualiza Streamlit SessionState y permite mappings simples en pruebas."""
    try:
        st.session_state[key] = value
    except Exception:
        setattr(st.session_state, key, value)


def _generate_once(client, model_name, full_prompt, temperature=0.1):
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SCHEMA,
        temperature=temperature,
        max_output_tokens=32768,
    )
    models = getattr(client, "models", client)
    return models.generate_content(model=model_name, contents=full_prompt, config=config)


def _parse_gemini_json(response_text, model_name):
    """Convierte la respuesta de Gemini a JSON sin alterar su contenido."""
    response_text = (response_text or "").strip()

    if not response_text:
        raise RuntimeError(
            f"{model_name}: Gemini devolvió una respuesta vacía."
        )

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```",
            response_text,
        )
        if not match:
            raise RuntimeError(
                f"{model_name}: la respuesta no es JSON válido. "
                f"Respuesta: {response_text[:1200]}"
            )
        return json.loads(match.group(1))


def _build_missing_cu_repair_prompt(full_prompt, data, missing_cu):
    """Solicita únicamente los CP faltantes, sin regenerar los existentes."""
    missing_text = "\n".join(
        f'- {cu["id"]}: {cu["name"]}'
        for cu in missing_cu
    )

    existing_ids = [
        str(tc.get("ID", "")).strip()
        for tc in data.get("TEST_CASES", [])
        if str(tc.get("ID", "")).strip()
    ]

    existing_titles = [
        str(tc.get("Title", "")).strip()
        for tc in data.get("TEST_CASES", [])
        if str(tc.get("Title", "")).strip()
    ]

    return (
        full_prompt
        + "\n\n=== RECUPERACIÓN CONTROLADA DE COBERTURA ===\n"
        + "La generación inicial dejó estos CU elegibles sin CP:\n"
        + missing_text
        + "\nGenera exclusivamente los casos de prueba que faltan para esos CU. "
        + "No regeneres, modifiques ni repitas los casos existentes. "
        + "Utiliza únicamente información explícita de la fuente original. "
        + "Cada CP debe relacionarse con exactamente un CU objetivo mediante "
        + "su identificador exacto en Related Use Case. "
        + "No generes CP para otros CU ni inventes comportamientos. "
        + "Devuelve el JSON completo con las claves USE_CASES, TEST_CASES, "
        + "ALERTS y COVERAGE. Incluye la clasificación completa de los CU "
        + "y únicamente los CP nuevos en TEST_CASES. "
        + "\nIDs de CP existentes (no repetir): "
        + json.dumps(existing_ids, ensure_ascii=False)
        + "\nTítulos existentes (no repetir): "
        + json.dumps(existing_titles, ensure_ascii=False)
    )



def _merge_repaired_cases(original, repair, missing_cu):
    """Agrega CP faltantes sin modificar ni duplicar los originales."""
    missing_ids = {
        str(cu["id"]).strip().upper().replace("_", "-").replace(" ", "-")
        for cu in missing_cu
    }

    existing_cases = list(original.get("TEST_CASES", []))
    existing_ids = {
        str(tc.get("ID", "")).strip().casefold()
        for tc in existing_cases
        if str(tc.get("ID", "")).strip()
    }
    existing_titles = {
        " ".join(str(tc.get("Title", "")).split()).casefold()
        for tc in existing_cases
        if str(tc.get("Title", "")).strip()
    }

    additions = []
    for tc in repair.get("TEST_CASES", []):
        relation = str(
            tc.get("Related Use Case")
            or tc.get("related_use_case")
            or tc.get("use_case")
            or tc.get("Requirement / Use Case")
            or tc.get("Caso de uso relacionado")
            or ""
        )

        found_ids = {
            match.upper().replace("_", "-").replace(" ", "-")
            for match in re.findall(
                r"\bCU[-_ ]?\d+\b",
                relation,
                flags=re.IGNORECASE,
            )
        }

        if len(found_ids) != 1 or not found_ids.issubset(missing_ids):
            raise ValueError(
                "Recuperación rechazada: un CP nuevo no está asociado "
                "exclusivamente a un CU faltante."
            )

        case_id = str(tc.get("ID", "")).strip().casefold()
        title = " ".join(str(tc.get("Title", "")).split()).casefold()

        if case_id and case_id in existing_ids:
            raise ValueError(
                f"Recuperación rechazada: ID de CP duplicado ({tc.get('ID')})."
            )
        if title and title in existing_titles:
            raise ValueError(
                f"Recuperación rechazada: título de CP duplicado ({tc.get('Title')})."
            )

        if case_id:
            existing_ids.add(case_id)
        if title:
            existing_titles.add(title)
        additions.append(dict(tc))

    if not additions:
        raise ValueError(
            "Recuperación incompleta: Gemini no devolvió CP nuevos."
        )

    merged = dict(original)
    merged["TEST_CASES"] = existing_cases + additions
    return merged



def generate_qa_data(prompt_text, source_content, api_key, model_name, temperature=0.1, max_retries=2, initial_wait=10):
    if genai is None:
        raise RuntimeError("No está instalada la librería google-genai.")
    if not api_key:
        raise ValueError("API Key no configurada.")
    if not source_content.strip():
        raise ValueError("Fuente de información vacía.")

    max_source_chars = 120000
    if len(source_content) > max_source_chars:
        source_content = source_content[:max_source_chars] + "\n...[DOCUMENTO EXCEDE EL LÍMITE DE SEGURIDAD]"

    full_prompt = (
        prompt_text
        + "\n\n==================== FUENTE PROPORCIONADA POR EL USUARIO ====================\n"
        + source_content
    )

    client = genai.Client(api_key=api_key)
    candidates = []
    for candidate in [model_name] + FALLBACK_MODELS:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    errors = []
    for candidate in candidates:
        for attempt in range(max_retries + 1):
            try:


                response = _generate_once(client, candidate, full_prompt, temperature)
                data = _parse_gemini_json(response.text, candidate)
                validated = validate_qa_structure(data)

                try:
                    validate_minimum_cu_coverage(validated)
                except ValueError:
                    metrics = calculate_cu_coverage(
                        validated.get("TEST_CASES", []),
                        validated.get("USE_CASES", []),
                    )

                    # Solo intentar reparar cuando el único problema sea la falta de CP.
                    has_other_coverage_errors = any(
                        metrics.get(key)
                        for key in (
                            "cp_without_cu",
                            "cp_multiple_cu",
                            "cp_non_eligible_cu",
                        )
                    )

                    if not metrics["missing_cu"] or has_other_coverage_errors:
                        raise

                    repair_prompt = _build_missing_cu_repair_prompt(
                        full_prompt,
                        validated,
                        metrics["missing_cu"],
                    )

                    repair_response = _generate_once(
                        client,
                        candidate,
                        repair_prompt,
                        temperature,
                    )
                    repair_data = validate_qa_structure(
                        _parse_gemini_json(repair_response.text, candidate)
                    )

                    validated = _merge_repaired_cases(
                        validated,
                        repair_data,
                        metrics["missing_cu"],
                    )

                    # La recuperación solo se acepta si la cobertura queda completa.
                    validate_minimum_cu_coverage(validated)

                _set_session_state("quota_exceeded", False)
                _set_session_state("retry_count", 0)
                return validated



            except Exception as exc:
                detail = _extract_error_detail(exc)
                errors.append(f"{candidate} / intento {attempt + 1}: {detail}")
                error_text = detail.lower()
                is_quota = "429" in detail or "quota" in error_text or "rate limit" in error_text or "resource exhausted" in error_text
                is_retryable_internal = "500" in detail or "internal" in error_text or "503" in error_text or "unavailable" in error_text or "deadline" in error_text or "timeout" in error_text
                if is_quota:
                    _set_session_state("quota_exceeded", True)
                    _set_session_state("retry_count", attempt + 1)
                    break
                is_bad_request = "400" in detail or "invalid argument" in error_text or "invalid_argument" in error_text or "unsupported" in error_text
                if attempt < max_retries and is_retryable_internal:
                    time.sleep(initial_wait * (attempt + 1))
                    continue
                if is_bad_request or is_retryable_internal:
                    break
                break

    raise RuntimeError(
        "Gemini no pudo completar la generación con los modelos probados.\n\nDetalle técnico: "
        + "\n".join(errors[-8:])
    )
