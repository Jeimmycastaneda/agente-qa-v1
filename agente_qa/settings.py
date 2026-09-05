"""Configuración de Azure DevOps compatible con la arquitectura objetivo."""
from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class AzureDevOpsSettings:
    organization: str
    project: str
    pat_secret_name: str = "AZURE_DEVOPS_PAT"
    enabled: bool = False
    api_version: str = "7.1"


def load_azure_devops_config():
    enabled = os.getenv("AZDO_ENABLED", "false").strip().lower() in {"1", "true", "yes", "si", "sí"}
    return AzureDevOpsSettings(
        organization=os.getenv("AZDO_ORGANIZATION", "").strip(),
        project=os.getenv("AZDO_PROJECT", "").strip(),
        enabled=enabled,
        api_version=os.getenv("AZDO_API_VERSION", "7.1").strip() or "7.1",
    )
