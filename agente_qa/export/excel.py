"""Exportación Excel del agente QA."""

import io
import pandas as pd

from agente_qa.utils import (
    safe_text, safe_steps, normalize_coverage, normalize_validation_method,
    build_azure_description, format_description_for_azure, build_case_title,
    normalize_case_id, find_coverage, aggregate_case_alerts,
)
from config.qa_config import AZURE_COLUMNS, MATRIZ_COLUMNS, EXCEL_CONFIGS


def create_excel(data, config_key):
    """Genera Azure Import y Matriz QA con la estructura aprobada."""
    config = EXCEL_CONFIGS[config_key]
    output = io.BytesIO()
    azure_rows = []
    matriz_rows = []
    cases = data.get("TEST_CASES", [])
    suite_name = safe_text(data.get("SUITE_NAME"), data.get("SUITE"))

    for idx, tc in enumerate(cases, start=1):
        module = safe_text(tc.get("Module"), "GENERAL")
        raw_case_id = safe_text(tc.get("ID"), f"CP-AU-{idx:05d}")
        # La numeración exportada debe ser determinista por Suite y no depender
        # de IDs inconsistentes o duplicados devueltos por el modelo.
        normalized_id = normalize_case_id(
            raw_case_id,
            module=module,
            index=idx,
            suite_name=suite_name,
            source_content=safe_text(data.get("SOURCE_CONTENT"), data.get("SOURCE")),
            hu_text=safe_text(data.get("HU_TEXT")),
        )
        title = build_case_title(
            tc,
            normalized_id,
            suite_name=suite_name,
            source_content=safe_text(data.get("SOURCE_CONTENT"), data.get("SOURCE")),
            hu_text=safe_text(data.get("HU_TEXT")),
            module=module,
        )
        case_id = title.split(" ", 1)[0]

        raw_description = safe_text(tc.get("Description"), safe_text(tc.get("Scenario")))
        preconditions = safe_text(tc.get("Preconditions"))
        scenario = safe_text(tc.get("Scenario"), raw_description)
        description = format_description_for_azure(build_azure_description(
            product=safe_text(safe_text(tc.get("Product"), data.get("PRODUCT")), "Pendiente"),
            module=module or "Pendiente",
            description=raw_description,
            expected=safe_text(safe_text(tc.get("Expected Result"), tc.get("ExpectedResult")), tc.get("Resultado esperado de la prueba"), "Pendiente"),
            preconditions=preconditions or "Pendiente",
            related_use_case=safe_text(safe_text(tc.get("Related Use Case"), tc.get("RelatedUseCase")), tc.get("Caso de uso relacionado"), "Pendiente"),
        ))
        steps = safe_steps(tc)
        coverage = find_coverage(data, tc)
        validation_method = normalize_validation_method(coverage.get("Validation Method", tc.get("Validation Method", "Pendiente")))
        coverage_value = normalize_coverage(coverage.get("Coverage", tc.get("Coverage", "Pendiente")))
        alerts = safe_text(coverage.get("Alerts")) or aggregate_case_alerts(data, tc)
        if alerts == "Sin Alertas" and data.get("ALERTS"):
            general_alerts = []
            for alert in data["ALERTS"]:
                name = safe_text(alert.get("Alert")); reason = safe_text(alert.get("Reason"))
                if name: general_alerts.append(f"{name}: {reason}" if reason else name)
            if general_alerts: alerts = " | ".join(general_alerts)

        steps_for_export = steps or [{"Step #": 1, "Action": "Información insuficiente para definir el paso.", "Expected value": "Validar con el equipo funcional antes de ejecutar."}]
        azure_rows.append({"ID": "", "Work Item Type": "Test Case", "Title": title, "Description": description, "Test Step": "", "Step Action": "", "Step Expected": "", "Area Path": safe_text(config.get("area_path"), "COTIZADORES WEB\\DESARROLLO"), "IDPadre": "", "Tipo Origen Proyecto": "Proyecto", "Tiempo Real": "", "Assigned To": safe_text(config.get("assigned_to")), "State": "Design"})
        for step_index, step in enumerate(steps_for_export, start=1):
            azure_rows.append({"ID": "", "Work Item Type": "", "Title": "", "Description": "", "Test Step": step.get("Step #", step_index), "Step Action": safe_text(step.get("Action"), step.get("action"), step.get("Step"), "Acción no definida"), "Step Expected": safe_text(step.get("Expected value"), step.get("Expected"), step.get("expected"), "Resultado esperado no definido"), "Area Path": "", "IDPadre": "", "Tipo Origen Proyecto": "", "Tiempo Real": "", "Assigned To": "", "State": ""})
        matriz_rows.append({"TestCaseId": case_id, "Title": title, "Requirement / Use Case": safe_text(coverage.get("Requirement / Use Case", tc.get("Related Use Case"))), "Criterion": safe_text(coverage.get("Criterion", tc.get("Criterion"))), "Scenario": scenario, "Scenario Type": safe_text(tc.get("Scenario Type"), "No definido"), "Description": description, "Preconditions": preconditions, "Validation Method": validation_method, "Coverage": coverage_value, "Alerts": alerts, "Effort": safe_text(tc.get("Effort"), "No definido")})

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(azure_rows, columns=AZURE_COLUMNS).to_excel(writer, sheet_name="Azure Import", index=False)
        pd.DataFrame(matriz_rows, columns=MATRIZ_COLUMNS).to_excel(writer, sheet_name="Matriz QA", index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
            for column_cells in ws.columns:
                letter = column_cells[0].column_letter
                max_len = max(len(str(cell.value or "")) for cell in column_cells)
                ws.column_dimensions[letter].width = min(max(max_len + 2, 12), 60)
    output.seek(0)
    return output.getvalue()
