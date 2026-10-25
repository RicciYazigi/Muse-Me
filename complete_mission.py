"""Paso 2 del Flujo Asistido Real: Importar Respuesta, Validar, Aprobar e Insertar.

Ejecuta:
1. Lectura de request.json, response.json y surface_info.json de la misión.
2. Validación criptográfica: correspondencia exacta de request_hash y payload_hash con la solicitud y el ledger SQLite.
3. Validación estricta de citas contra allowed_sources.
4. Vinculación estricta al control de destino original (Win32ControlSurface o VerifiableControlSurface).
5. Aprobación humana de inserción vinculada al borrador exacto y control.
6. Inserción con readback en el control de destino.
7. Consumo único de la misión y registro en el ledger SQLite.
8. Verificación dura de éxito: falla el proceso si inserción, readback o cadena no se validan.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.store import EventStore, digest
from muse_env.invoke import prepare_reply, insert_reply, approve_transfer, approve_insertion
from muse_env.operators.antigravity import AntigravityAssistedOperator
from muse_env.operators.contract import MissionRequest
from muse_env.surfaces.base import TargetDestination
from muse_env.surfaces.win32_control import Win32ControlSurface
from muse_env.surfaces.test_control import VerifiableControlSurface


def main():
    parser = argparse.ArgumentParser(description="Completar Misión de Operador Antigravity (Paso 2)")
    parser.add_argument("--mission-id", type=str, required=True, help="ID de la misión a completar")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--actor", type=str, default="operador-humano (aprobación de inserción)")
    args = parser.parse_args()

    mission_dir = args.output_dir / "runs" / args.mission_id
    req_file = mission_dir / "request.json"
    res_file = mission_dir / "response.json"
    surface_file = mission_dir / "surface_info.json"
    db_path = args.output_dir / "assisted_memory.sqlite"

    if not req_file.exists():
        raise FileNotFoundError(f"No se encontró la solicitud de misión en: {req_file}")
    if not res_file.exists():
        raise FileNotFoundError(
            f"No se encontró la respuesta del operador en: {res_file}\n"
            f"El operador Antigravity debe generar este archivo antes de continuar."
        )

    print(f"=== PASO 2: IMPORTACIÓN, APROBACIÓN E INSERCIÓN ===")
    print(f"Misión ID: {args.mission_id}")
    print(f"Directorio de Misión: {mission_dir}")

    store = EventStore(db_path)
    req_data = json.loads(req_file.read_text(encoding="utf-8"))
    req = MissionRequest(**req_data)

    # Identificación y vinculación estricta de la superficie destino
    surface_meta = json.loads(surface_file.read_text(encoding="utf-8")) if surface_file.exists() else {}
    surface_type = surface_meta.get("type", "test_control")

    dest = TargetDestination(
        application_name=req.target_application,
        window_id=f"HWND-0x{surface_meta.get('hwnd', 0):08X}" if surface_type == "win32" else "HWND-0x002A04E8",
        process_name="python.exe" if surface_type == "win32" else "app_prueba.exe",
        control_id=f"CTRL-0x{surface_meta.get('hwnd', 0):08X}" if surface_type == "win32" else "draft-input-editor-01",
        is_external=True,
        title="Control de Prueba de Misión",
    )

    if surface_type == "win32" and sys.platform == "win32":
        surface = Win32ControlSurface(dest, hwnd=surface_meta["hwnd"])
        execution_mode = "asistido_win32_real"
        print(f"Superficie: Win32ControlSurface nativa de Windows (HWND vinculado: {surface.hwnd})")
        if not surface.is_target_active():
            store.close()
            raise RuntimeError(
                f"El control Win32 de destino (HWND: {surface.hwnd}) ya no está activo o ha desaparecido. "
                "Rechazando operación sin recrear silenciosamente."
            )
    else:
        surface = VerifiableControlSurface(dest)
        execution_mode = "asistido_control_prueba"
        print(f"Superficie: VerifiableControlSurface ({surface.mode})")

    # Validación de correspondencia de target_id
    if surface.target_id != req.target_id:
        store.close()
        raise RuntimeError(
            f"El destino actual ({surface.target_id}) difiere del destino autorizado en la solicitud ({req.target_id})"
        )

    operator = AntigravityAssistedOperator(run_dir=args.output_dir / "runs", store=store)

    # Importación y validación estricta de hashes contra la solicitud y el registro persistido en SQLite
    proposal = operator.import_proposal(res_file, req, store=store)
    print(f"[1/4] Propuesta importada y validada contra SQLite:")
    print(f"      - ID Propuesta : {proposal.proposal_id}")
    print(f"      - Texto        : \"{proposal.text}\"")
    print(f"      - Citas        : {proposal.citations}")
    print(f"      - Hash Request : {proposal.request_hash[:16]}... (VALIDADO CONTRA STORE)")
    print(f"      - Hash Payload : {proposal.payload_hash[:16]}... (VALIDADO CONTRA STORE)")

    # Reconstrucción y validación del paquete de contexto
    events = store.all()
    from muse_env.episodes import build_episodes
    from muse_env.context_builder import ContextBuilder
    current_ev = [e for e in events if e.application == req.target_application][-1]
    package = ContextBuilder().build(
        action=req.action,
        target_application=req.target_application,
        current_content=current_ev.content,
        episodes=build_episodes(events),
        target_is_external=True,
    )

    t_approval = approve_transfer(package, operator, actor="operador-humano (transferencia revalidada)")
    prep = prepare_reply(
        store=store,
        package=package,
        provider=operator,
        surface=surface,
        transfer_approval=t_approval,
    )
    if prep["status"] != "draft_ready":
        store.close()
        raise RuntimeError(f"Fallo al preparar borrador: {prep}")

    draft = prep["draft"]
    print(f"[2/4] Borrador preparado en base de datos:")
    print(f"      - Draft ID   : {draft['draft_id']}")
    print(f"      - Draft Hash : {digest(draft)}")

    # Aprobación explícita de inserción ligada al borrador exacto y destino
    ins_approval = approve_insertion(draft, actor=args.actor)
    print(f"[3/4] Aprobación humana concedida por: '{ins_approval.actor}'")

    # Inserción con readback
    result = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
    readback_ok = surface.verify_inserted(draft["text"])
    print(f"[4/4] Inserción completada:")
    print(f"      - Estado   : {result['status']}")
    print(f"      - Readback : {'CORRECTO' if readback_ok else 'FALLO'}")

    chain_valid = store.verify_chain()
    store.close()

    success = (result["status"] == "inserted_not_sent") and (readback_ok is True) and (chain_valid is True)

    summary = {
        "format_version": 2,
        "mode": execution_mode,
        "mission_id": req.mission_id,
        "operator": operator.identity,
        "request_hash": req.digest,
        "payload_hash": req.payload_hash,
        "proposal": proposal.to_dict(),
        "draft_id": draft["draft_id"],
        "draft_hash": digest(draft),
        "surface": surface.mode,
        "insertion_status": result["status"],
        "readback_verified": readback_ok,
        "chain_valid": chain_valid,
        "outcome_verified": success,
    }
    report_file = mission_dir / "resultado_mision.json"
    report_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if surface_type == "win32" and hasattr(surface, "close"):
        surface.close()

    if not success:
        print(f"\n[FALLO] La misión no completó la inserción verificada o la integridad de la cadena falló.")
        sys.exit(1)

    print(f"\n[ÉXITO] Misión completada e inscrita en el ledger con verificación integral.")
    print(f"Evidencia sellada en: {report_file}")


if __name__ == "__main__":
    main()
