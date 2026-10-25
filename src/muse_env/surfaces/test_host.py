"""Manager for persistent Win32 test host processes.

Provides a clean programmatic API to spawn, query, and cleanly stop the persistent Win32 EDIT control host.
"""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .base import TargetDestination


class Win32TestHost:
    def __init__(self, status_file: Path | str | None = None, title: str = "MuseWin32TestControl"):
        self.status_file = Path(status_file).resolve() if status_file else None
        self.title = title
        self.proc: subprocess.Popen | None = None
        self.hwnd: int = 0
        self.pid: int = 0
        self.destination: TargetDestination | None = None

    def start(self, timeout: float = 5.0, detached: bool = False) -> Win32TestHost:
        if sys.platform != "win32":
            raise RuntimeError("Win32TestHost solo puede ejecutarse en Windows")

        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [ctypes.wintypes.HWND]
        user32.IsWindow.restype = ctypes.wintypes.BOOL
        # Si ya hay un host corriendo con el status_file y la ventana sigue viva, reutilizarlo
        if self.status_file and self.status_file.exists():
            try:
                info = json.loads(self.status_file.read_text(encoding="utf-8"))
                hwnd = int(info.get("hwnd", 0))
                if hwnd and user32.IsWindow(hwnd):
                    self.hwnd = hwnd
                    self.pid = int(info.get("pid", 0))
                    self._build_destination()
                    return self
            except Exception:
                pass

        script = Path(__file__).resolve().parents[3] / "scripts" / "win32_test_host.py"
        cmd = [sys.executable, "-u", str(script), "--title", self.title]
        if self.status_file:
            cmd.extend(["--status-file", str(self.status_file)])

        if detached:
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            self.proc = subprocess.Popen(
                cmd,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

        # Esperar la línea de inicio o el status_file
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not detached and self.proc and self.proc.poll() is not None:
                err = self.proc.stderr.read() if self.proc.stderr else ""
                raise RuntimeError(f"El proceso de test host terminó prematuramente: {err}")

            if self.status_file and self.status_file.exists():
                try:
                    info = json.loads(self.status_file.read_text(encoding="utf-8"))
                    hwnd = int(info.get("hwnd", 0))
                    if hwnd and ctypes.windll.user32.IsWindow(hwnd):
                        self.hwnd = hwnd
                        self.pid = int(info.get("pid", self.proc.pid if self.proc else 0))
                        self._build_destination()
                        return self
                except Exception:
                    pass

            if not detached and self.proc and self.proc.stdout:
                line = self.proc.stdout.readline()
                if "WIN32_TEST_HOST_READY" in line:
                    for part in line.strip().split():
                        if part.startswith("HWND="):
                            self.hwnd = int(part.split("=")[1])
                        elif part.startswith("PID="):
                            self.pid = int(part.split("=")[1])
                    if self.hwnd:
                        self._build_destination()
                        return self

            time.sleep(0.05)

        raise TimeoutError("Tiempo de espera agotado iniciando Win32TestHost")

    def _build_destination(self):
        self.destination = TargetDestination(
            application_name="Win32TestHost",
            window_id=f"HWND-0x{self.hwnd:08X}",
            process_name="python.exe",
            control_id=f"CTRL-0x{self.hwnd:08X}",
            is_external=True,
            title=self.title
        )

    def is_alive(self) -> bool:
        if not self.hwnd:
            return False
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [ctypes.wintypes.HWND]
        user32.IsWindow.restype = ctypes.wintypes.BOOL
        return bool(user32.IsWindow(self.hwnd))

    def stop(self, timeout: float = 3.0):
        if self.hwnd and ctypes.windll.user32.IsWindow(self.hwnd):
            WM_CLOSE = 0x0010
            ctypes.windll.user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=1.0)
        elif self.pid and not self.proc:
            try:
                os.kill(self.pid, 9)
            except OSError:
                pass
        if self.status_file and self.status_file.exists():
            try:
                self.status_file.unlink()
            except OSError:
                pass
        self.hwnd = 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
