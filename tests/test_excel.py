from io import BytesIO

from openpyxl import load_workbook

from agente_qa.export.excel import create_excel
from config.qa_config import AZURE_COLUMNS, MATRIZ_COLUMNS


def test_excel_preserves_approved_columns_and_uses_step_expected_fallback():
    data = {
        "PRODUCT": "Cotizadores Web",
        "TEST_CASES": [
            {
                "ID": "CP-AC-CAC-00001",
                "Product": "Cotizadores Web",
                "Module": "Cotizador Autos Colectivos",
                "Title": "Consultar cotización",
                "Description": "Validar consulta",
                "Expected Result": "Se muestra la cotización",
                "Preconditions": "Usuario autenticado",
                "Related Use Case": "CU-325",
                "Steps": [
                    {
                        "Step #": 1,
                        "Action": "Ingresar al módulo",
                        "Expected": "Se muestra el formulario",
                    }
                ],
            }
        ],
        "USE_CASES": [{"ID": "CU-325", "Name": "Consultar cotización"}],
    }

    content = create_excel(data, "Autos Colectivos")
    workbook = load_workbook(BytesIO(content), read_only=True)

    azure = workbook["Azure Import"]
    matriz = workbook["Matriz QA"]

    assert list(next(azure.values)) == AZURE_COLUMNS
    assert list(next(matriz.values)) == MATRIZ_COLUMNS

    rows = list(azure.values)
    assert rows[1][7] == "COTIZADORES WEB\\DESARROLLO"
    assert rows[1][9] == "Proyecto"
    assert rows[2][5] == "Ingresar al módulo"
    assert rows[2][6] == "Se muestra el formulario"
