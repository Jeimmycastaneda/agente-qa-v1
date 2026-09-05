"""Punto de entrada de Agente QA.

Durante la migración a la estructura modular, ``app_legacy.py`` conserva la
interfaz funcional aprobada. Este punto de entrada la ejecuta sin alterar su
orden, textos ni comportamiento visual. Los módulos bajo ``agente_qa/`` se
mantienen como destino de la migración progresiva.

Reglas de trabajo:
- Solo se modifica ``organizar-main``.
- ``main`` es fuente funcional/visual y no se modifica.
- ``mao-dev-branch`` es referencia estructural y no se modifica.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _run_approved_interface() -> None:
    """Ejecuta la interfaz aprobada conservando su comportamiento actual.

    La siguiente etapa de la migración moverá bloques completos de
    ``app_legacy.py`` a los módulos de ``agente_qa/`` sin cambiar la interfaz.
    No se reconstruye ni se simplifica la UI en este punto.
    """
    legacy_path = Path(__file__).with_name("app_legacy.py")
    source = legacy_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(legacy_path))
    code = compile(tree, str(legacy_path), "exec")
    namespace = {
        "__name__": "__main__",
        "__file__": str(legacy_path),
        "__package__": None,
    }
    exec(code, namespace, namespace)


_run_approved_interface()
