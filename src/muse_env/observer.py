# -*- coding: utf-8 -*-
"""Observador. En este entorno (sandbox Linux) la fuente es 'simulated': superficies
controladas que imitan editor/navegador/chat. En Windows, esta misma interfaz se
implementa con pywinauto/UIA (ver docs/ADAPTADORES_WINDOWS.md). La interfaz es el contrato."""
from __future__ import annotations
from .events import ObservationEvent

class SimulatedObserver:
    source_type = "simulated"
    def __init__(self, script: list[dict]): self.script = script
    def stream(self):
        for step in self.script:
            yield ObservationEvent(source_type=self.source_type, **step)

# Escenario del demo: trabajas en un editor (FastAPI), consultas documentación,
# y hay material restringido que JAMÁS debe cruzar al chat externo.
DEMO_SCRIPT = [
    dict(kind="window_focus", application="VS Code", ts=1000.0, content="api.py FastAPI endpoint"),
    dict(kind="content_observed", application="VS Code", ts=1005.0,
         content="FastAPI devuelve 422 porque el esquema Pydantic espera entero y recibe cadena en api.py",
         permission_scope="may_transfer"),
    dict(kind="content_observed", application="Chrome Docs", ts=1100.0,
         content="La documentación de FastAPI indica validar el tipo antes de construir el esquema",
         permission_scope="may_transfer"),
    dict(kind="content_observed", application="Notas privadas", ts=1200.0,
         content="Credencial interna del despliegue y notas personales del proyecto",
         permission_scope="restricted"),
    dict(kind="window_focus", application="Chat externo", ts=1300.0,
         content="¿Por qué FastAPI devuelve 422 en mi endpoint?", permission_scope="may_transfer"),
]
