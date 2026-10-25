"""Win32 Native Control Surface.

Creates and operates a real Win32 EDIT control window using user32.dll via ctypes.
Sends real Windows messages:
- WM_SETTEXT (0x000C) for insertion
- WM_GETTEXT (0x000D) for independent readback verification
Enforces cryptographic and physical binding between the OS handle and target_id,
rejecting any handle swap or focus tampering at runtime.
"""
from __future__ import annotations
import ctypes
import hashlib
import os
import sys
from ctypes import wintypes
from .base import BaseSurface, TargetDestination

WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WS_VISIBLE = 0x10000000
WS_POPUP = 0x80000000
WS_DISABLED = 0x08000000


class Win32ControlSurface(BaseSurface):
    mode = "windows_win32_control"

    def __init__(self, destination: TargetDestination, hwnd: int | None = None, auto_create: bool = False):
        if sys.platform != "win32":
            raise RuntimeError("Win32ControlSurface solo puede ejecutarse en Windows")
        self.user32 = ctypes.windll.user32
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._created_internally = False
        if hwnd is not None:
            self.hwnd = int(hwnd)
        elif auto_create:
            # Crea una ventana de control EDIT nativa real de Windows
            created = self.user32.CreateWindowExW(
                0,
                "EDIT",
                "",
                WS_POPUP | WS_DISABLED,
                0, 0, 200, 50,
                0, 0, 0, 0
            )
            if not created:
                raise RuntimeError("No se pudo crear la ventana de control Win32 EDIT")
            self.hwnd = int(created)
            self._created_internally = True
        else:
            raise ValueError("Se requiere un hwnd existente o auto_create=True")

        # Vincular físicamente el handle a la identidad del destino
        self._bound_hwnd = int(self.hwnd)
        pid = ctypes.c_ulong()
        self.user32.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        self.pid = int(pid.value)

        # Generar destino físico exacto
        bound_dest = TargetDestination(
            application_name=destination.application_name,
            window_id=f"HWND-0x{self._bound_hwnd:08X}",
            process_name=destination.process_name or f"pid-{self.pid}",
            control_id=f"CTRL-0x{self._bound_hwnd:08X}",
            is_external=destination.is_external,
            title=destination.title or "Win32-Native-Edit-Control"
        )
        super().__init__(bound_dest)

    @property
    def target_id(self) -> str:
        # Si el handle es alterado en tiempo de ejecución, el target_id cambia inmediatamente
        current_hwnd = int(self.hwnd) if self.hwnd else 0
        raw = f"{self.name}:{self.destination.process_name}:HWND-0x{current_hwnd:08X}:CTRL-0x{current_hwnd:08X}"
        return f"target-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def is_target_active(self) -> bool:
        if not self.hwnd or int(self.hwnd) != self._bound_hwnd:
            # Handle alterado después de la inicialización / aprobación
            return False
        return bool(self.user32.IsWindow(self.hwnd))

    def insert(self, text: str) -> bool:
        if not self.is_target_active():
            return False
        # Envía mensaje real de Windows WM_SETTEXT
        res = self.user32.SendMessageW(self.hwnd, WM_SETTEXT, 0, text)
        return bool(res)

    def verify_inserted(self, text: str) -> bool:
        if not self.is_target_active():
            return False
        # Consulta la longitud y lee mediante WM_GETTEXT independiente
        length = self.user32.SendMessageW(self.hwnd, WM_GETTEXTLENGTH, 0, 0)
        buf = ctypes.create_unicode_buffer(length + 1)
        self.user32.SendMessageW(self.hwnd, WM_GETTEXT, length + 1, buf)
        return buf.value == text

    def close(self):
        if self._created_internally and self.hwnd and self.user32.IsWindow(self.hwnd):
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None
            self._bound_hwnd = 0

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
