"""Verifiable Test Control Surface.

Simulates a real control buffer with explicit focus state, destination validation, and readback.
Allows testing focus theft (e.g. by overlay HUD) and target alteration before insertion.
"""
from __future__ import annotations
from .base import BaseSurface, TargetDestination


class VerifiableControlSurface(BaseSurface):
    mode = "control_prueba"

    def __init__(self, destination: TargetDestination):
        super().__init__(destination)
        self.buffer = ""
        self._active = True
        self._readback_tampered = False

    def set_active(self, active: bool):
        """Simula pérdida de foco o cambio de ventana en el sistema."""
        self._active = active

    def simulate_tampering(self, tamper: bool = True):
        """Simula que el control fue modificado concurrentemente."""
        self._readback_tampered = tamper

    def is_target_active(self) -> bool:
        return self._active

    def insert(self, text: str) -> bool:
        if not self._active:
            # Ventana o control no activo al momento de la inserción
            return False
        self.buffer = text
        return True

    def verify_inserted(self, text: str) -> bool:
        if not self._active:
            return False
        if self._readback_tampered:
            return False
        return self.buffer == text
