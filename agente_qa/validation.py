"""Validaciones técnicas de cobertura QA."""

import re
import streamlit as st

ALLOWED_INTERFACE_STATUS = {"UI_VERIFICABLE", "NO_UI", "AMBIGUA"}


def _normalize_cu(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def _extract_related_cu(tc):
    """Extrae las referencias a CU desde Related Use Case."""
    value = (
        tc.get("Related Use Case")
        or tc.get("related_use_case")
        or tc.get("use_case")
        or tc.get("Requirement / Use Case")
        or tc.get("Caso de uso relacionado")
        or ""
    )
    if isinstance(value, list):
        raw_parts = [str(x).strip() for x in value if str(x).strip()]
    else:
        raw_parts = [x.strip() for x in re.split(r"[;\n|]", str(value)) if x.strip()]

    results = []
    for part in raw_parts:
        match = re.search(r"\b(CU[-_ ]?\d+)\b", part, flags=re.IGNORECASE)
        if match:
            results.append(match.group(1).upper().replace("_", "-").replace(" ", "-"))
        else:
            results.append(part)
    return results


def _cu_info(cu):
    if isinstance(cu, dict):
        cid = str(
            cu.get("ID") or cu.get("id") or
            cu.get("Use Case ID") or cu.get("CU") or ""
        ).strip()
        name = str(
            cu.get("Name") or cu.get("name") or
            cu.get("Title") or cu.get("Description") or ""
        ).strip()
        status = str(cu.get("INTERFACE_STATUS") or "").strip().upper()
        eligible = cu.get("CP_ELIGIBLE")
    else:
        cid = str(cu).strip()
        name = cid
        status = ""
        eligible = None
    return cid, name or cid, status, eligible


def calculate_cu_coverage(cases, identified_use_cases):
    """Calcula cobertura obligatoria únicamente sobre CU elegibles para CP."""
    cu_map = {}
    eligible_keys = set()
    ambiguous = []
    non_eligible = []

    for cu in identified_use_cases or []:
        cid, name, status, eligible = _cu_info(cu)
        if not cid:
            continue
        if status not in ALLOWED_INTERFACE_STATUS:
            raise ValueError(f"CU {cid}: INTERFACE_STATUS inválido o ausente.")
        expected_eligible = status == "UI_VERIFICABLE"
        if eligible is not expected_eligible:
            raise ValueError(f"CU {cid}: CP_ELIGIBLE no coincide con INTERFACE_STATUS.")

        key = _normalize_cu(cid)
        cu_map[key] = {"id": cid, "name": name, "interface_status": status}
        if expected_eligible:
            eligible_keys.add(key)
        elif status == "AMBIGUA":
            ambiguous.append({"id": cid, "name": name})
        else:
            non_eligible.append({"id": cid, "name": name})

    covered = {}
    cp_without_cu = []
    cp_multiple_cu = []
    cp_non_eligible_cu = []

    for index, tc in enumerate(cases or [], start=1):
        cp_id = str(tc.get("ID") or f"CP-{index:05d}").strip()
        relations = _extract_related_cu(tc)

        if len(relations) == 0:
            cp_without_cu.append(cp_id)
            continue
        if len(relations) != 1:
            cp_multiple_cu.append(cp_id)
            continue

        rel = _normalize_cu(relations[0])
        matched = None
        for cu_key, cu_info in cu_map.items():
            if rel == cu_key or rel == _normalize_cu(cu_info["name"]):
                matched = cu_key
                break

        if matched is None:
            cp_without_cu.append(cp_id)
        elif matched not in eligible_keys:
            cp_non_eligible_cu.append(cp_id)
        else:
            covered.setdefault(matched, []).append(cp_id)

    missing = [
        info for key, info in cu_map.items()
        if key in eligible_keys and key not in covered
    ]
    total_cu = len(cu_map)
    total_eligible_cu = len(eligible_keys)
    total_cp = len(cases or [])
    covered_count = len(covered)
    percentage = round((covered_count / total_eligible_cu) * 100, 1) if total_eligible_cu else 100.0

    return {
        "total_cu": total_cu,
        "total_eligible_cu": total_eligible_cu,
        "total_non_eligible_cu": len(non_eligible),
        "total_ambiguous_cu": len(ambiguous),
        "non_eligible_cu": non_eligible,
        "ambiguous_cu": ambiguous,
        "total_cp": total_cp,
        "covered_cu": covered_count,
        "missing_cu": missing,
        "cp_without_cu": cp_without_cu,
        "cp_multiple_cu": cp_multiple_cu,
        "cp_non_eligible_cu": cp_non_eligible_cu,
        "percentage": percentage,
        "valid": (
            total_cu > 0
            and not missing
            and not cp_without_cu
            and not cp_multiple_cu
            and not cp_non_eligible_cu
            and all(
                any(
                    isinstance(a, dict)
                    and str(a.get("Alert", "")).strip()
                    and str(a.get("Reason", "")).strip()
                    for a in []
                )
                for _ in []
            )
        ),
    }


def _ambiguous_alerts(data):
    """Verifica que cada CU AMBIGUA tenga ALERTA."""
    alerts = data.get("ALERTS", []) or []
    alert_text = " ".join(
        str(a.get("Alert", "")) + " " + str(a.get("Reason", ""))
        for a in alerts if isinstance(a, dict)
    ).casefold()
    missing = []
    for cu in data.get("USE_CASES", []) or []:
        if isinstance(cu, dict) and cu.get("INTERFACE_STATUS") == "AMBIGUA":
            cid = str(cu.get("ID", "")).strip()
            if cid and cid.casefold() not in alert_text:
                missing.append(cid)
    return missing


def validate_minimum_cu_coverage(data):
    """Bloquea solo por falta de cobertura de CU con interfaz verificable."""
    cases = data.get("TEST_CASES", []) or []
    use_cases = data.get("USE_CASES", []) or []

    if not use_cases:
        raise ValueError(
            "GENERACIÓN BLOQUEADA: Gemini no devolvió la lista completa de Casos de Uso (USE_CASES)."
        )

    metrics = calculate_cu_coverage(cases, use_cases)
    missing_ambiguous_alerts = _ambiguous_alerts(data)
    if missing_ambiguous_alerts:
        raise ValueError(
            "GENERACIÓN BLOQUEADA: los CU AMBIGUA requieren ALERTA: "
            + ", ".join(missing_ambiguous_alerts)
        )

    if not metrics["valid"]:
        missing = ", ".join(f'{x["id"]} - {x["name"]}' for x in metrics["missing_cu"])
        details = []
        if missing:
            details.append("CU elegible sin CP: " + missing)
        if metrics["cp_without_cu"]:
            details.append("CP sin CU válido: " + ", ".join(metrics["cp_without_cu"]))
        if metrics["cp_multiple_cu"]:
            details.append("CP con más de un CU: " + ", ".join(metrics["cp_multiple_cu"]))
        if metrics["cp_non_eligible_cu"]:
            details.append("CP asociado a CU no elegible: " + ", ".join(metrics["cp_non_eligible_cu"]))
        raise ValueError(
            f'COBERTURA INCOMPLETA: {metrics["covered_cu"]}/{metrics["total_eligible_cu"]} CU elegibles cubiertos '
            f'({metrics["percentage"]}%). ' + " | ".join(details)
        )
    return metrics


def render_cu_coverage(metrics):
    st.markdown("### 📊 Cobertura de CU con interfaz verificable")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CU identificados", metrics["total_cu"])
    c2.metric("CU elegibles", metrics["total_eligible_cu"])
    c3.metric("CP generados", metrics["total_cp"])
    c4.metric("Cobertura", f'{metrics["percentage"]}%')
    if metrics["valid"]:
        st.success(
            "✅ Cobertura completa: cada CU con interfaz verificable tiene mínimo un CP. "
            f'Quedan fuera de generación {metrics["total_non_eligible_cu"]} CU sin interfaz y '
            f'{metrics["total_ambiguous_cu"]} CU ambiguos.'
        )
    else:
        st.error(
            f'🔴 Cobertura incompleta: {metrics["covered_cu"]}/{metrics["total_eligible_cu"]} CU elegibles cubiertos. '
            f'Faltan {len(metrics["missing_cu"])} CU.'
        )
        if metrics["missing_cu"]:
            with st.expander("Ver CU elegibles sin Caso de Prueba", expanded=True):
                for cu in metrics["missing_cu"]:
                    st.write(f'• **{cu["id"]}** — {cu["name"]}')
        if metrics["cp_without_cu"]:
            st.warning("CP sin CU válido: " + ", ".join(metrics["cp_without_cu"]))
        if metrics["cp_multiple_cu"]:
            st.warning("CP relacionados con más de un CU: " + ", ".join(metrics["cp_multiple_cu"]))
        if metrics["cp_non_eligible_cu"]:
            st.warning("CP asociados a CU no elegibles: " + ", ".join(metrics["cp_non_eligible_cu"]))
