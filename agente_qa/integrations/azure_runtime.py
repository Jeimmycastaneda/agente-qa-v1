"""Runtime Azure DevOps preservado durante la migración modular.

Este módulo mantiene exactamente el comportamiento de lectura y publicación
que utilizaba la interfaz aprobada, pero lo separa del punto de entrada.
No ejecuta operaciones de escritura por sí mismo: las funciones de creación
solo se invocan desde la confirmación explícita de la UI.
"""
from __future__ import annotations

import base64
import html
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import streamlit as st

from agente_qa.secrets import resolve_secret
from agente_qa.utils import build_azure_description, build_case_title, safe_steps, safe_text, _ui_text


class AzureDevOpsError(RuntimeError):
    pass


def _az_config():
    """Resuelve la configuración Azure desde el proveedor central de secretos."""
    return {
        "org": resolve_secret("AZURE_DEVOPS_ORG"),
        "project": resolve_secret("AZURE_DEVOPS_PROJECT"),
        "pat": resolve_secret("AZURE_DEVOPS_PAT"),
    }


def _az_validate(cfg):
    missing = [k for k in ("org", "project", "pat") if not cfg.get(k)]
    if missing:
        raise AzureDevOpsError("Faltan secretos de Azure DevOps: " + ", ".join(missing))


def _az_auth_header(pat):
    """Construye el encabezado Basic de Azure DevOps en un único punto."""
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _az_send(req, timeout, detail_limit, unauthorized_message, not_found_message=None):
    """Ejecuta la petición HTTP y centraliza el tratamiento de errores."""
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return (json.loads(raw) if raw else {}), response.headers
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:detail_limit]
        except Exception:
            pass
        if exc.code in (401, 403):
            raise AzureDevOpsError(unauthorized_message.format(code=exc.code)) from exc
        if exc.code == 404 and not_found_message:
            raise AzureDevOpsError(not_found_message) from exc
        raise AzureDevOpsError(f"Azure respondió HTTP {exc.code}. {detail}") from exc
    except URLError as exc:
        raise AzureDevOpsError(
            f"No fue posible comunicarse con Azure DevOps: {exc.reason}"
        ) from exc


def _az_get_json(url, pat):
    req = Request(
        url,
        method="GET",
        headers={
            "Authorization": _az_auth_header(pat),
            "Accept": "application/json",
            "User-Agent": "Agente-QA-Streamlit/1.0",
        },
    )
    return _az_send(
        req,
        timeout=20,
        detail_limit=1000,
        unauthorized_message=(
            "Azure rechazó la autenticación/autorización (HTTP {code}). "
            "Verifica el PAT, su vigencia y sus scopes."
        ),
        not_found_message=(
            "No se encontró el proyecto o el recurso de Test Plans. "
            "Verifica AZURE_DEVOPS_ORG y AZURE_DEVOPS_PROJECT."
        ),
    )


