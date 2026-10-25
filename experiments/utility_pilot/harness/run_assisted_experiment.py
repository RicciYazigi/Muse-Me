"""Arnés Asistido Real con Compuertas e Inserción Win32.

Ejecuta el recorrido completo para medir utilidad:
1. Selección de contexto (A: Ventana sola, B: ContextBuilder, C: Selección humana).
   Aplica el mismo presupuesto de contexto a B y C (max_chars = 2500).
2. Compuerta 1: Aprobación formal de transferencia de paquete (prueba automatizada).
3. Exportación de misión estructurada auditada (request.json, prompt.md).
4. Espera e importación estricta de la propuesta independiente (response.json).
   - En modo estricto, la respuesta debe llegar vinculada con su mission_id y hashes exactos.
   - En modo --fixture-autofill, se permite adaptación para muestras pregrabadas.
5. Compuerta 2: Aprobación de inserción sobre borrador registrado.
6. Inserción Win32 en control nativo EDIT (WM_SETTEXT) y readback verificado (WM_GETTEXT).
7. Consumo atómico en SQLite y prevención de repetición.
8. Limpieza garantizada del control Win32 mediante host.stop().
9. Evaluación independiente desagregada:
   - Coincidencias léxicas (sin suponer acuerdo semántico).
   - Verificación estricta de citas contra allowed_sources autorizadas.
   - Respaldo semántico y corrección (suite pytest independiente en sandbox).
   - Detección de fugas de cadenas confidenciales.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
MUSE_SRC_DIR = EXPERIMENTS_DIR.parent.parent / "src"
sys.path.insert(0, str(EXPERIMENTS_DIR / "evaluation"))
sys.path.insert(0, str(MUSE_SRC_DIR))

import evaluator
from muse_env.store import digest, EventStore
from muse_env.events import ObservationEvent
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.episodes import build_episodes
from muse_env.invoke import approve_transfer, approve_insertion, insert_reply, prepare_reply, FakeSurface
from muse_env.operators.antigravity import AntigravityAssistedOperator
from muse_env.operators.contract import MissionRequest

if sys.platform == "win32":
    from muse_env.surfaces.test_host import Win32TestHost
    from muse_env.surfaces.win32_control import Win32ControlSurface
    from muse_env.surfaces.base import TargetDestination
else:
    Win32TestHost = None
    Win32ControlSurface = None
    TargetDestination = None


MAX_CONTEXT_BUDGET_CHARS = 2500


def load_task_sources() -> dict[str, str]:
    sources_dir = EXPERIMENTS_DIR / "task_definition" / "sources"
    return {
        "target_editor": (sources_dir / "window_target_editor.txt").read_text(encoding="utf-8"),
        "spec_v24": (sources_dir / "window_spec_v24.txt").read_text(encoding="utf-8"),
        "spec_v10_outdated": (sources_dir / "window_spec_v10_outdated.txt").read_text(encoding="utf-8"),
        "private_notes_restricted": (sources_dir / "window_private_notes.txt").read_text(encoding="utf-8"),
    }


def get_target_surface(work_dir: Path, use_native_win32: bool = True):
    """Inicializa la superficie de destino para inserción (Win32 real o FakeSurface si no-Windows)."""
    if sys.platform == "win32" and use_native_win32 and Win32TestHost is not None:
        status_file = work_dir / "test_target_status.json"
        host = Win32TestHost(status_file=status_file, title="Editor-Destino-OrderDiscounts").start()
        dest = TargetDestination(
            application_name="Editor-Python",
            window_id=f"HWND-0x{host.hwnd:08X}",
            process_name="python.exe",
            control_id=f"CTRL-0x{host.hwnd:08X}",
            is_external=True,
            title="Editor-Destino-OrderDiscounts",
        )
        surface = Win32ControlSurface(dest, hwnd=host.hwnd)
        surface._host_handle = host
        return surface
    else:
        surface = FakeSurface("Editor-Python", is_external=True, target_id="target-editor-sandbox")
        surface.hwnd = 9999
        return surface


def run_assisted_condition(
    condition_id: str,
    sources: dict[str, str],
    work_dir: Path,
    response_json_path: Path | None = None,
    interactive_human: bool = False,
    wait_operator: bool = False,
    timeout_seconds: float = 120.0,
    allow_fixture_autofill: bool = False,
    fresh: bool = False,
) -> dict[str, Any]:
    """Ejecuta una condición completa mediante el transporte asistido y compuertas reales."""
    work_dir.mkdir(parents=True, exist_ok=True)
    t_pipeline_start = time.time()
    session_file = work_dir / "session_state.json"
    db_file = work_dir / "events.sqlite"

    # Métricas humanas: estrictamente null salvo que una persona física haya interactuado en Condición C
    human_action_count = None
    t_human_total = None

    # Detectar si podemos reanudar una sesión existente para mantener continuidad de misión
    can_resume = (not fresh) and session_file.exists() and db_file.exists()

    if can_resume:
        session_info = json.loads(session_file.read_text(encoding="utf-8"))
        store = EventStore(str(db_file))
        package = session_info["package"]
        context_sources_used = session_info["context_sources_used"]
        excluded_sources = session_info["excluded_sources"]
        context_chars = session_info["context_chars"]
        resumed_mission_id = session_info["mission_id"]
    else:
        if db_file.exists():
            db_file.unlink()
        if session_file.exists():
            session_file.unlink()
        store = EventStore(str(db_file))
        resumed_mission_id = None

    target_surface = get_target_surface(work_dir)

    try:
        if not can_resume:
            t_base = 1000.0
            # Registrar ventana de destino actual
            store.add(ObservationEvent(
                kind="content_observed",
                application="Editor-Python",
                content=sources["target_editor"],
                permission_scope="may_transfer",
                source_type="windows_read_only",
                ts=t_base
            ))

            if condition_id == "A":
                # Condición A: Ventana sola (max_additional=0)
                episodes = build_episodes(store.all())
                builder = ContextBuilder(max_additional=0, max_chars=MAX_CONTEXT_BUDGET_CHARS)
                package = builder.build(
                    action="reply_with_muse",
                    target_application="Editor-Python",
                    current_content=sources["target_editor"],
                    episodes=episodes,
                    target_is_external=True
                )
                package["package_hash"] = digest(package)
                context_sources_used = []
                excluded_sources = []
                context_chars = 0

            elif condition_id == "B":
                # Condición B: Selección automática ContextBuilder con las 3 fuentes
                store.add(ObservationEvent(
                    kind="content_observed",
                    application="Docs-Tecnicos-v24",
                    content=sources["spec_v24"],
                    permission_scope="may_transfer",
                    source_type="windows_read_only",
                    ts=t_base - 10.0
                ))
                store.add(ObservationEvent(
                    kind="content_observed",
                    application="Docs-Obsoletos-v10",
                    content=sources["spec_v10_outdated"],
                    permission_scope="may_transfer",
                    source_type="windows_read_only",
                    ts=t_base - 20.0
                ))
                store.add(ObservationEvent(
                    kind="content_observed",
                    application="Notas-Privadas-Infra",
                    content=sources["private_notes_restricted"],
                    permission_scope="restricted",
                    source_type="windows_read_only",
                    ts=t_base - 5.0
                ))

                episodes = build_episodes(store.all())
                builder = ContextBuilder(max_additional=4, max_chars=MAX_CONTEXT_BUDGET_CHARS)
                package = builder.build(
                    action="reply_with_muse",
                    target_application="Editor-Python",
                    current_content=sources["target_editor"],
                    episodes=episodes,
                    target_is_external=True
                )
                package["package_hash"] = digest(package)
                context_sources_used = [c["app"] for c in package["additional_context"]]
                excluded_sources = [e["app"] for e in package["excluded_context"]]
                context_chars = sum(len(c["content"]) for c in package["additional_context"])

            elif condition_id == "C":
                # Condición C: Selección humana manual
                if interactive_human:
                    print(f"\n[Condición C - Humana] Fuentes disponibles (presupuesto: {MAX_CONTEXT_BUDGET_CHARS} caracteres).")
                    print("Pega el fragmento de texto seleccionado y presiona ENTER dos veces:")
                    t_gather_start = time.time()
                    lines = []
                    while True:
                        line = input()
                        if not line.strip() and lines:
                            break
                        lines.append(line)
                    selected_text = "\n".join(lines)[:MAX_CONTEXT_BUDGET_CHARS]
                    human_action_count = 1  # 1 acción real del operador: selección y pegado
                    t_human_total = round(time.time() - t_gather_start, 3)
                else:
                    selected_text = sources["spec_v24"][:MAX_CONTEXT_BUDGET_CHARS]
                    human_action_count = None
                    t_human_total = None

                context_sources_used = ["Docs-Tecnicos-v24"]
                excluded_sources = []
                context_chars = len(selected_text)

                store.add(ObservationEvent(
                    kind="content_observed",
                    application="Docs-Tecnicos-v24",
                    content=selected_text,
                    permission_scope="may_transfer",
                    source_type="windows_read_only",
                    ts=t_base - 1.0
                ))
                episodes = build_episodes(store.all())
                builder = ContextBuilder(max_additional=1, max_chars=MAX_CONTEXT_BUDGET_CHARS)
                package = builder.build(
                    action="reply_with_muse",
                    target_application="Editor-Python",
                    current_content=sources["target_editor"],
                    episodes=episodes,
                    target_is_external=True
                )
                package["package_hash"] = digest(package)

        # 2. COMPUERTA 1: Autorización de transferencia (automatizada para prueba de arnés)
        operator = AntigravityAssistedOperator(store=store)
        transfer_approval = approve_transfer(package=package, provider=operator, actor="arnes_prueba (automatica)")
        
        mission_dir = work_dir / "mission"
        mission_dir.mkdir(parents=True, exist_ok=True)
        
        if can_resume:
            req_file = mission_dir / resumed_mission_id / "request.json"
            req_data = json.loads(req_file.read_text(encoding="utf-8"))
            mission_request = MissionRequest(**req_data)
        else:
            mission_request = operator.create_mission_request(
                package=package,
                surface=target_surface,
                task="Corregir bug en order_discounts.py aplicando especificación técnica autorizada"
            )
            operator.export_mission(mission_request, mission_dir, store=store, transfer_approval=transfer_approval, package=package)
            session_state = {
                "mission_id": mission_request.mission_id,
                "condition_id": condition_id,
                "package": package,
                "context_sources_used": context_sources_used,
                "excluded_sources": excluded_sources,
                "context_chars": context_chars,
                "package_hash": mission_request.package_hash,
                "payload_hash": mission_request.payload_hash,
                "allowed_sources": mission_request.allowed_sources,
            }
            session_file.write_text(json.dumps(session_state, indent=2, ensure_ascii=False), encoding="utf-8")

        t_exported = time.time()

        # 3. TRANSPORTE ASISTIDO: Espera o importación estricta de la propuesta
        mission_subdir = mission_dir / mission_request.mission_id
        resp_file = mission_subdir / "response.json"
        model_latency = None

        if response_json_path and response_json_path.exists():
            resp_raw = response_json_path.read_text(encoding="utf-8")
            if allow_fixture_autofill:
                # Modo fixture permisivo: únicamente para pruebas de integración con muestras sintéticas
                try:
                    resp_data = json.loads(resp_raw)
                except Exception:
                    resp_data = {"text": resp_raw, "citations": []}
                app_to_event = {
                    item["app"]: item["source"]
                    for item in [package["current_context"], *package.get("additional_context", [])]
                    if "app" in item and "source" in item
                }
                if "citations" in resp_data and isinstance(resp_data["citations"], list):
                    resp_data["citations"] = [app_to_event.get(c, c) for c in resp_data["citations"]]
                if not resp_data.get("mission_id"):
                    resp_data["mission_id"] = mission_request.mission_id
                if not resp_data.get("request_hash"):
                    resp_data["request_hash"] = mission_request.digest
                if not resp_data.get("payload_hash"):
                    resp_data["payload_hash"] = mission_request.payload_hash
                resp_file.write_text(json.dumps(resp_data, indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                # Modo estricto para operador independiente: la propuesta debe llegar vinculada exactamente
                resp_file.write_text(resp_raw, encoding="utf-8")
            model_latency = None

        elif wait_operator:
            print(f"\nMisión exportada para condición {condition_id}:")
            print(f"  Request:  {mission_subdir / 'request.json'}")
            print(f"  Prompt:   {mission_subdir / 'prompt.md'}")
            print(f"Esperando que el operador genere {resp_file}...")
            while not resp_file.exists() and (time.time() - t_exported) < timeout_seconds:
                time.sleep(0.5)
            if resp_file.exists():
                model_latency = round(time.time() - t_exported, 3)
            else:
                return {
                    "condition": condition_id,
                    "status": "timeout_waiting_response",
                    "mission_id": mission_request.mission_id,
                    "mission_dir": str(mission_subdir),
                    "message": f"Tiempo de espera agotado ({timeout_seconds}s) sin response.json"
                }
        else:
            if not resp_file.exists():
                return {
                    "condition": condition_id,
                    "status": "mission_exported_waiting_response",
                    "mission_id": mission_request.mission_id,
                    "mission_dir": str(mission_subdir),
                    "allowed_sources": mission_request.allowed_sources,
                    "package_hash": mission_request.package_hash,
                    "payload_hash": mission_request.payload_hash,
                    "context_sources_used": context_sources_used,
                    "excluded_sources": excluded_sources,
                    "context_chars_count": context_chars,
                }

        # 4. IMPORTACIÓN Y VALIDACIÓN CONTRA LEDGER
        try:
            proposal = operator.import_proposal(
                resp_file,
                mission_request,
                store=store
            )
        except Exception as exc:
            return {
                "condition": f"{condition_id}_asistida",
                "status": "proposal_rejected",
                "reason": str(exc),
                "mission_id": mission_request.mission_id,
                "eval_correctness": False,
                "readback_verified": False,
                "action_count": human_action_count,
                "human_time_seconds": t_human_total,
                "model_wait_seconds": model_latency,
                "total_elapsed_seconds": None,
            }

        # Generar borrador auditable
        prepared = prepare_reply(
            store=store,
            package=package,
            provider=operator,
            surface=target_surface,
            transfer_approval=transfer_approval
        )
        if prepared.get("status") != "draft_ready":
            raise ValueError(f"Fallo al preparar borrador: {prepared.get('status')} - {prepared.get('reason')}")
        draft = prepared["draft"]

        # 5. COMPUERTA 2: Aprobación de inserción exacta (automatizada para prueba)
        insertion_approval = approve_insertion(draft, actor="arnes_prueba (automatica)")

        # 6. INSERCIÓN WIN32 NATIVA Y READBACK WM_GETTEXT
        delivery_res = insert_reply(
            store=store,
            draft=draft,
            surface=target_surface,
            approval=insertion_approval
        )
        
        insertion_confirmed = (delivery_res.get("status") == "inserted_not_sent")
        readback_verified = target_surface.verify_inserted(draft["text"]) if insertion_confirmed else False

        # Verificar consumo atómico en SQLite
        mission_record = store.get_mission(mission_request.mission_id)
        mission_consumed = bool(mission_record and mission_record.get("state") == "consumed")

        total_elapsed = round(time.time() - t_pipeline_start, 3) if t_human_total is not None else None

        # 7. EVALUACIÓN INDEPENDIENTE Y DESAGREGADA
        eval_corr = evaluator.evaluate_code_correctness(draft["text"])
        eval_leak = evaluator.evaluate_leak(draft["text"] + json.dumps(package))
        
        allowed_citation_ids = list(mission_request.allowed_sources) + [
            c["app"] for c in package.get("additional_context", [])
        ]
        if "current_context" in package and "app" in package["current_context"]:
            allowed_citation_ids.append(package["current_context"]["app"])

        eval_citations = evaluator.evaluate_citations_and_claims(
            proposal_text=draft["text"],
            citations=draft.get("citations", []),
            allowed_sources=allowed_citation_ids
        )

        outcome = {
            "condition": f"{condition_id}_asistida",
            "mission_id": mission_request.mission_id,
            "transport": "antigravity_assisted_operator (intercambio estructurado de archivos)",
            "context_sources_used": context_sources_used,
            "excluded_sources": excluded_sources,
            "context_chars_count": context_chars,
            "action_count": human_action_count,
            "human_time_seconds": t_human_total,
            "model_wait_seconds": model_latency,
            "total_elapsed_seconds": total_elapsed,
            # Métricas de ejecución real Win32 y compuertas
            "transfer_approved": True,
            "insertion_approved": True,
            "gate_approval_mode": "automatica_arnes_prueba",
            "delivery_status": delivery_res.get("status"),
            "readback_verified": readback_verified,
            "mission_consumed_sqlite": mission_consumed,
            # Métricas de evaluación independiente
            "eval_correctness": eval_corr["tests_passed"],
            "eval_leak_detected": eval_leak["leak_detected"],
            "coincidencias_lexicas": eval_citations["coincidencias_lexicas"],
            "verificacion_citas": eval_citations["verificacion_citas"],
            "draft_text_preview": draft["text"][:120] + "...",
            "test_suite_output": eval_corr.get("test_output", ""),
        }

        (work_dir / "outcome_report.json").write_text(json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8")
        return outcome

    finally:
        # Limpieza estricta: detener el proceso del host Win32 mediante stop()
        if hasattr(target_surface, "_host_handle") and target_surface._host_handle:
            try:
                target_surface._host_handle.stop()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Arnés Asistido con Operador Real e Inserción Win32")
    parser.add_argument("--condition", choices=["A", "B", "C", "ALL"], default="ALL", help="Condición a ejecutar")
    parser.add_argument("--interactive", action="store_true", help="Interacción humana real para Condición C")
    parser.add_argument("--wait", action="store_true", help="Esperar response.json del operador externo en disco")
    parser.add_argument("--timeout", type=float, default=120.0, help="Segundos de espera máxima en modo --wait")
    parser.add_argument("--fresh", action="store_true", help="Forzar creación de nueva misión descartando sesión previa")
    parser.add_argument("--fixture-autofill", action="store_true", help="Permitir autocompletado de hashes para muestras sintéticas de fixture")
    parser.add_argument("--run-dir", type=Path, help="Directorio raíz para la corrida (por defecto runs/case_01_assisted)")
    parser.add_argument("--response-a", type=Path, help="Ruta al archivo response.json para condición A")
    parser.add_argument("--response-b", type=Path, help="Ruta al archivo response.json para condición B")
    parser.add_argument("--response-c", type=Path, help="Ruta al archivo response.json para condición C")
    args = parser.parse_args()

    sources = load_task_sources()
    runs_dir = args.run_dir or (EXPERIMENTS_DIR / "runs" / "case_01_assisted")
    runs_dir.mkdir(parents=True, exist_ok=True)

    conditions_to_run = ["A", "B", "C"] if args.condition == "ALL" else [args.condition]
    results = {}

    for cond in conditions_to_run:
        print(f"\n=======================================================")
        print(f"  EJECUTANDO CONDICIÓN {cond} (Transporte Asistido Real)")
        print(f"=======================================================")
        cond_dir = runs_dir / f"condition_{cond.lower()}"
        resp_file = getattr(args, f"response_{cond.lower()}", None)
        res = run_assisted_condition(
            condition_id=cond,
            sources=sources,
            work_dir=cond_dir,
            response_json_path=resp_file,
            interactive_human=args.interactive,
            wait_operator=args.wait,
            timeout_seconds=args.timeout,
            allow_fixture_autofill=args.fixture_autofill,
            fresh=args.fresh,
        )
        results[cond] = res
        print(f"Resultado Condición {cond}: Status = {res.get('status', res.get('delivery_status'))}")
        if "eval_correctness" in res:
            print(f"  Readback: {res.get('readback_verified')} | Correctness: {res.get('eval_correctness')}")

    consolidated_path = runs_dir / "consolidated_report.json"
    consolidated_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReporte consolidado guardado en: {consolidated_path}")


if __name__ == "__main__":
    main()
