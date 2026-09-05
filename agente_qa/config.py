"""Configuración modular. Reexporta la configuración aprobada sin duplicarla."""
from config.qa_config import AZURE_COLUMNS, EXCEL_CONFIGS, MATRIZ_COLUMNS

APP_VERSION = "V43-CAMPOS-REQUERIDOS-AZURE"
DEFAULT_PROVIDER = "gemini"
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
PROVIDERS = {"gemini": {"secret_name": "GEMINI_API_KEY"}}
DEBUG = False
