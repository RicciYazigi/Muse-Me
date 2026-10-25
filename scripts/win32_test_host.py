"""Win32 Test Control Host script.

Runs as an independent process holding an EDIT control window.
Maintains a Windows message loop so cross-process WM_SETTEXT and WM_GETTEXT are processed.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_BORDER = 0x00800000
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002


def run_host(status_file: Path | None = None, title: str = "MuseWin32TestControl"):
    if sys.platform != "win32":
        raise RuntimeError("Win32 test host solo está disponible en Windows")

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL

    debug_log = Path("data/host_debug.log")
    debug_log.parent.mkdir(parents=True, exist_ok=True)
    with open(debug_log, "a", encoding="utf-8") as log:
        log.write(f"[{time.time()}] Starting host PID={os.getpid()}\n")

    # Crear ventana de control EDIT nativo
    hwnd = user32.CreateWindowExW(
        0,
        "EDIT",
        title,
        WS_POPUP | WS_VISIBLE | WS_BORDER | ES_MULTILINE | ES_AUTOVSCROLL,
        100, 100, 300, 100,
        0, 0, 0, 0
    )
    if not hwnd:
        err = kernel32.GetLastError()
        with open(debug_log, "a", encoding="utf-8") as log:
            log.write(f"[{time.time()}] CreateWindowExW failed: {err}\n")
        raise RuntimeError(f"Error creando ventana EDIT: {err}")

    pid = os.getpid()
    hwnd_int = int(hwnd)
    info = {
        "hwnd": hwnd_int,
        "pid": pid,
        "title": title,
        "created_at": time.time(),
        "application_name": "Win32TestHost",
        "process_name": "python.exe",
        "control_id": f"CTRL-0x{hwnd_int:08X}",
        "window_id": f"HWND-0x{hwnd_int:08X}"
    }

    if status_file:
        status_file = Path(status_file).resolve()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(info, indent=2), encoding="utf-8")

    print(f"WIN32_TEST_HOST_READY HWND={hwnd_int} PID={pid}", flush=True)
    with open(debug_log, "a", encoding="utf-8") as log:
        log.write(f"[{time.time()}] Window created HWND={hwnd_int}, entering message loop\n")

    # Bucle de mensajes estándar de Windows
    msg = wintypes.MSG()
    try:
        while True:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res == 0:
                with open(debug_log, "a", encoding="utf-8") as log:
                    log.write(f"[{time.time()}] Received WM_QUIT, breaking loop\n")
                break
            if res == -1:
                with open(debug_log, "a", encoding="utf-8") as log:
                    log.write(f"[{time.time()}] GetMessageW returned -1 error={ctypes.GetLastError()}\n")
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except Exception as e:
        with open(debug_log, "a", encoding="utf-8") as log:
            log.write(f"[{time.time()}] Exception in message loop: {e}\n")
    finally:
        with open(debug_log, "a", encoding="utf-8") as log:
            log.write(f"[{time.time()}] Exiting host finally block\n")
        if status_file and status_file.exists():
            try:
                status_file.unlink()
            except OSError:
                pass
        if user32.IsWindow(hwnd):
            user32.DestroyWindow(hwnd)


def stop_host(status_file: Path | None = None):
    if not status_file or not status_file.exists():
        print("No se encontró archivo de estado del host.")
        return
    info = json.loads(status_file.read_text(encoding="utf-8"))
    hwnd = int(info.get("hwnd", 0))
    pid = int(info.get("pid", 0))
    user32 = ctypes.windll.user32
    if hwnd and user32.IsWindow(hwnd):
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        print(f"Mensaje WM_CLOSE enviado al control HWND: {hwnd} (PID: {pid})")
    try:
        status_file.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Win32 Native Test Control Host")
    parser.add_argument("--status-file", type=Path, default=None, help="Archivo donde escribir metadatos del control")
    parser.add_argument("--title", type=str, default="MuseWin32TestControl", help="Título del control")
    parser.add_argument("--stop", action="store_true", help="Detener un host en ejecución según el status-file")
    args = parser.parse_args()
    if args.stop:
        stop_host(status_file=args.status_file)
    else:
        run_host(status_file=args.status_file, title=args.title)
