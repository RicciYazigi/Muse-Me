"""Surface contracts: destination identity and verification.

Distinguishes simulated surfaces from real OS control targets.
Enforces that insertion requires target identity revalidation and post-insertion readback.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import hashlib
import json
from uuid import uuid4


@dataclass(frozen=True)
class TargetDestination:
    application_name: str
    window_id: str
    process_name: str
    control_id: str
    is_external: bool = True
    title: str = ""

    def __post_init__(self):
        if not self.application_name or not self.window_id or not self.control_id:
            raise ValueError("application_name, window_id y control_id son obligatorios")

    @property
    def target_id(self) -> str:
        # Genera un ID unívoco y determinista para este control específico
        raw = f"{self.application_name}:{self.process_name}:{self.window_id}:{self.control_id}"
        return f"target-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def to_dict(self) -> dict:
        return asdict(self)


class BaseSurface:
    """Contrato base para todas las superficies."""
    mode: str = "base"

    def __init__(self, destination: TargetDestination):
        self.destination = destination
        self.name = destination.application_name
        self.is_external = destination.is_external

    @property
    def target_id(self) -> str:
        return self.destination.target_id

    def is_target_active(self) -> bool:
        """Comprueba si el destino (ventana y control) sigue activo antes de insertar."""
        raise NotImplementedError

    def insert(self, text: str) -> bool:
        """Inserta texto en el control de destino."""
        raise NotImplementedError

    def verify_inserted(self, text: str) -> bool:
        """Verifica mediante lectura directa (readback) que el texto en el control coincide."""
        raise NotImplementedError
