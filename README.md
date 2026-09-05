# 🤖 Agente QA

Agente especializado en analizar Historias de Usuario (HU), Casos de Uso, Criterios de Aceptación y reglas funcionales para generar **Casos de Prueba (CP) funcionales en versión DRAFT**, con trazabilidad y validaciones orientadas a QA.

> **Estado:** MVP / evolución activa.

## 🎯 Objetivo

El Agente QA convierte documentación funcional en casos de prueba estructurados, revisables y preparados para su gestión en Azure DevOps, evitando inventar información que no esté sustentada por la fuente.

## 🧠 Componentes principales

### Streamlit

Es la interfaz de la aplicación. Permite cargar documentación, ejecutar la generación, revisar los CP y trabajar con las salidas generadas.

### Gemini

Es el **cerebro de IA** del agente. Analiza la documentación siguiendo el prompt QA y genera la estructura de Casos de Prueba.

### Motor QA

La lógica funcional debe garantizar, entre otras reglas:

- usar únicamente información disponible en la documentación;
- **no inventar** datos funcionales;
- generar alertas cuando falte información;
- conservar contradicciones de la fuente y alertarlas;
- mantener trazabilidad entre HU, CU, criterios y CP;
- generar como mínimo **1 CP por Caso de Uso**;
- mantener **1 Caso de Uso relacionado por CP**;
- cuando una misma funcionalidad tenga dos o más tipos de cotización con reglas, cálculos, condiciones o comportamientos diferenciados, generar **CP independientes por cada tipo** y validar cada escenario de forma completa.

## 🧪 Estructura de un Caso de Prueba

Los CP utilizan la estructura funcional definida para el proyecto, incluyendo:

- ID del CP;
- Producto;
- Módulo;
- Descripción;
- Resultado esperado de la prueba;
- Precondiciones;
- Caso de uso relacionado;
- Steps con **Steps / Action / Expected**;
- alertas y trazabilidad cuando corresponda.

El formato de identificación utilizado para Autos Colectivos sigue el patrón:

```text
CP-AC-<MÓDULO>-#####
```

## 📊 Exportaciones

La aplicación contempla generación de:

- **Excel** compatible con el flujo de importación de Azure DevOps y con la **Matriz QA** aprobada.
- **PDF** para revisión y consulta de los casos generados.

Se debe conservar el modelo aprobado de columnas y títulos; cualquier cambio estructural debe validarse antes de incorporarse.

## ☁️ Azure DevOps

La integración contempla trabajar con:

- Test Plans;
- Suites;
- Test Cases;
- Parent asociado a la Suite seleccionada;
- Related Work asociado al Caso de Uso;
- Steps nativos de Azure DevOps;
- descripción estructurada.

La integración debe permanecer protegida y **deshabilitada por defecto** hasta configurar las credenciales necesarias.

## 📁 Estructura actual del repositorio

La rama `organizar-main` contiene la aplicación reorganizada por responsabilidades, conservando la funcionalidad e interfaz aprobadas de `main` y utilizando `mao-dev-branch` únicamente como referencia estructural.

```text
Agente-QA-V1/
│
├── app.py
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
│   ├── providers/
│   │   ├── base.py
│   │   └── gemini.py
│   ├── export/
│   │   ├── excel.py
│   │   └── pdf.py
│   ├── integrations/
│   │   ├── azure_devops.py
│   │   └── azure_runtime.py
│   └── ui/
│       ├── azure_section.py
│       ├── coverage.py
│       ├── document.py
│       ├── editor.py
│       ├── generation.py
│       ├── generation_section.py
│       ├── prompt_editor.py
│       ├── results.py
│       ├── sidebar.py
│       ├── state.py
│       └── upload.py
├── config/
├── docs/
├── prompts/
├── tests/
├── prompt_qa.txt
├── requirements.txt
└── README.md
```

Los antiguos módulos duplicados de Azure y editor que existían en la raíz fueron eliminados. La implementación canónica se encuentra ahora en `agente_qa/integrations/` y `agente_qa/ui/`.

## 🏗️ Arquitectura y ramas

La estrategia de trabajo es:

| Rama | Propósito |
|---|---|
| `main` | Fuente funcional y visual aprobada |
| `mao-dev-branch` | Referencia exclusiva para arquitectura/estructura |
| `organizar-main` | Única rama donde se realiza la reorganización y los cambios de esta migración |

**Regla:** `main` y `mao-dev-branch` no se modifican durante esta reorganización.

## 🚀 Instalación local

Clonar el repositorio y crear un entorno virtual:

```bash
python -m venv .venv
```

Activar el entorno en Windows:

```bash
.venv\Scripts\activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## ▶️ Ejecutar la aplicación

Desde la raíz del proyecto:

```bash
streamlit run app.py
```

La aplicación utiliza Streamlit como interfaz web local.

## 🔐 Variables / secretos

Las credenciales y secretos **no deben guardarse en el repositorio**.

Para Gemini se utiliza la clave de API mediante configuración segura de Streamlit o variable de entorno.

Para Azure DevOps se utilizan credenciales mediante configuración segura.

El conector Azure debe permanecer deshabilitado hasta que exista configuración válida.

## 🛡️ Principios del proyecto

1. **No inventar información funcional.**
2. **Trazabilidad completa.**
3. **Alertar información faltante o contradictoria.**
4. **Conservar la estructura aprobada de Excel/PDF.**
5. **No modificar títulos de columnas sin aprobación.**
6. **Separar la lógica QA de la interfaz.**
7. **Mantener Gemini como cerebro del agente.**
8. **Mantener Streamlit como interfaz.**
9. **Proteger las ramas estables.**
10. **Probar la nueva arquitectura antes de hacer merge.**

## 📚 Próximos pasos

- Validar generación y cobertura de CP.
- Validar Excel y Matriz QA.
- Validar PDF.
- Validar editor.
- Validar conexión con Azure DevOps cuando corresponda.
- Validar Parent/Suite y Related Work/CU.
- Ejecutar pruebas de regresión antes de cualquier merge a `main`.

---

**Agente QA — proyecto en evolución**
