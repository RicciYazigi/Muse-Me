"""Win32 Read-Only Observer con Autorización Estricta y Política de No Captura.

Observador Windows de solo lectura, con activación explícita (opt-in) y
restricción exclusiva por identidad exacta de control (HWND en allowlist).

Garantías de seguridad arquitectónica:
1. Autorización por identidad exacta: solo se aceptan HWNDs registrados explícitamente.
   No se utiliza el título para inferir o heredar permisos de otros controles.
2. Comprobación previa sin lectura: el observador verifica la autorización antes de
   llamar a GetWindowTextW o WM_GETTEXT. Los controles no autorizados son rechazados
   inmediatamente sin leer sus datos ni su título.
3. Separación de captura y transferencia:
   - capture_allowed (bool): gobierna si está permitido leer y capturar el contenido.
   - permission_scope (str): gobierna si el contenido capturado puede transferirse ("may_transfer", "local-only", "restricted").
   Para fuentes no capturables (capture_allowed=False), el contenido NUNCA se lee del control,
   el evento almacena texto vacío (""), la procedencia registra "NO_CAPTURE_POLICY"
   y no hay texto sensible en memoria, SQLite ni evidencias JSON.
4. Vinculación estricta de procedencia: cada WindowsProvenance incluye el event_id exacto
   del ObservationEvent persistido en el ledger.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
import sys
import time
from uuid import uuid4

from ..events import ObservationEvent

WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class WindowsProvenance:
    event_id: str
    hwnd: int
    pid: int
    process_name: str
    window_title: str
    class_name: str
    control_id: str
    window_id: str
    target_id: str
    capture_allowed: bool = True
    read_method: str = "WM_GETTEXT"
    captured_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuthorizedSurfaceRule:
    application: str
    hwnd: int
    capture_allowed: bool = True
    permission_scope: str = "may_transfer"
    is_external: bool = True
    window_title: str | None = None
    authorized: bool = True


def get_process_name_by_pid(pid: int) -> str:
    """Obtiene el nombre del ejecutable a partir de un PID en Windows."""
    if sys.platform != "win32" or not pid:
        return "unknown"
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return Path(sys.executable).name

    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        success = kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
        if success:
            return Path(buf.value).name
        return Path(sys.executable).name
    except Exception:
        return Path(sys.executable).name
    finally:
        kernel32.CloseHandle(h_proc)


class Win32ReadonlyObserver:
    """Sensor de solo lectura sobre ventanas y controles nativos de Windows con autorización por identidad exacta."""

    source_type = "windows_read_only"

    def __init__(self, opt_in: bool = False):
        self.opt_in = opt_in
        self._rules: dict[int, AuthorizedSurfaceRule] = {}
        self._provenance_records: list[WindowsProvenance] = []

    def activate(self) -> None:
        """Activa explícitamente la capacidad de observación (opt-in del usuario)."""
        self.opt_in = True

    def deactivate(self) -> None:
        """Desactiva la capacidad de observación."""
        self.opt_in = False

    def authorize_surface(
        self,
        application: str,
        hwnd: int,
        capture_allowed: bool = True,
        permission_scope: str = "may_transfer",
        is_external: bool = True,
        window_title: str | None = None,
        authorized: bool = True,
    ) -> None:
        """Registra una superficie autorizada por identidad exacta de HWND."""
        if hwnd is None:
            raise ValueError("La autorización de superficie requiere un HWND exacto")
        rule = AuthorizedSurfaceRule(
            application=application,
            hwnd=int(hwnd),
            capture_allowed=capture_allowed,
            permission_scope=permission_scope,
            is_external=is_external,
            window_title=window_title,
            authorized=authorized,
        )
        self._rules[int(hwnd)] = rule

    def revoke_surface(self, hwnd: int) -> None:
        """Revoca la autorización de una superficie retirándola de las reglas."""
        if hwnd is not None:
            hwnd_int = int(hwnd)
            if hwnd_int in self._rules:
                self._rules[hwnd_int].authorized = False
            else:
                self._rules.pop(hwnd_int, None)

    def is_surface_authorized(self, hwnd: int) -> tuple[bool, AuthorizedSurfaceRule | None]:
        """Comprueba autorización por identidad exacta de HWND sin leer texto ni títulos."""
        hwnd_int = int(hwnd)
        if hwnd_int in self._rules:
            rule = self._rules[hwnd_int]
            return bool(rule.authorized), rule
        return False, None

    def read_control_text(self, hwnd: int) -> str:
        """Lee el texto actual del control mediante WM_GETTEXT (solo lectura nativa)."""
        if sys.platform != "win32":
            raise RuntimeError("La lectura nativa Win32 requiere Windows")
        user32 = ctypes.windll.user32

        length = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
        if length < 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, buf)
        return buf.value

    def observe(self, hwnd: int, kind: str = "content_observed") -> tuple[ObservationEvent, WindowsProvenance]:
        """Realiza una observación de solo lectura respetando la política de captura e identidad exacta.

        Precondición de seguridad:
        - Si no está autorizado el HWND exacto, falla inmediatamente sin leer el texto ni el título.
        - Si la regla prohíbe captura (capture_allowed=False), jamás se lee el texto del control.
        """
        if not self.opt_in:
            raise PermissionError("La observación de Windows requiere activación explícita (opt-in)")

        hwnd_int = int(hwnd)

        # 1. Comprobación estricta de autorización por HWND ANTES de cualquier lectura al OS
        is_auth, rule = self.is_surface_authorized(hwnd_int)
        if not is_auth or not rule:
            raise PermissionError(f"Control HWND {hwnd_int} no está en la lista de superficies autorizadas (allowlist)")

        if sys.platform != "win32":
            raise RuntimeError("Win32 observe requiere Windows")

        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        if not user32.IsWindow(hwnd_int):
            raise ValueError(f"HWND {hwnd_int} no es una ventana activa del sistema")

        # 2. Metadatos estructurales del control y proceso (sin leer contenido de texto)
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        pid_val = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd_int, ctypes.byref(pid_val))
        pid = int(pid_val.value)
        process_name = get_process_name_by_pid(pid)

        buf_class = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd_int, buf_class, 256)
        class_name = buf_class.value

        control_id = f"CTRL-0x{hwnd_int:08X}"
        window_id = f"HWND-0x{hwnd_int:08X}"
        raw = f"{process_name}:{window_id}:{control_id}:{class_name}"
        target_id = f"target-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"
        now = time.time()
        event_id = f"evt-{uuid4().hex}"

        # 3. Política explícita de NO CAPTURA para fuentes sensibles
        if not rule.capture_allowed:
            # NO se invoca WM_GETTEXT ni GetWindowTextW: ausencia total de contenido
            content = ""
            read_method = "NO_CAPTURE_POLICY"
            window_title = rule.window_title or "[REDACTADO_POR_POLITICA_DE_NO_CAPTURA]"
        else:
            # Fuente autorizada para captura de texto
            content = self.read_control_text(hwnd_int)
            read_method = "WM_GETTEXT"
            # En controles EDIT, GetWindowTextW devolvería el contenido del texto,
            # por lo que preservamos la etiqueta asignada o un identificador estructural
            if class_name.lower() == "edit":
                window_title = rule.window_title or f"Win32EditControl[{control_id}]"
            else:
                buf_title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd_int, buf_title, 512)
                window_title = buf_title.value

        provenance = WindowsProvenance(
            event_id=event_id,
            hwnd=hwnd_int,
            pid=pid,
            process_name=process_name,
            window_title=window_title,
            class_name=class_name,
            control_id=control_id,
            window_id=window_id,
            target_id=target_id,
            capture_allowed=rule.capture_allowed,
            read_method=read_method,
            captured_at=now,
        )

        event = ObservationEvent(
            kind=kind,
            application=rule.application,
            content=content,
            epistemic_status="observed",
            permission_scope=rule.permission_scope,
            source_type=self.source_type,
            ts=now,
            event_id=event_id,
        )

        self._provenance_records.append(provenance)
        return event, provenance

    @property
    def provenance_records(self) -> list[WindowsProvenance]:
        return list(self._provenance_records)
