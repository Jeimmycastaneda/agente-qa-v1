"""Utilidades de texto, títulos, IDs y trazabilidad QA.

Código copiado desde main. mao-dev-branch solo aporta la estructura.
"""

import json
import re


def _ui_text(value, default=""):
    """Texto seguro para UI: nunca muestra el literal None."""
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def safe_text(value, default="", *fallbacks):
    """Convierte valores a texto y permite valores de respaldo."""
    candidates = (value, default, *fallbacks)
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, (dict, list)):
            text = json.dumps(candidate, ensure_ascii=False).strip()
        else:
            text = str(candidate).strip()
        if text:
            return text
    return ""


def safe_steps(tc):
    steps = tc.get("Steps", [])
    return steps if isinstance(steps, list) else []


def normalize_coverage(value):
    v = safe_text(value).strip().lower()
    allowed = {
        "completa": "Completa",
        "parcial": "Parcial",
        "no cubierta": "No cubierta",
        "fuera de alcance": "Fuera de alcance",
    }
    return allowed.get(v, safe_text(value, "Pendiente"))


def normalize_validation_method(value):
    v = safe_text(value).strip().lower()
    mapping = {
        "ui": "UI",
        "interfaz": "UI",
        "interfaz de usuario": "UI",
        "bd": "BD",
        "base de datos": "BD",
        "database": "BD",
        "api": "API",
        "web service": "API",
        "web services": "API",
        "mixta": "Mixta",
        "mixto": "Mixta",
    }
    return mapping.get(v, safe_text(value, "Pendiente"))


def _remove_trailing_pipe(value):
    """Elimina únicamente un pipe sobrante al final."""
    text = safe_text(value)
    return re.sub(r"\s*\|\s*$", "", text).rstrip()


_DESCRIPTION_LABELS = (
    "Producto",
    "Módulo",
    "Descripción",
    "Resultado esperado de la prueba",
    "Precondiciones",
    "Caso de uso relacionado",
)


def _extract_labeled_blocks(value):
    """Extrae bloques estructurados aunque las etiquetas estén en la misma línea."""
    text = _remove_trailing_pipe(value)
    if not text:
        return {}

    labels_pattern = "|".join(re.escape(label) for label in _DESCRIPTION_LABELS)
    pattern = rf"(?is)(?:^|\n|\r|\*\*)\s*(?P<label>{labels_pattern})\s*\**\s*:\s*"
    matches = list(re.finditer(pattern, text))
    if not matches:
        return {}

    blocks = {}
    for index, match in enumerate(matches):
        label = match.group("label")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        content = re.sub(r"\*\*\s*$", "", content).strip()
        blocks[label] = content
    return blocks


def _extract_description_block(value, label, next_labels):
    """Extrae el contenido de un bloque etiquetado, incluso si está en línea."""
    text = _remove_trailing_pipe(value)
    if not text:
        return ""

    labels = [label, *next_labels]
    labels_pattern = "|".join(re.escape(item) for item in labels)
    pattern = rf"(?is)(?:^|\n|\r|\*\*)\s*{re.escape(label)}\s*\**\s*:\s*(.*?)(?=(?:\n|\r|\*\*)?\s*(?:{labels_pattern})\s*\**\s*:|\Z)"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _clean_description_content(value):
    """Evita que Description contenga nuevamente los seis bloques estructurales."""
    text = _remove_trailing_pipe(value)
    if not text:
        return ""

    blocks = _extract_labeled_blocks(text)
    if blocks:
        # Si Gemini ya entregó la estructura completa, Description solo debe conservar
        # el contenido de su propio bloque. Los demás bloques se toman de sus campos.
        return blocks.get("Descripción", "").strip() or text

    # También elimina un encabezado aislado de Description para evitar duplicarlo.
    text = re.sub(r"(?is)^\s*\**Descripción\**\s*:\s*", "", text, count=1).strip()
    return text


