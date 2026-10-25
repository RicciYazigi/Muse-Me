"""Paso 1 del Flujo Asistido Real: Exportar Misión Autorizada.

Ejecuta:
1. Lectura/registro de eventos y construcción de contexto.
2. Comprobación y exclusión de datos restringidos.
3. Creación y vinculación del destino físico real (Win32ControlSurface o VerifiableControlSurface).
4. Autorización de transferencia explícita (previa al despacho de contexto).
5. Exportación estricta de request.json y PROMPT_OPERADOR.md verificando payload derivado.
6. Registro de la misión en el ledger SQLite.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.store import EventStore
from muse_env.events import ObservationEvent
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.invoke import approve_transfer
from muse_env.operators.antigravity import AntigravityAssistedOperator
from muse_env.surfaces.base import TargetDestination
from muse_env.surfaces.win32_control import Win32ControlSurface
from muse_env.surfaces.test_control import VerifiableControlSurface
from muse_env.surfaces.test_host import Win32TestHost


def main():
    parser = argparse.ArgumentParser(description="Exportar Misión para Operador Antigravity (Paso 1)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--actor", type=str, default="operador-humano (autorización de transferencia)")
    parser.add_argument("--use-win32-real", action="store_true", help="Crear y vincular un control EDIT Win32 real en Windows")
    args = parser.parse_args()

    runs_dir = args.output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    db_path = args.output_dir / "assisted_memory.sqlite"

    target_app = "Win32TestHost" if args.use_win32_real else "AppPruebaControl"

    store = EventStore(db_path)
    print(f"=== PASO 1: EXPORTACIÓN DE MISIÓN AUTORIZADA ===")
    print(f"Store SQLite: {db_path}")

    # Registra eventos si el store no tiene observaciones para la aplicación objetivo
    existing_for_target = [e for e in store.all() if e.application == target_app]
    if not existing_for_target:
        events = [
            ObservationEvent(
                kind="content_observed",
                application="VS Code",
                ts=1000.0,
                content="FastAPI endpoint /items lanza 422 Unprocessable Entity al validar el esquema Pydantic",
                permission_scope="may_transfer",
            ),
            ObservationEvent(
                kind="content_observed",
                application="Chrome Docs",
                ts=1010.0,
                content="Documentación FastAPI: el error 422 ocurre si los tipos de query o body no coinciden con el esquema",
                permission_scope="may_transfer",
            ),
            ObservationEvent(
                kind="content_observed",
                application="Notas privadas",
                ts=1020.0,
                content="API_KEY_INTERNA_DE_DESPLIEGUE=sk-secret-prod-998877",
                permission_scope="restricted",
            ),
            ObservationEvent(
                kind="window_focus",
                application=target_app,
                ts=1030.0,
                content="¿Por qué mi endpoint de FastAPI devuelve error 422?",
                permission_scope="may_transfer",
            ),
        ]
        for ev in events:
            store.add(ev)

    events = store.all()
    episodes = build_episodes(events)
    current_ev = [e for e in events if e.application == target_app][-1]

    package = ContextBuilder().build(
        action="reply_with_muse",
        target_application=target_app,
        current_content=current_ev.content,
        episodes=episodes,
        target_is_external=True,
    )

    if args.use_win32_real and sys.platform == "win32":
        status_file = args.output_dir / "win32_test_host.json"
        host = Win32TestHost(status_file=status_file)
        host.start(detached=True)
        surface = Win32ControlSurface(host.destination, hwnd=host.hwnd)
        surface_meta = {
            "type": "win32",
            "hwnd": host.hwnd,
            "pid": host.pid,
            "target_id": surface.target_id,
            "application_name": surface.name,
            "process_name": host.destination.process_name,
            "control_id": host.destination.control_id,
            "window_id": host.destination.window_id,
            "title": host.destination.title,
        }
        print(f"Destino: Control nativo Win32 en host persistente (HWND: {host.hwnd}, PID: {host.pid})")
    else:
        dest = TargetDestination(
            application_name=target_app,
            window_id="HWND-0x002A04E8",
            process_name="app_prueba.exe",
            control_id="draft-input-editor-01",
            is_external=True,
            title="Ventana de Prueba",
        )
        surface = VerifiableControlSurface(dest)
        surface_meta = {
            "type": "test_control",
            "target_id": surface.target_id,
            "application_name": surface.name,
        }
        print(f"Destino: VerifiableControlSurface ({surface.mode})")

    operator = AntigravityAssistedOperator(run_dir=runs_dir, store=store)
    req = operator.create_mission_request(
        package=package,
        surface=surface,
        task="Explicar por qué ocurre el error 422 en FastAPI y cómo corregirlo según las fuentes autorizadas",
    )

    # Autorización de transferencia previa al despacho
    t_approval = approve_transfer(package, operator, actor=args.actor)
    exported = operator.export_mission(req, runs_dir, store=store, package=package, transfer_approval=t_approval)

    # Guardar metadatos de superficie vinculados
    (exported["mission_dir"] / "surface_info.json").write_text(json.dumps(surface_meta, indent=2), encoding="utf-8")
    store.close()

    print(f"\n[OK] Misión creada y exportada:")
    print(f"     ID de Misión : {req.mission_id}")
    print(f"     Request Hash : {req.digest}")
    print(f"     Payload Hash : {req.payload_hash}")
    print(f"     Solicitud    : {exported['request_file']}")
    print(f"     Prompt Guía  : {exported['prompt_file']}")
    print(f"\n---> ACCIÓN ASISTIDA REQUERIDA:")
    print(f"     1. Abra '{exported['prompt_file']}'.")
    print(f"     2. Como Operador Antigravity, genere el archivo 'response.json' en '{exported['mission_dir']}'.")
    print(f"     3. Ejecute: python complete_mission.py --mission-id {req.mission_id}")


if __name__ == "__main__":
    main()