def _az_request_json(url, pat, method="POST", payload=None, content_type="application/json"):
    """Solicitud Azure con escritura explícita; solo se invoca desde la confirmación de carga."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = Request(
        url,
        method=method,
        data=body,
        headers={
            "Authorization": _az_auth_header(pat),
            "Accept": "application/json",
            "Content-Type": content_type,
            "User-Agent": "Agente-QA-Streamlit/1.0",
        },
    )
    return _az_send(
        req,
        timeout=30,
        detail_limit=1800,
        unauthorized_message=(
            "Azure rechazó la operación de escritura (HTTP {code}). "
            "Verifica que el PAT tenga permisos de Work Items/Test Plans y esté vigente."
        ),
    )


def _azure_steps_xml(steps):
    """Construye Microsoft.VSTS.TCM.Steps con Action + Expected."""
    nodes = []
    for idx, step in enumerate(steps or [], start=1):
        if not isinstance(step, dict):
            continue
        action = safe_text(step.get("Action"), step.get("action"), step.get("Step"))
        expected = safe_text(step.get("Expected value"), step.get("Expected"), step.get("expected"))
        if not action and not expected:
            continue
        action_html = html.escape(action, quote=False).replace("\n", "<br />")
        expected_html = html.escape(expected, quote=False).replace("\n", "<br />")
        nodes.append(
            f'<step id="{idx}" type="ActionStep">'
            f'<parameterizedString isformatted="true">{action_html}</parameterizedString>'
            f'<parameterizedString isformatted="true">{expected_html}</parameterizedString>'
            f'</step>'
        )
    if not nodes:
        return '<steps id="0" last="0"></steps>'
    return f'<steps id="0" last="{len(nodes)}">{"".join(nodes)}</steps>'


def _azure_description_html(description):
    """Convierte la Description del CP a HTML real para Azure DevOps."""
    text = safe_text(description)
    if not text:
        return ""
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?(?:div|p|span|blockquote)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"</?(?:ul|ol)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = re.sub(r"</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    labels = ["Producto:", "Módulo:", "Descripción:", "Resultado esperado de la prueba:", "Precondiciones:", "Caso de uso relacionado:"]
    for label in labels:
        text = re.sub(rf"\s*{re.escape(label)}\s*", f"\n{label} ", text, count=1, flags=re.I)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?m)^\s*[•●▪◦]\s*", "- ", text)
    text = re.sub(r"(?m)^\s*[o]\s+", "- ", text)
    text = re.sub(r"(?m)^\s*[-–—]\s*", "- ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    block_pattern = re.compile(
        r"(?ms)^(Producto:|Módulo:|Descripción:|Resultado esperado de la prueba:|Precondiciones:|Caso de uso relacionado:)\s*(.*?)(?=\n(?:Producto:|Módulo:|Descripción:|Resultado esperado de la prueba:|Precondiciones:|Caso de uso relacionado:)|$)",
        re.I,
    )
    blocks = block_pattern.findall(text)
    if not blocks:
        return f"<p>{html.escape(text, quote=False)}</p>"
    html_blocks = []
    for label, content in blocks:
        label = next((x for x in labels if x.lower() == label.lower()), label)
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        bullets = [line[2:].strip() for line in lines if line.startswith("- ")]
        normal = [line for line in lines if not line.startswith("- ")]
        label_html = f"<strong>{html.escape(label)}</strong>"
        if label.rstrip(":") == "Caso de uso relacionado" or (bullets and not normal):
            items = bullets or [content.strip() or "Pendiente"]
            html_blocks.append(f"<p>{label_html}</p><ul>{''.join(f'<li>{html.escape(item, quote=False)}</li>' for item in items)}</ul>")
        else:
            content_html = "<br/>".join(html.escape(line, quote=False) for line in lines) or "Pendiente"
            html_blocks.append(f"<p>{label_html} {content_html}</p>")
    return "<p>&nbsp;</p>".join(html_blocks)


def _get_id_padre(tc):
    """Obtiene el ID padre explícito. Nunca usa el Test Plan como sustituto."""
    for key in ("IDPadre", "ID Padre", "Parent ID", "ParentId", "parent_id", "id_padre"):
        value = safe_text(tc.get(key))
        if value:
            return value
    return safe_text(st.session_state.get("azure_id_padre"))


def _tipo_origen_proyecto(tc):
    """Valor requerido por el campo Custom.TipoOrigenProyecto."""
    return safe_text(
        tc.get("Tipo Origen Proyecto"), tc.get("TipoOrigenProyecto"),
        st.session_state.get("azure_tipo_origen_proyecto"), "Proyecto",
    )


def create_azure_test_case_work_item(tc, target_plan):
    """Crea un Work Item de tipo Test Case. Solo se llama al confirmar."""
    cfg = _az_config()
    _az_validate(cfg)
    case_id = safe_text(tc.get("ID"), "CP-PREVIEW")
    title = build_case_title(tc, case_id)

    # Siempre arma el bloque completo solicitado por el modelo: no descartar
    # Producto, Módulo, Resultado esperado, Precondiciones ni CU relacionado.
    description = build_azure_description(
        safe_text(tc.get("Product"), "Cotizadores Web"),
        safe_text(tc.get("Module"), "Cotizador Autos Colectivos"),
        safe_text(tc.get("Description"), tc.get("Scenario"), title),
        safe_text(tc.get("Expected Result"), "Pendiente"),
        safe_text(tc.get("Preconditions"), "Pendiente"),
        safe_text(tc.get("Related Use Case"), "Pendiente"),
    )

    id_padre = _get_id_padre(tc)
    tipo_origen = _tipo_origen_proyecto(tc)
    if not id_padre:
        raise AzureDevOpsError(
            "No se puede crear el CP: Azure exige el campo Custom.IDPadre. "
            "Informa el ID del Work Item padre (HU/elemento funcional) antes de confirmar. "
            "No se usará automáticamente el Test Plan ni la Suite como IDPadre."
        )
    if not tipo_origen:
        raise AzureDevOpsError(
            "No se puede crear el CP: Azure exige Custom.TipoOrigenProyecto. "
            "El valor esperado para esta configuración es 'Proyecto'."
        )

    id_padre_value = int(id_padre) if id_padre.isdigit() else id_padre
    patch = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": _azure_description_html(description)},
        {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": _azure_steps_xml(safe_steps(tc))},
        {"op": "add", "path": "/fields/Custom.IDPadre", "value": id_padre_value},
        {"op": "add", "path": "/fields/Custom.TipoOrigenProyecto", "value": tipo_origen},
    ]
    area_path = safe_text(target_plan.get("area_path"))
    iteration = safe_text(target_plan.get("iteration"))
    if area_path:
        patch.append({"op": "add", "path": "/fields/System.AreaPath", "value": area_path})
    if iteration:
        patch.append({"op": "add", "path": "/fields/System.IterationPath", "value": iteration})
    org = quote(cfg["org"], safe="")
    project = quote(cfg["project"], safe="")
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$Test%20Case?api-version=7.1"
    payload, _ = _az_request_json(url, cfg["pat"], method="POST", payload=patch, content_type="application/json-patch+json")
    return payload


def _az_testplan_url(cfg, path):
    return f"https://dev.azure.com/{quote(cfg['org'], safe='')}/{quote(cfg['project'], safe='')}/_apis/testplan/{path}"


def add_test_cases_to_suite(plan_id, suite_id, work_item_ids):
    cfg = _az_config()
    _az_validate(cfg)
    if not work_item_ids:
        return []
    path = f"Plans/{quote(str(plan_id), safe='')}/Suites/{quote(str(suite_id), safe='')}/TestCase"
    payload, _ = _az_request_json(
        _az_testplan_url(cfg, path) + "?api-version=7.1",
        cfg["pat"], method="POST",
        payload=[{"workItem": {"id": int(wid)}} for wid in work_item_ids],
    )
    return payload.get("value", payload if isinstance(payload, list) else [])


def create_selected_cases_in_azure(cases, target_plan, target_suite):
    created, work_item_ids, errors = [], [], []
    for tc in cases:
        cp_id = safe_text(tc.get("ID"), "CP-PREVIEW")
        try:
            wi = create_azure_test_case_work_item(tc, target_plan)
            azure_id = wi.get("id")
            if not azure_id:
                raise AzureDevOpsError("Azure no devolvió el ID del Work Item creado.")
            work_item_ids.append(int(azure_id))
            created.append({"cp_id": cp_id, "title": build_case_title(tc, cp_id), "azure_id": int(azure_id), "status": "Work Item creado; pendiente de asociar a Suite"})
        except Exception as exc:
            errors.append({"cp_id": cp_id, "error": str(exc)})
    if work_item_ids:
        try:
            add_test_cases_to_suite(target_plan["id"], target_suite["id"], work_item_ids)
            for row in created:
                row["status"] = "Creado y asociado a la Suite"
        except Exception as exc:
            for row in created:
                row["status"] = "Work Item creado, pero NO se pudo asociar a la Suite"
                row["association_error"] = str(exc)
            errors.append({"cp_id": "LOTE", "error": f"No se pudo asociar el lote a la Suite: {exc}"})
    return {"created": created, "errors": errors}


def test_connection():
    cfg = _az_config()
    _az_validate(cfg)
    org = quote(cfg["org"], safe="")
    project = quote(cfg["project"], safe="")
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitemtypes/Test%20Case?api-version=7.1"
    payload, _ = _az_get_json(url, cfg["pat"])
    return {"organization": cfg["org"], "project": cfg["project"], "work_item_type": payload.get("name", "Test Case"), "message": "Conexión correcta. Solo se realizó una consulta de lectura."}


def list_test_plans(limit=10):
    cfg = _az_config()
    _az_validate(cfg)
    params = urlencode({"api-version": "7.1", "$top": int(limit)})
    payload, _ = _az_get_json(_az_testplan_url(cfg, "plans") + "?" + params, cfg["pat"])
    plans = sorted(payload.get("value") or [], key=lambda x: int(x.get("id") or 0), reverse=True)[:int(limit)]
    rows = [{"id": p.get("id"), "name": _ui_text(p.get("name"), "Sin nombre"), "state": p.get("state", ""), "area_path": p.get("areaPath", ""), "iteration": p.get("iteration", ""), "start_date": p.get("startDate", ""), "end_date": p.get("endDate", "")} for p in plans]
    return {"ok": True, "organization": cfg["org"], "project": cfg["project"], "count": len(rows), "plans": rows, "message": "Consulta correcta. Solo se consultaron los 10 Test Plans más recientes por ID; no se creó, modificó ni eliminó ningún recurso."}


def list_test_suites(plan_id):
    cfg = _az_config()
    _az_validate(cfg)
    path = f"Plans/{quote(str(plan_id), safe='')}/suites"
    payload, _ = _az_get_json(_az_testplan_url(cfg, path) + "?api-version=7.1", cfg["pat"])
    rows = []
    for s in payload.get("value") or []:
        plan = s.get("plan") if isinstance(s.get("plan"), dict) else {}
        parent = s.get("parentSuite") if isinstance(s.get("parentSuite"), dict) else {}
        rows.append({"id": s.get("id"), "name": _ui_text(s.get("name"), "Suite sin nombre"), "suite_type": s.get("suiteType", ""), "plan_id": plan.get("id", plan_id), "parent_suite": parent.get("id")})
    return rows


def _normalize_case_rows(payload):
    rows = []
    values = payload.get("value") if isinstance(payload, dict) else []
    for item in values or []:
        if not isinstance(item, dict):
            continue
        wi = {}
        for key in ("testCase", "workItem"):
            candidate = item.get(key)
            if isinstance(candidate, dict):
                wi = candidate
                break
        if not wi:
            wi = item
        nested_work_item = wi.get("workItem")
        nested_id = nested_work_item.get("id") if isinstance(nested_work_item, dict) else None
        raw_id = wi.get("id") or item.get("id") or nested_id
        if not raw_id:
            for container in (wi, item):
                if not isinstance(container, dict):
                    continue
                for key in ("url", "href", "webUrl"):
                    value = container.get(key)
                    if value:
                        match = re.search(r"/workitems/(\d+)(?:[/?]|$)", str(value), re.I)
                        if match:
                            raw_id = match.group(1)
                            break
                if raw_id:
                    break
        title = wi.get("name") or wi.get("title") or item.get("name") or item.get("title")
        if raw_id is None or str(raw_id).strip() == "":
            continue
        rows.append({"id": str(raw_id).strip(), "title": _ui_text(title, "Test Case sin título"), "raw": item})
    unique, seen = [], set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        unique.append(row)
    return unique


def list_test_cases(plan_id, suite_id):
    cfg = _az_config()
    _az_validate(cfg)
    path = f"Plans/{quote(str(plan_id), safe='')}/Suites/{quote(str(suite_id), safe='')}/TestCase"
    payload, _ = _az_get_json(_az_testplan_url(cfg, path) + "?api-version=7.1&expand=true", cfg["pat"])
    rows = _normalize_case_rows(payload)
    if not rows:
        org = quote(cfg["org"], safe="")
        project = quote(cfg["project"], safe="")
        fallback_url = f"https://dev.azure.com/{org}/{project}/_apis/test/Plans/{quote(str(plan_id), safe='')}/suites/{quote(str(suite_id), safe='')}/testcases?api-version=7.1"
        fallback_payload, _ = _az_get_json(fallback_url, cfg["pat"])
        rows = _normalize_case_rows(fallback_payload)
    return rows


def _az_parse_steps_xml(xml_text):
    if not xml_text:
        return []
    decoded = html.unescape(str(xml_text))
    steps = []
    for match in re.finditer(r"<step\b[^>]*>.*?</step>", decoded, flags=re.I | re.S):
        node = match.group(0)
        vals = re.findall(r"<parameterizedString[^>]*>(.*?)</parameterizedString>", node, flags=re.I | re.S)
        clean = []
        for value in vals[:2]:
            value = re.sub(r"<[^>]+>", "", value)
            clean.append(html.unescape(value).strip())
        if clean:
            steps.append({"Step #": len(steps) + 1, "Action": clean[0] if len(clean) > 0 else "", "Expected value": clean[1] if len(clean) > 1 else ""})
    return steps


def get_test_case_detail(test_case_id):
    cfg = _az_config()
    _az_validate(cfg)
    org = quote(cfg["org"], safe="")
    project = quote(cfg["project"], safe="")
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{quote(str(test_case_id), safe='')}?api-version=7.1"
    payload, _ = _az_get_json(url, cfg["pat"])
    fields = payload.get("fields") or {}
    return {"id": payload.get("id"), "title": fields.get("System.Title", ""), "description": fields.get("System.Description", "") or "", "steps": _az_parse_steps_xml(fields.get("Microsoft.VSTS.TCM.Steps", "") or ""), "area_path": fields.get("System.AreaPath", ""), "iteration_path": fields.get("System.IterationPath", ""), "state": fields.get("System.State", ""), "work_item_type": fields.get("System.WorkItemType", "Test Case"), "raw_fields": fields}
