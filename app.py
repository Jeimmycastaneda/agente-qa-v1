"""Punto de entrada de Agente QA.

La aplicación histórica se conserva en app_legacy.py mientras se completa la
migración funcional hacia los módulos de agente_qa/. No se copia lógica desde
mao-dev; main/organizar-main son las fuentes permitidas.
"""

# Streamlit ejecuta este archivo como script. Importar el legado conserva el
# comportamiento actual sin duplicar otra copia de la aplicación.
import app_legacy  # noqa: F401,E402
