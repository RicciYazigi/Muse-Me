"""Windows Probe Surface (Read-Only Sensor).

Inspects actual Windows foreground window, title, and process ID using Win32 API via ctypes.
Explicitly rejects insert and verify_inserted operations to prevent false claims of OS writing.
"""
from __future__ import annotations
import ctypes
import os
import sys
from .base import BaseSurface, TargetDestination


def get_windows_foreground_info() -> dict[str, str | int]:
    """Obtiene información de la ventana en primer plano en Windows si está disponible."""
    if sys.platform != "win32":
        return {"available": False, "reason": "not_win32"}
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"available": False, "reason": "no_foreground_window"}
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {
            "available": True,
            "hwnd": int(hwnd),
            "title": buf.value,
            "pid": int(pid.value),
        }
    except Exception as err:
        return {"available": False, "reason": str(err)}


class WindowsProbeSurface(BaseSurface):
    mode = "windows_probe_solo_lectura"

    def __init__(self, destination: TargetDestination, expected_hwnd: int | None = None):
        super().__init__(destination)
        self.expected_hwnd = expected_hwnd

    def is_target_active(self) -> bool:
        info = get_windows_foreground_info()
        if not info.get("available"):
            return False
        if self.expected_hwnd is not None and info.get("hwnd") != self.expected_hwnd:
            return False
        return True

    def insert(self, text: str) -> bool:
        # Honestidad arquitectónica: esta sonda NO finge inserción en el OS
        raise NotImplementedError(
            "WindowsProbeSurface es únicamente un sensor de lectura/foco; no implementa inserción en el OS. "
            "Para inserción verificada, use un adaptador de control real (Win32ControlSurface) o de prueba."
        )

    def verify_inserted(self, text: str) -> bool:
        raise NotImplementedError("WindowsProbeSurface no implementa lectura de inserción.")