def build_azure_description(product, module, description, expected, preconditions, related_use_case):
    """Construye una única estructura aprobada de Description para Azure."""
    raw_values = {
        "Producto": _remove_trailing_pipe(product),
        "Módulo": _remove_trailing_pipe(module),
        "Descripción": _remove_trailing_pipe(description),
        "Resultado esperado de la prueba": _remove_trailing_pipe(expected),
        "Precondiciones": _remove_trailing_pipe(preconditions),
        "Caso de uso relacionado": _remove_trailing_pipe(related_use_case),
    }

    # Si cualquiera de los campos trae la estructura completa generada por Gemini,
    # descomponerla una sola vez y usar sus bloques como fuente de respaldo.
    combined_blocks = {}
    for value in raw_values.values():
        blocks = _extract_labeled_blocks(value)
        if blocks:
            for key, content in blocks.items():
                if content and not combined_blocks.get(key):
                    combined_blocks[key] = content

    values = {}
    for label, value in raw_values.items():
        if combined_blocks.get(label):
            # El bloque estructurado tiene prioridad para evitar que el mismo contenido
            # vuelva a aparecer dentro de otro bloque.
            values[label] = combined_blocks[label]
        else:
            values[label] = value

    # Si Description contiene estructura, tomar únicamente su bloque Descripción.
    description_blocks = _extract_labeled_blocks(values["Descripción"])
    if description_blocks:
        values["Descripción"] = description_blocks.get("Descripción", "").strip()

    # Limpiar etiquetas estructurales residuales de cada campo individual.
    expected_blocks = _extract_labeled_blocks(values["Resultado esperado de la prueba"])
    if expected_blocks:
        values["Resultado esperado de la prueba"] = expected_blocks.get("Resultado esperado de la prueba", "").strip()

    precondition_blocks = _extract_labeled_blocks(values["Precondiciones"])
    if precondition_blocks:
        values["Precondiciones"] = precondition_blocks.get("Precondiciones", "").strip()

    related_blocks = _extract_labeled_blocks(values["Caso de uso relacionado"])
    if related_blocks:
        values["Caso de uso relacionado"] = related_blocks.get("Caso de uso relacionado", "").strip()

    product_blocks = _extract_labeled_blocks(values["Producto"])
    if product_blocks:
        values["Producto"] = product_blocks.get("Producto", "").strip()

    module_blocks = _extract_labeled_blocks(values["Módulo"])
    if module_blocks:
        values["Módulo"] = module_blocks.get("Módulo", "").strip()

    return (
        f"Producto: {values['Producto'] or 'Pendiente'}\n\n"
        f"Módulo: {values['Módulo'] or 'Pendiente'}\n\n"
        f"Descripción: {values['Descripción'] or 'Pendiente'}\n\n"
        f"Resultado esperado de la prueba: {values['Resultado esperado de la prueba'] or 'Pendiente'}\n\n"
        f"Precondiciones: {values['Precondiciones'] or 'Pendiente'}\n\n"
        f"Caso de uso relacionado: {values['Caso de uso relacionado'] or 'Pendiente'}"
    )


def format_description_for_azure(description):
    """Formatea Description para Azure DevOps sin cambiar su contenido funcional."""
    text = safe_text(description).replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return ""

    text = re.sub(r"[ \t]+", " ", text)
    labels = [
        "Producto:",
        "Módulo:",
        "Descripción:",
        "Resultado esperado de la prueba:",
        "Precondiciones:",
        "Caso de uso relacionado:",
    ]
    for label in labels:
        text = re.sub(rf"\s*{re.escape(label)}\s*", f"\n{label} ", text, count=1)

    text = re.sub(r"(?m)^\s*[•●▪◦]\s*", "- ", text)
    text = re.sub(r"(?m)^\s*[o]\s+", "- ", text)
    text = re.sub(r"\n\s*[-–—]\s*", "\n- ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    for label in labels:
        text = re.sub(rf"(?m)^{re.escape(label)}\s*", f"**{label}** ", text)
    for label in labels[1:]:
        text = re.sub(rf"\n\*\*{re.escape(label)}\*\*", f"\n\n**{label}**", text)
    text = re.sub(r"^\*\*Producto:\*\*", "**Producto:**", text)
    return text.strip()


def module_token(module, title="", scenario=""):
    raw = safe_text(module) or safe_text(title) or safe_text(scenario) or "GENERAL"
    raw = re.sub(r"[^A-Za-z0-9]+", " ", raw).strip().upper()
    words = raw.split()
    if not words:
        return "GENERAL"
    if len(words) == 1:
        return words[0][:12]
    return "".join(w[0] for w in words)[:8]


def build_case_title(tc, case_id):
    """Garantiza que Title sea funcional y no solamente el ID del CP."""
    raw_title = safe_text(tc.get("Title"))
    normalized_title = re.sub(r"\s+", " ", raw_title).strip()
    if (
        not normalized_title
        or normalized_title.upper() == case_id.upper()
        or re.fullmatch(r"CP-[A-Z0-9_-]+-\d{5}", normalized_title.upper())
    ):
        candidates = [
            safe_text(tc.get("Scenario")),
            safe_text(tc.get("Description")),
            safe_text(tc.get("Related Use Case")),
        ]
        for candidate in candidates:
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if candidate and candidate.upper() != case_id.upper():
                normalized_title = candidate
                break
    if not normalized_title:
        normalized_title = f"Caso de prueba {case_id}"
    return normalized_title


def normalize_case_id(raw_id, module, index, prefix="CP-AC-"):
    candidate = safe_text(raw_id)
    if re.fullmatch(r"CP-AC-[A-Za-z0-9_-]+-\d{5}", candidate):
        return candidate
    return f"{prefix}{module_token(module)}-{index:05d}"


def find_coverage(data, tc):
    tc_id = safe_text(tc.get("ID"))
    for row in data.get("COVERAGE", []) if isinstance(data.get("COVERAGE", []), list) else []:
        if safe_text(row.get("Test Case")) == tc_id:
            return row
    return {}


def aggregate_case_alerts(data, tc):
    parts = []
    case_alerts = tc.get("Alerts", [])
    if isinstance(case_alerts, list):
        for alert in case_alerts:
            text = safe_text(alert.get("Alert"))
            reason = safe_text(alert.get("Reason"))
            validation = safe_text(alert.get("Validation Required"))
            if text:
                if reason:
                    text += f": {reason}"
                if validation:
                    text += f" | Validación: {validation}"
                parts.append(text)
    return " | ".join(parts) if parts else "Sin Alertas"
