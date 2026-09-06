# 🤖 Agente QA

Agente especializado en analizar Historias de Usuario (HU), Casos de Uso, Criterios de Aceptación y reglas funcionales para generar **Casos de Prueba (CP) funcionales en versión DRAFT**, con trazabilidad y validaciones orientadas a QA.

> **Estado:** estabilización en `organizar-main`. No se debe pasar a `main` hasta completar las pruebas de regresión.

## Objetivo

Convertir documentación funcional en casos de prueba estructurados, revisables y preparados para gestión en Azure DevOps, sin inventar información que no esté sustentada por la fuente.

## Arquitectura

- **Gemini:** cerebro de IA.
- **Streamlit:** interfaz.
- **Motor QA:** generación, normalización, validación y cobertura.
- **Exportación:** Excel compatible con el modelo aprobado y PDF.
- **Azure DevOps:** consulta de referencia, preview y publicación explícita.

El punto de entrada es `app.py`; la lógica se encuentra separada por responsabilidades dentro de `agente_qa/`.

```text
Agente-QA-V1/
├── app.py
├── prompt_qa.txt
├── requirements.txt
├── config/
│   └── qa_config.py
├── agente_qa/
│   ├── config.py
│   ├── defaults.py
│   ├── errors.py
│   ├── extraction.py
│   ├── generation.py
│   ├── prompts.py
│   ├── secrets.py
│   ├── security.py
│   ├── settings.py
│   ├── utils.py
│   ├── validation.py
│   ├── export/
│   │   ├── excel.py
│   │   └── pdf.py
│   ├── integrations/
│   │   ├── azure_runtime.py
│   │   └── azure_devops.py
│   ├── providers/
│   │   ├── base.py
│   │   └── gemini.py
│   └── ui/
│       ├── azure_section.py
│       ├── coverage.py
│       ├── document.py
│       ├── editor.py
│       ├── generation_section.py
│       ├── prompt_editor.py
│       ├── results.py
│       └── state.py
└── tests/
    ├── test_azure_devops.py
    ├── test_utils.py
    └── test_validation.py
```

`agente_qa/integrations/azure_runtime.py` es la implementación canónica de Azure. `azure_devops.py` únicamente conserva compatibilidad con nombres históricos; no debe contener una segunda implementación HTTP.

## Reglas funcionales del agente

1. Usar únicamente información disponible en HU, CU, criterios, reglas, mockups, notas, restricciones, dependencias y datos técnicos proporcionados.
2. No inventar información funcional.
3. Cuando falte información, generar la alerta correspondiente.
4. Si un mensaje no está definido en la fuente, usar exactamente: `Mensaje no definido en la fuente. Validar con equipo funcional.`
5. Conservar contradicciones de la fuente y generar alerta.
6. Mantener trazabilidad entre fuente y CP.
7. Generar como mínimo **1 CP por Caso de Uso**.
8. Un CP debe tener **un solo Caso de Uso relacionado**.
9. Si existen tipos de cotización con reglas o comportamientos diferentes, generar CP independientes por tipo.
10. El título del CP debe iniciar con verbo en infinitivo, ser breve, claro y autosuficiente; la navegación pertenece a los Steps.

## Estructura del CP

Cada CP contempla:

- ID;
- Product;
- Module;
- Description;
- Expected Result;
- Preconditions;
- Related Use Case;
- Steps con Action y Expected;
- Coverage, Validation Method, Alerts y trazabilidad cuando corresponda.

Para Autos Colectivos, el identificador sigue el patrón:

```text
CP-AC-<MODULE>-#####
```

## Excel y Matriz QA

Se debe conservar exactamente el modelo aprobado de columnas y títulos para Azure DevOps. No se agregan ni cambian columnas sin aprobación.

La configuración de Autos Colectivos utiliza `COTIZADORES WEB\\DESARROLLO` como Area Path y mantiene la hoja de Matriz QA.

## Azure DevOps

La integración debe seguir estas reglas:

- Las consultas de Test Plans, Suites y Test Cases son de lectura.
- La Suite seleccionada puede analizarse de forma conjunta para obtener referencia estructural.
- Azure es **referencia estructural**, no fuente de reglas funcionales.
- La HU continúa siendo la fuente funcional del nuevo CP.
- La generación de preview no publica cambios.
- La creación en Azure requiere selección explícita, revisión y confirmación.
- Se valida la existencia de títulos duplicados antes de crear.
- `IDPadre` no se sustituye automáticamente por Test Plan o Suite.
- Las credenciales no se almacenan en el código fuente.

## Seguridad y secretos

Los secretos se resuelven desde configuración segura de Streamlit o variables de entorno mediante `agente_qa/secrets.py`.

Nunca se debe subir `.streamlit/secrets.toml`, PAT, API keys u otras credenciales al repositorio.

## Pruebas y criterio de estabilidad

Las pruebas automatizadas se ejecutan con:

```bash
python -m pytest -q
```

También existe validación automática en GitHub Actions para `organizar-main`.

Antes de considerar estable la rama se debe verificar:

- compilación de todos los módulos Python;
- pruebas automatizadas en verde;
- generación de CP y cobertura CU;
- exportación Excel y Matriz QA;
- exportación PDF;
- edición de CP;
- preview basado en referencia Azure;
- publicación Azure solo con confirmación explícita;
- ausencia de secretos o archivos generados en Git;
- ejecución funcional desde `streamlit run app.py`.

## Ramas

| Rama | Propósito |
|---|---|
| `main` | Rama estable/aprobada. No se modifica durante la estabilización. |
| `mao-dev-branch` | Solo referencia estructural. No se usa como fuente funcional. |
| `organizar-main` | Única rama donde se realizan los cambios y pruebas de esta reorganización. |

**Regla de trabajo:** toda corrección y validación se realiza primero en `organizar-main`. Solo cuando la rama esté estable, probada y revisada se podrá considerar un futuro merge a `main`.

## Instalación local

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

## Flujo de estabilización

1. Estabilizar la arquitectura modular.
2. Unificar implementaciones duplicadas.
3. Ejecutar pruebas automatizadas y corregir regresiones.
4. Validar generación, cobertura y exportaciones.
5. Validar Azure en modo lectura y posteriormente publicación controlada.
6. Ejecutar prueba funcional completa desde Streamlit.
7. Revisar cambios finales de `organizar-main`.
8. **Solo después de todo lo anterior**, evaluar el merge a `main`.
