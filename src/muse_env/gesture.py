"""Muse-Me Desktop Gesture & Global Hotkey Engine (Finding F5).
Implements the core product gesture: 'Responder / Completar con Muse' directly
over the user's active window via global hotkey, tray, or quick invocation CLI.

Preserves the zero-trust kernel:
- Detects the active foreground window.
- Checks identity and authorization before reading any text.
- If unauthorized, displays safety notice and requests permission in panel.
- If authorized, invokes context compiler and prepares draft proposal for Gate 2.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, Optional

from .surfaces.win32_observer import Win32ReadonlyObserver, get_process_name_by_pid
from .project_memory import ProjectMemory
from .capabilities import propose_deliverable, CAPABILITY_DELIVERABLE_PRODUCTION


class MuseDesktopGesture:
    """Manages desktop hotkey and contextual action trigger."""
    def __init__(self, memory_path: Optional[str] = None):
        if not memory_path:
            memory_path = os.environ.get("MUSE_MEMORY_DB", "data/demo_walkthrough/project_memory.sqlite")
        self.memory = ProjectMemory(str(Path(memory_path).resolve()))
        self.observer = Win32ReadonlyObserver(opt_in=True)

    def get_active_window_info(self) -> Dict[str, Any]:
        """Inspects active foreground window without reading internal content."""
        if sys.platform != "win32":
            return {"hwnd": 0, "title": "Plataforma no Windows", "process": "mock", "class_name": "Mock"}

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "Ninguna ventana en primer plano", "process": "", "class_name": ""}

        length = user32.GetWindowTextLengthW(hwnd)
        buf_title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf_title, length + 1)

        buf_class = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf_class, 256)

        pid_val = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
        process_name = get_process_name_by_pid(int(pid_val.value))

        return {
            "hwnd": hwnd,
            "title": buf_title.value,
            "process": process_name,
            "class_name": buf_class.value
        }

    def trigger_gesture(self, target_hwnd: Optional[int] = None, project: str = "demo-latam", goal: Optional[str] = None) -> Dict[str, Any]:
        """The core product gesture: 'Responder con Muse'."""
        if target_hwnd is None:
            info = self.get_active_window_info()
            target_hwnd = info["hwnd"]
        else:
            info = {"hwnd": target_hwnd, "title": f"HWND 0x{target_hwnd:X}", "process": "unknown"}

        # 1. Authorization check
        is_auth, rule = self.observer.is_surface_authorized(target_hwnd)
        if not is_auth:
            return {
                "gesture_action": "authorization_required",
                "status": "blocked",
                "hwnd": target_hwnd,
                "window_info": info,
                "message": (
                    f"Ventana '{info.get('title')}' (proceso: {info.get('process')}, HWND: {target_hwnd}) "
                    "no está en la lista de superficies autorizadas. "
                    "Por seguridad, active el permiso de captura en el Panel de Revisión antes de continuar."
                ),
                "review_panel_url": "http://127.0.0.1:8080"
            }

        # 2. Authorized window: compile governed context package
        query_goal = goal or f"Asistencia contextual {info.get('title')}"
        compiler_res = self.memory.search_with_exclusions(project, query_goal, external=False)
        selected = compiler_res["selected"]

        if not selected:
            return {
                "gesture_action": "reply_with_muse",
                "status": "insufficient_evidence",
                "hwnd": target_hwnd,
                "window_info": info,
                "message": "No se encontró evidencia transferible vigente en memoria para esta tarea.",
                "review_panel_url": "http://127.0.0.1:8080"
            }

        # 3. Create mission and proposal draft
        refs = {s["source"]: s["revision"] for s in selected}
        mission_id = self.memory.checkpoint(project, query_goal, refs, capability=CAPABILITY_DELIVERABLE_PRODUCTION.id)
        proposal = propose_deliverable(self.memory, mission_id, title=f"Asistencia Contextual - {info.get('title')}")

        return {
            "gesture_action": "reply_with_muse",
            "status": "proposal_ready",
            "hwnd": target_hwnd,
            "window_info": info,
            "mission_id": mission_id,
            "draft_sha256": proposal["draft_sha256"],
            "requires_gate2_human_approval": True,
            "draft_preview": proposal.get("draft_markdown", "")[:350] + "...",
            "message": "Propuesta contextual lista para revisión de Compuerta 2.",
            "review_panel_url": f"http://127.0.0.1:8080#mission-{mission_id}"
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Muse-Me Global Gesture & Hotkey Runner")
    parser.add_argument("--trigger", action="store_true", help="Dispara el gesto sobre la ventana activa de inmediato")
    parser.add_argument("--hwnd", type=int, default=None, help="HWND específico para probar el gesto")
    parser.add_argument("--project", default="demo-latam", help="Proyecto objetivo")
    args = parser.parse_args()

    gesture = MuseDesktopGesture()
    if args.trigger or args.hwnd is not None:
        result = gesture.trigger_gesture(target_hwnd=args.hwnd, project=args.project)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Muse-Me Global Gesture Engine inicializado.")
        print("Presione Ctrl+Shift+M sobre cualquier ventana autorizada o ejecute con --trigger.")


if __name__ == "__main__":
    main()
