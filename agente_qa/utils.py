"""Utilidades de texto, títulos, IDs y trazabilidad QA.

Código funcional copiado desde main. mao-dev-branch solo aporta la estructura.
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
    pattern = rf"(?is)(?:^|\s|\*\*)\s*(?P<label>{labels_pattern})\s*\**\s*:\s*"
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
    pattern = rf"(?is)(?:^|\s|\*\*)\s*{re.escape(label)}\s*\**\s*:\s*(.*?)(?=(?:\s|\*\*)\s*(?:{labels_pattern})\s*\**\s*:|\Z)"
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
        return blocks.get("Descripción", "").strip() or text

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

    combined_blocks = {}
    for value in raw_values.values():
        blocks = _extract_labeled_blocks(value)
        for key, content in blocks.items():
            if content and not combined_blocks.get(key):
                combined_blocks[key] = content

    values = {}
    for label, value in raw_values.items():
        values[label] = combined_blocks.get(label, value)

    for label in _DESCRIPTION_LABELS:
        blocks = _extract_labeled_blocks(values[label])
        if blocks and label in blocks:
            values[label] = blocks[label].strip()

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


def _suite_prefix(suite_name):
    """Obtiene las primeras tres siglas sustentadas por el nombre de la Suite."""
    text = safe_text(suite_name)
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", text)
    if not words:
        return "GEN"
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(word[0] for word in words)[:3].upper()


def _domain_prefix(source_content="", hu_text="", module=""):
    """Determina AU por defecto y HO solo ante evidencia funcional explícita de Hogar."""
    evidence = " ".join(safe_text(x) for x in (source_content, hu_text, module)).casefold()
    hogar_patterns = (
        r"\bproducto\s*[:\-]?\s*hogar\b",
        r"\bmódulo\s*[:\-]?\s*hogar\b",
        r"\bmodule\s*[:\-]?\s*hogar\b",
        r"\bseguro\s+de\s+hogar\b",
        r"\bseguros?\s+de\s+hogar\b",
        r"\bcotizador(?:es)?\s+de\s+hogar\b",
        r"\bcotizador(?:es)?\s+hogar\b",
        r"\bproducto\s+hogar\b",
        r"\bmódulo\s+hogar\b",
        r"\bfuncionalidad\s+de\s+hogar\b",
    )
    return "HO" if any(re.search(pattern, evidence) for pattern in hogar_patterns) else "AU"


def build_case_title(tc, case_id, suite_name="", source_content="", hu_text="", module=""):
    """Construye: CP-[DOMINIO][SIGLAS_SUITE]-##### [DESCRIPCIÓN]."""
    suite_prefix = _suite_prefix(suite_name)
    tc_module = safe_text(tc.get("Module")) if isinstance(tc, dict) else ""
    domain_prefix = _domain_prefix(source_content, hu_text, module or tc_module)
    raw_case_id = safe_text(case_id)
    match = re.search(r"(\d{5})$", raw_case_id)
    sequence = match.group(1) if match else "00001"

    description = safe_text(tc.get("Title"))
    if not description or re.fullmatch(r"CP-[A-Z0-9_-]+-\d{5}(?:\s+.*)?", description.upper()):
        description = safe_text(tc.get("Scenario"), safe_text(tc.get("Description")))
    description = re.sub(r"\s+", " ", description).strip()
    if not description:
        description = "Caso de prueba"
    description = description.replace("|", "")
    return f"CP-{domain_prefix}{suite_prefix}-{sequence} {description}".strip()


def normalize_case_id(
    raw_id,
    module,
    index,
    prefix="CP-AU-",
    suite_name="",
    source_content="",
    hu_text="",
):
    """Normaliza IDs al formato CP-[DOMINIO][SIGLAS_SUITE]-#####."""
    candidate = safe_text(raw_id)
    if re.fullmatch(r"CP-(?:AU|HO)[A-Z0-9]{1,3}-\d{5}", candidate):
        return candidate

    suite_prefix = _suite_prefix(suite_name)
    domain_prefix = _domain_prefix(source_content, hu_text, module)
    return f"CP-{domain_prefix}{suite_prefix}-{index:05d}"


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
