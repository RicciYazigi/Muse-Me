"""Flujo End-to-End asistido con Operador Antigravity y Superficie Verificable.

Demuestra:
1. Observación de eventos con fuentes restringidas (secreto excluido por política).
2. Construcción de paquete autorizado y payload mínimo.
3. Exportación de solicitud de misión (request.json + PROMPT_OPERADOR.md).
4. Generación e importación de respuesta estructurada del Operador Antigravity (asistido).
5. Doble aprobación humana (transferencia de contexto e inserción de borrador).
6. Inserción con validación de destino, control activo y comprobación de lectura (readback).
7. Verificación criptográfica del ledger SHA-256 en SQLite.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.store import EventStore, digest
from muse_env.events import ObservationEvent
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.invoke import prepare_reply, insert_reply, approve_transfer, approve_insertion
from muse_env.operators.antigravity import AntigravityAssistedOperator
from muse_env.operators.contract import OperatorProposal
from muse_env.surfaces.base import TargetDestination
from muse_env.surfaces.test_control import VerifiableControlSurface
from muse_env.surfaces.win32_control import Win32ControlSurface


def main():
    parser = argparse.ArgumentParser(description="Demo Flujo Asistido Operador Antigravity")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--use-win32-real", action="store_true", help="Usar control EDIT Win32 nativo real en Windows")
    args = parser.parse_args()

    runs_dir = args.output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    db_path = args.output_dir / "demo_antigravity.sqlite"

    print("================================================================================")
    print("MUSE ENVIRONMENT — FLUJO END-TO-END CON OPERADOR ANTIGRAVITY (ASISTIDO)")
    print("================================================================================")

    store = EventStore(db_path)
    print(f"[1/7] Store inicializado en: {db_path}")

    # 1. Registrar eventos observados (incluyendo material sensible que JAMÁS debe salir)
    target_app = "Win32TestHost" if args.use_win32_real else "Slack Dev"
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
            permission_scope="restricted",  # CONFIDENCIAL: Nunca debe ser transferido
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
    print(f"      {len(events)} eventos registrados (incluyendo fuente 'restricted' confidencial).")

    # 2. Context Builder y comprobación de exclusiones
    episodes = build_episodes(store.all())
    package = ContextBuilder().build(
        action="reply_with_muse",
        target_application=target_app,
        current_content=events[-1].content,
        episodes=episodes,
        target_is_external=True,
    )

    outbound = provider_payload(package)
    has_secret = "API_KEY_INTERNA" in json.dumps(outbound)
    print(f"[2/7] Contexto construido:")
    print(f"      - Fuentes seleccionadas: {[item['app'] for item in package['additional_context']]}")
    print(f"      - Exclusiones de seguridad: {[ex['reason'] for ex in package['excluded_context']]}")
    print(f"      - ¿Fuga de secretos en outbound payload?: {'SÍ (FALLO GRAVE)' if has_secret else 'NO (EXCLUIDO CORRECTAMENTE)'}")
    if has_secret:
        raise RuntimeError("Fuga de seguridad detectada en el payload saliente")

    # 3. Identificación del Control de Destino
    if args.use_win32_real and sys.platform == "win32":
        temp_dest = TargetDestination(
            application_name=target_app,
            window_id="HWND-PENDING",
            process_name="python.exe",
            control_id="CTRL-PENDING",
            is_external=True,
            title="Control EDIT Nativo Win32 de Prueba",
        )
        surface = Win32ControlSurface(temp_dest, auto_create=True)
        execution_mode = "asistido_win32_real"
        dest = surface.destination
        print(f"[3/7] Superficie de destino identificada (Control nativo Win32 REAL):")
        print(f"      - App: {dest.application_name} | Proceso: {dest.process_name} | HWND: {dest.window_id}")
        print(f"      - Control: {dest.control_id} | Target ID único: {dest.target_id}")
    else:
        dest = TargetDestination(
            application_name=target_app,
            window_id="HWND-0x002A04E8",
            process_name="slack.exe" if not args.use_win32_real else "python.exe",
            control_id="draft-input-editor-01",
            is_external=True,
            title="Canal #desarrollo-backend",
        )
        surface = VerifiableControlSurface(dest)
        execution_mode = "asistido_control_prueba"
        print(f"[3/7] Superficie de destino identificada (Simulación VerifiableControlSurface):")
        print(f"      - App: {dest.application_name} | Proceso: {dest.process_name} | HWND: {dest.window_id}")
        print(f"      - Control: {dest.control_id} | Target ID único: {dest.target_id}")

    # 4. Solicitud al Operador Antigravity y Exportación (con autorización de transferencia previa)
    operator = AntigravityAssistedOperator(run_dir=runs_dir, store=store)
    req = operator.create_mission_request(
        package=package,
        surface=surface,
        task="Generar borrador de respuesta técnica explicando el error 422 basándote únicamente en el código y documentación",
    )
    # Aprobación previa de transferencia requerida por política antes del despacho/exportación
    t_approval = approve_transfer(package, operator, actor="demo-script (aprobación de transferencia)")
    exported = operator.export_mission(req, runs_dir, store=store, package=package, transfer_approval=t_approval)
    print(f"[4/7] Misión exportada para Operador Antigravity (Modo: {execution_mode}):")
    print(f"      - Solicitud JSON: {exported['request_file']}")
    print(f"      - Prompt auditable: {exported['prompt_file']}")

    # 5. Generación de respuesta estructurada del Operador (fixture sintético para la demo)
    res_data = {
        "proposal_id": f"prop-{req.mission_id[-6:]}",
        "mission_id": req.mission_id,
        "request_hash": req.digest,
        "payload_hash": req.payload_hash,
        "text": "El error 422 en FastAPI ocurre porque el esquema Pydantic espera tipos exactos (entero vs cadena) según la documentación.",
        "citations": req.allowed_sources[:2],
        "operator_identity": operator.operator_identity,
        "actions_requested": [],
    }
    res_file = exported["mission_dir"] / "response.json"
    res_file.write_text(json.dumps(res_data, indent=2, ensure_ascii=False), encoding="utf-8")

    proposal = operator.import_proposal(res_file, req, store=store)
    print(f"[5/7] Propuesta importada y validada del Operador:")
    print(f"      - Texto: \"{proposal.text}\"")
    print(f"      - Citas auditadas: {proposal.citations}")
    print(f"      - Vinculación request_hash: {proposal.request_hash[:16]}... (COINCIDE)")

    # 6. Preparación de Borrador e Inserción Controlada
    prep = prepare_reply(
        store=store,
        package=package,
        provider=operator,
        surface=surface,
        transfer_approval=t_approval,
    )
    if prep["status"] != "draft_ready":
        raise RuntimeError(f"Error preparando borrador: {prep}")

    draft = prep["draft"]
    print(f"[6/7] Borrador sellado:")
    print(f"      - Draft ID: {draft['draft_id']}")
    print(f"      - Draft Hash (SHA-256): {digest(draft)}")

    # Paso B: Aprobación explícita de inserción ligada al borrador exacto y control
    ins_approval = approve_insertion(draft, actor="operador-humano (aprobación de inserción en Slack)")
    result = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)

    readback_ok = surface.verify_inserted(draft["text"])
    print(f"      - Resultado de inserción: {result['status']}")
    print(f"      - Comprobación de lectura (readback): {'CORRECTO' if readback_ok else 'FALLO'}")

    # 7. Verificación de Cadena y Reanudación
    chain_valid = store.verify_chain()
    chain_length = len(store.chain())
    store.close()

    # Reabrir para comprobar persistencia
    reopened = EventStore(db_path)
    persisted_ok = reopened.verify_chain()
    reopened.close()

    print(f"[7/7] Integridad criptográfica:")
    print(f"      - Ledger SHA-256 verificado: {chain_valid} ({chain_length} eslabones encadenados)")
    print(f"      - Persistencia tras reapertura: {persisted_ok}")

    # Guardar reporte completo de la misión
    success = (result["status"] == "inserted_not_sent") and (readback_ok is True) and (chain_valid is True)
    summary = {
        "format_version": 2,
        "mode": execution_mode,
        "operator": operator.identity,
        "mission_id": req.mission_id,
        "request_hash": req.digest,
        "package_hash": req.package_hash,
        "payload_hash": req.payload_hash,
        "excluded_sources": package["excluded_context"],
        "destination": dest.to_dict(),
        "proposal": proposal.to_dict(),
        "draft_id": draft["draft_id"],
        "draft_hash": digest(draft),
        "surface": surface.mode,
        "insertion_status": result["status"],
        "readback_verified": readback_ok,
        "chain_valid": chain_valid,
        "chain_length": chain_length,
        "outcome_verified": success,
    }
    report_path = exported["mission_dir"] / "resultado_mision.json"
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReporte de evidencia generado en: {report_path}")

    if hasattr(surface, "close"):
        surface.close()

    if not success:
        print("================================================================================")
        print("VERIFICACIÓN COMPLETA: FALLO (Inserción, readback o integridad no verificada)")
        print("================================================================================")
        return 1

    print("================================================================================")
    print(f"VERIFICACIÓN COMPLETA: ÉXITO (MODO: {execution_mode.upper()} · VERIFICADO)")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
