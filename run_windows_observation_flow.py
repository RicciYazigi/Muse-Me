"""Orquestador para el Flujo de Observación Windows de Solo Lectura con Autorización Estricta y Política de No Captura.

Garantiza:
1. Creación de dos superficies de prueba nativas (Win32 EDIT controls) con contenido de prueba cargado.
2. Activación explícita (opt-in) del Win32ReadonlyObserver con autorización por identidad exacta de HWND.
3. Comprobación previa sin lectura: controles no autorizados son rechazados antes de acceder a texto o títulos.
4. Separación estricta entre permiso de captura y permiso de transferencia:
   - Fuente pertinente: capture_allowed=True, permission_scope="may_transfer"
   - Fuente irrelevante: capture_allowed=True, permission_scope="may_transfer"
   - Fuente sensible/restringida: capture_allowed=False, permission_scope="restricted"
     (el texto sensible NUNCA se lee del control, no se almacena en SQLite ni en JSON).
5. Selección y exclusión matemática en ContextBuilder:
   - Pertinente: seleccionada en additional_context
   - Irrelevante: excluida con 'not_relevant_to_current_action'
   - Restringida: excluida con 'restricted_no_transfer'
6. Vinculación estricta de procedencia (WindowsProvenance con event_id) persistida en SQLite.
7. Conservación del historial de ejecuciones en observation_memory.sqlite (sin eliminar la base).
8. Etiquetado honesto y transparente en el informe de evidencia sellada:
   - "captura_nativa_con_contenido_sintetico"
   - "respuesta_de_prueba_automatizada" (o respuesta asistida)
   - "consulta_sintetica_en_codigo"
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.events import ObservationEvent
from muse_env.store import EventStore, digest
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.invoke import approve_transfer, approve_insertion, prepare_reply, insert_reply
from muse_env.surfaces.base import TargetDestination
from muse_env.surfaces.win32_control import Win32ControlSurface
from muse_env.surfaces.win32_observer import Win32ReadonlyObserver
from muse_env.operators.antigravity import AntigravityAssistedOperator


def main():
    parser = argparse.ArgumentParser(description="Flujo de Observación Windows de Solo Lectura con Autorización Estricta")
    parser.add_argument("--interactive", action="store_true", help="Pausar para permitir redacción manual de response.json por el operador")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("Este flujo requiere Windows.")
        return 1

    print("=== INICIANDO FLUJO DE OBSERVACIÓN WINDOWS DE SOLO LECTURA (AUTORIZACIÓN ESTRICTA) ===")

    # 1. Crear las dos superficies de prueba y el control de destino
    dest_s1 = TargetDestination("Win32EditorSrc", "HWND-S1", "python.exe", "CTRL-S1", is_external=True, title="Editor-Principal-FastAPI")
    dest_s2 = TargetDestination("Win32DocsSrc", "HWND-S2", "python.exe", "CTRL-S2", is_external=True, title="Docs-Y-Notas-Privadas")
    dest_tgt = TargetDestination("Win32TargetApp", "HWND-TGT", "python.exe", "CTRL-TGT", is_external=True, title="Chat-Destino-Win32")

    s1 = Win32ControlSurface(dest_s1, auto_create=True)
    s2 = Win32ControlSurface(dest_s2, auto_create=True)
    target = Win32ControlSurface(dest_tgt, auto_create=True)

    print(f"[SUPERFICIE 1 - Editor] HWND: {s1.hwnd} (0x{s1.hwnd:08X}) | PID: {s1.pid}")
    print(f"[SUPERFICIE 2 - Docs/Notas] HWND: {s2.hwnd} (0x{s2.hwnd:08X}) | PID: {s2.pid}")
    print(f"[DESTINO - Inserción] HWND: {target.hwnd} (0x{target.hwnd:08X}) | PID: {target.pid}")

    try:
        # 2. Configurar observador con activación explícita (opt-in) y autorización por identidad exacta de HWND
        observer = Win32ReadonlyObserver(opt_in=True)
        observer.authorize_surface("Win32EditorSrc", hwnd=s1.hwnd, capture_allowed=True, permission_scope="may_transfer", window_title="Editor-Principal-FastAPI")
        observer.authorize_surface("Win32DocsSrc", hwnd=s2.hwnd, capture_allowed=True, permission_scope="may_transfer", window_title="Docs-Y-Notas-Privadas")

        # 3. Cargar contenido en los controles de prueba (captura nativa con contenido sintético)
        texto_pertinente = "FastAPI devuelve error 422: el esquema Pydantic espera entero en query param 'limit' pero recibe cadena"
        texto_irrelevante = "Monitor de sistema: 12 procesos en segundo plano activos, temperatura normal y memoria al 38%"
        texto_restringido = "CLAVE_PRIVADA_DESPLIEGUE = sec_live_9948271 (CONFIDENCIAL NO COMPARTIR)"

        # 4. Observar las fuentes reales
        # Fuente 1: Captura autorizada y transferible
        s1.insert(texto_pertinente)
        ev_pertinente, prov_pertinente = observer.observe(s1.hwnd)

        # Fuente 2: Captura autorizada e irrelevante
        s2.insert(texto_irrelevante)
        ev_irrelevante, prov_irrelevante = observer.observe(s2.hwnd)

        # Fuente 3: Regla de NO CAPTURA para fuente confidencial
        # Se actualiza la regla del control para denegar captura
        observer.authorize_surface(
            "Win32NotasPrivadas",
            hwnd=s2.hwnd,
            capture_allowed=False,  # NO CAPTURAR: no lee texto ni título
            permission_scope="restricted",
            window_title="NotasPrivadasConfidenciales"
        )
        s2.insert(texto_restringido)
        ev_restringido, prov_restringido = observer.observe(s2.hwnd)

        print(f"\n=== PASO 1: OBSERVACIONES WINDOWS REALES CAPTURADAS ===")
        print(f"1. Fuente Pertinente : ID={ev_pertinente.event_id} | HWND={prov_pertinente.hwnd} | Scope={ev_pertinente.permission_scope} | Captura={prov_pertinente.capture_allowed}")
        print(f"   Contenido leído   : {ev_pertinente.content[:60]}...")
        print(f"2. Fuente Irrelevante: ID={ev_irrelevante.event_id} | HWND={prov_irrelevante.hwnd} | Scope={ev_irrelevante.permission_scope} | Captura={prov_irrelevante.capture_allowed}")
        print(f"   Contenido leído   : {ev_irrelevante.content[:60]}...")
        print(f"3. Fuente Restringida: ID={ev_restringido.event_id} | HWND={prov_restringido.hwnd} | Scope={ev_restringido.permission_scope} | Captura={prov_restringido.capture_allowed}")
        print(f"   Contenido en evento: '{ev_restringido.content}' (CERO filtración: texto no leído por política de no captura)")

        # Verificación rigurosa de no captura
        assert ev_restringido.content == "", "El contenido de la fuente restringida debió ser cadena vacía"
        assert texto_restringido not in prov_restringido.window_title
        assert prov_restringido.read_method == "NO_CAPTURE_POLICY"

        # 5. Persistir en store SQLite acumulando historial (sin eliminar la base previa)
        runs_dir = ROOT / "data" / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        db_path = ROOT / "data" / "observation_memory.sqlite"
        store = EventStore(str(db_path))

        try:
            store.add(ev_pertinente)
            store.save_provenance(prov_pertinente)

            store.add(ev_irrelevante)
            store.save_provenance(prov_irrelevante)

            store.add(ev_restringido)
            store.save_provenance(prov_restringido)

            # Consulta actual de foco en el destino (etiquetada transparentemente como sintética en código)
            ev_current = ObservationEvent(
                kind="window_focus",
                application="Win32TargetApp",
                content="¿Por qué mi endpoint de FastAPI devuelve error 422?",
                permission_scope="may_transfer",
                source_type="simulated_user_query",
                ts=time.time(),
            )
            store.add(ev_current)

            # 6. Construir contexto y aplicar selección y exclusión
            # Usar ventana de episodios asociada a la sesión actual
            all_events = store.all()
            session_events = [e for e in all_events if e.event_id in (ev_pertinente.event_id, ev_irrelevante.event_id, ev_restringido.event_id, ev_current.event_id)]
            episodes = build_episodes(session_events)
            builder = ContextBuilder(max_additional=8)
            package = builder.build(
                action="reply_with_muse",
                target_application="Win32TargetApp",
                current_content=ev_current.content,
                episodes=episodes,
                target_is_external=True,
            )

            print(f"\n=== PASO 2: SELECCIÓN Y EXCLUSIÓN EN CONTEXT BUILDER ===")
            print(f"- Fuentes seleccionadas en additional_context: {[item['source'] for item in package['additional_context']]}")
            print(f"- Fuentes excluidas en excluded_context: {package['excluded_context']}")

            # Comprobar selección y exclusión
            sel_ids = [item["source"] for item in package["additional_context"]]
            assert ev_pertinente.event_id in sel_ids, "La fuente pertinente debe ser seleccionada"
            assert ev_irrelevante.event_id not in sel_ids, "La fuente irrelevante no debe transferirse"
            assert ev_restringido.event_id not in sel_ids, "La fuente restringida jamás debe transferirse"

            outbound = provider_payload(package)
            outbound_json = json.dumps(outbound)
            assert texto_restringido not in outbound_json, "Fuga de datos restringidos detectada!"
            assert "sec_live" not in outbound_json, "Fuga de credencial detectada!"

            # 7. Operador Antigravity: Creación y exportación de misión
            operator = AntigravityAssistedOperator(store=store)
            req = operator.create_mission_request(package=package, surface=target)
            t_approval = approve_transfer(package, operator, actor="operador-humano (autorización transferencia)")

            mission_info = operator.export_mission(req, runs_dir, store=store, package=package, transfer_approval=t_approval)
            mission_dir = mission_info["mission_dir"]
            mission_id = req.mission_id
            print(f"\n=== PASO 3: MISIÓN EXPORTADA ===")
            print(f"Misión ID: {mission_id}")
            print(f"Carpeta: {mission_dir}")

            res_file = mission_dir / "response.json"
            if args.interactive:
                print("\n[MODO INTERACTIVO] Esperando que el operador redacte response.json...")
                print(f"Por favor redactar {res_file} y guardar...")
                while not res_file.exists():
                    time.sleep(1)
                proposal_data = json.loads(res_file.read_text(encoding="utf-8"))
                proposal_text = proposal_data["text"]
                proposal_nature = "respuesta_operador_asistido_real"
            else:
                # Modo prueba automatizada: respuesta fixture explícitamente etiquetada
                proposal_text = (
                    "El error HTTP 422 en FastAPI ocurre porque el endpoint espera un número entero "
                    "para el parámetro 'limit' según el esquema Pydantic, pero la solicitud está enviando una cadena. "
                    "Para corregirlo, asegúrese de enviar un valor numérico entero en el query parameter 'limit'."
                )
                res_data = {
                    "proposal_id": f"prop-obs-win32-{mission_id[-6:]}",
                    "mission_id": mission_id,
                    "request_hash": req.digest,
                    "payload_hash": req.payload_hash,
                    "text": proposal_text,
                    "citations": [ev_pertinente.event_id],
                    "operator_identity": "antigravity-ide:agent",
                    "actions_requested": []
                }
                res_file.write_text(json.dumps(res_data, indent=2, ensure_ascii=False), encoding="utf-8")
                proposal_nature = "respuesta_de_prueba_automatizada (fixture)"

            # 8. Importar propuesta y verificar integridad
            proposal = operator.import_proposal(res_file, req, store=store)
            print(f"\n=== PASO 4: PROPUESTA DEL OPERADOR VALIDADA CONTRA SQLITE ===")
            print(f"- Proposal ID: {proposal.proposal_id}")
            print(f"- Naturaleza: {proposal_nature}")
            print(f"- Citas: {proposal.citations}")

            # 9. Preparar borrador y solicitar aprobación de inserción
            prep = prepare_reply(store=store, package=package, provider=operator, surface=target, transfer_approval=t_approval)
            assert prep["status"] == "draft_ready", f"Fallo al preparar borrador: {prep}"
            draft = prep["draft"]

            ins_approval = approve_insertion(draft, actor="operador-humano (aprobación inserción)")

            # 10. Inserción nativa y readback verificado
            delivery = insert_reply(store=store, draft=draft, surface=target, approval=ins_approval)
            assert delivery["status"] == "inserted_not_sent", f"Fallo inserción: {delivery}"
            assert target.verify_inserted(proposal_text) is True, "Readback nativo no coincide"
            print(f"\n=== PASO 5: INSERCIÓN Y READBACK NATIVO VERIFICADOS ===")
            print(f"- Estado de Inserción : {delivery['status']}")
            print(f"- Readback Verificado : True")

            # Comprobar que la misión fue consumida de forma atómica en SQLite durante la preparación del borrador
            m_record = store.get_mission(mission_id)
            assert m_record["state"] == "consumed", f"Estado de misión inesperado: {m_record}"
            print(f"[STORE SQLITE] Misión {mission_id} registrada como 'consumed' (consumo atómico comprobado).")

            # 11. Estructurar y sellar informe de evidencia con etiquetas transparentes y procedencia vinculada
            evidence_file = mission_dir / "evidencia_observacion_windows.json"
            evidence_data = {
                "format_version": 2,
                "mission_id": mission_id,
                "circuito": "observacion_windows_solo_lectura",
                "etiquetas_metodologicas": {
                    "modo_ejecucion": proposal_nature,
                    "origen_contenido_fuentes": "captura_nativa_con_contenido_sintetico",
                    "origen_consulta_foco": "consulta_sintetica_en_codigo",
                    "historial_sqlite": "acumulado_en_observation_memory.sqlite"
                },
                "observaciones_reales": [
                    {
                        "event_id": ev_pertinente.event_id,
                        "source_type": ev_pertinente.source_type,
                        "epistemic_status": ev_pertinente.epistemic_status,
                        "application": ev_pertinente.application,
                        "permission_scope": ev_pertinente.permission_scope,
                        "content": ev_pertinente.content,
                        "provenance": prov_pertinente.to_dict(),
                        "clasificacion": "fuente_pertinente_autorizada",
                        "politica_captura": "captura_permitida"
                    },
                    {
                        "event_id": ev_irrelevante.event_id,
                        "source_type": ev_irrelevante.source_type,
                        "epistemic_status": ev_irrelevante.epistemic_status,
                        "application": ev_irrelevante.application,
                        "permission_scope": ev_irrelevante.permission_scope,
                        "content": ev_irrelevante.content,
                        "provenance": prov_irrelevante.to_dict(),
                        "clasificacion": "fuente_irrelevante_excluida",
                        "politica_captura": "captura_permitida"
                    },
                    {
                        "event_id": ev_restringido.event_id,
                        "source_type": ev_restringido.source_type,
                        "epistemic_status": ev_restringido.epistemic_status,
                        "application": ev_restringido.application,
                        "permission_scope": ev_restringido.permission_scope,
                        "content": ev_restringido.content,
                        "provenance": prov_restringido.to_dict(),
                        "clasificacion": "fuente_restringida_excluida",
                        "politica_captura": "no_captura_estricta (texto_vacio, sin_lectura_WM_GETTEXT)"
                    }
                ],
                "inferencias": [
                    {
                        "proposal_id": proposal.proposal_id,
                        "operator_identity": proposal.operator_identity,
                        "epistemic_status": "inferred",
                        "naturaleza": proposal_nature,
                        "text": proposal.text,
                        "citations": proposal.citations,
                        "request_hash": proposal.request_hash,
                        "payload_hash": proposal.payload_hash
                    }
                ],
                "datos_sinteticos": [
                    {
                        "descripcion": "Los controles EDIT eran reales del sistema operativo Windows, pero el texto inyectado en ellos era texto de prueba sintético para simular el fallo técnico y notas confidenciales.",
                        "categoria": "captura_nativa_con_contenido_sintetico"
                    },
                    {
                        "descripcion": "El evento de consulta actual ('¿Por qué mi endpoint de FastAPI devuelve error 422?') fue emitido programáticamente como foco de usuario.",
                        "categoria": "consulta_sintetica_en_codigo"
                    }
                ],
                "seleccion_y_exclusion": {
                    "fuente_pertinente_seleccionada": ev_pertinente.event_id,
                    "fuentes_excluidas": package["excluded_context"]
                },
                "destino_verificado": {
                    "surface": target.mode,
                    "target_id": target.target_id,
                    "hwnd": target.hwnd,
                    "pid": target.pid,
                    "insertion_status": delivery["status"],
                    "readback_verified": True,
                    "outcome_verified": True
                }
            }
            evidence_file.write_text(json.dumps(evidence_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\n=== EVIDENCIA SELLADA DISPONIBLE EN ===")
            print(f"{evidence_file}")

            # 12. Verificación de rechazo de repetición (Replay Prevention)
            replay_claimed = store.claim_mission(mission_id, req.digest, req.payload_hash)
            assert replay_claimed is False, "Fallo: la misión permitió repetición"
            print("[REPLAY PREVENTION] Reintento rechazado correctamente por SQLite (misión ya consumida).")

        finally:
            store.close()

        print("\n=== FLUJO DE OBSERVACIÓN WINDOWS COMPLETADO EXITOSAMENTE ===")
        return 0

    finally:
        s1.close()
        s2.close()
        target.close()
        print("[SUPERFICIES DE PRUEBA CERRADAS ORDENADAMENTE]")


if __name__ == "__main__":
    sys.exit(main())
