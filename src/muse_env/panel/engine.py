"""Motor de Estado para el Panel Local de Revisión de Muse Environment.

Reutiliza los contratos arquitectónicos existentes:
1. Win32TestHost: proceso host persistente con bucle de mensajes Windows real para evitar bloqueos.
2. Win32ReadonlyObserver: activación explícita (opt-in), allowlist por identidad exacta de HWND,
   comprobación previa sin lectura y política de no captura (capture_allowed=False).
3. EventStore: persistencia en SQLite de eventos, misiones y tabla observation_provenance,
   cadena hash criptográfica y verificación estricta de procedencia con verify_chain().
4. ContextBuilder: selección de contexto relevante y exclusión explícita con motivos.
5. Gate 1 (Transferencia): approve_transfer ligado criptográficamente al paquete y al operador.
6. AntigravityAssistedOperator: exportación auditable de misiones e importación verificada.
7. Gate 2 (Inserción): approve_insertion ligado al borrador exacto y al destino físico.
8. Win32ControlSurface: inserción Win32 real (WM_SETTEXT), readback independiente (WM_GETTEXT)
   y prevención estricta de replay.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time
from typing import Any
from uuid import uuid4

from ..events import ObservationEvent
from ..store import EventStore, digest
from ..episodes import build_episodes
from ..context_builder import ContextBuilder, provider_payload
from ..invoke import approve_transfer, approve_insertion, prepare_reply, insert_reply, TransferApproval, InsertionApproval, FakeSurface
from ..surfaces.base import TargetDestination
from ..surfaces.win32_observer import Win32ReadonlyObserver, WindowsProvenance

if sys.platform == "win32":
    from ..surfaces.win32_control import Win32ControlSurface
    from ..surfaces.test_host import Win32TestHost
else:
    Win32ControlSurface = None
    Win32TestHost = None

from ..operators.antigravity import AntigravityAssistedOperator


class PanelEngine:
    def __init__(self, db_path: Path | str | None = None, runs_dir: Path | str | None = None, use_mock_surfaces: bool = False, project_memory_path: Path | str | None = None):
        root = Path(__file__).resolve().parent.parent.parent.parent
        self.runs_dir = Path(runs_dir) if runs_dir else (root / "data" / "runs")
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.use_mock_surfaces = use_mock_surfaces
        self._lock = threading.RLock()

        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = root / "data" / "observation_memory.sqlite"
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.store = EventStore(str(self.db_path))
        self.observer = Win32ReadonlyObserver(opt_in=False)

        # Superficies de prueba aisladas
        self._init_surfaces()

        # Estado del flujo
        self.current_query = "¿Por qué mi endpoint de FastAPI devuelve error 422?"
        self.package: dict[str, Any] | None = None
        self.transfer_approval: TransferApproval | None = None
        self.mission_request: Any = None
        self.mission_info: dict[str, Any] | None = None
        self.proposal: Any = None
        self.proposal_nature: str = "no_iniciada"
        self.draft: dict[str, Any] | None = None
        self.insertion_approval: InsertionApproval | None = None
        self.delivery_result: dict[str, Any] | None = None
        self.operator = AntigravityAssistedOperator(store=self.store)
        self.last_tamper_log: str | None = None

    def _init_surfaces(self) -> None:
        if sys.platform == "win32" and not self.use_mock_surfaces:
            # Reutilizar hosts persistentes con bucle de mensajes Windows para procesar SendMessageW sin bloquear
            self.host_s1 = Win32TestHost(status_file=self.runs_dir / "panel_host_s1.json", title="Editor-Principal-FastAPI").start()
            self.host_s2 = Win32TestHost(status_file=self.runs_dir / "panel_host_s2.json", title="Docs-Y-Notas-Privadas").start()
            self.host_target = Win32TestHost(status_file=self.runs_dir / "panel_host_target.json", title="Chat-Destino-Win32").start()

            dest_s1 = TargetDestination("Win32EditorSrc", f"HWND-0x{self.host_s1.hwnd:08X}", "python.exe", f"CTRL-0x{self.host_s1.hwnd:08X}", is_external=True, title="Editor-Principal-FastAPI")
            dest_s2 = TargetDestination("Win32DocsSrc", f"HWND-0x{self.host_s2.hwnd:08X}", "python.exe", f"CTRL-0x{self.host_s2.hwnd:08X}", is_external=True, title="Docs-Y-Notas-Privadas")
            dest_tgt = TargetDestination("Win32TargetApp", f"HWND-0x{self.host_target.hwnd:08X}", "python.exe", f"CTRL-0x{self.host_target.hwnd:08X}", is_external=True, title="Chat-Destino-Win32")

            self.s1 = Win32ControlSurface(dest_s1, hwnd=self.host_s1.hwnd)
            self.s2 = Win32ControlSurface(dest_s2, hwnd=self.host_s2.hwnd)
            self.target = Win32ControlSurface(dest_tgt, hwnd=self.host_target.hwnd)

            # Carga de contenido de prueba inicial
            self.s1.insert("FastAPI devuelve error 422: el esquema Pydantic espera entero en query param 'limit' pero recibe cadena")
            self.s2.insert("CLAVE_PRIVADA_DESPLIEGUE = sec_live_9948271 (CONFIDENCIAL NO COMPARTIR)")
        else:
            self.s1 = FakeSurface("Win32EditorSrc", is_external=True, target_id="target-mock-s1")
            self.s2 = FakeSurface("Win32DocsSrc", is_external=True, target_id="target-mock-s2")
            self.target = FakeSurface("Win32TargetApp", is_external=True, target_id="target-mock-tgt")
            self.s1.hwnd = 1001
            self.s2.hwnd = 1002
            self.target.hwnd = 1003
            self.s1.pid = 9001
            self.s2.pid = 9002
            self.target.pid = 9003
            self.s1.insert("FastAPI devuelve error 422: el esquema Pydantic espera entero en query param 'limit' pero recibe cadena")
            self.s2.insert("CLAVE_PRIVADA_DESPLIEGUE = sec_live_9948271 (CONFIDENCIAL NO COMPARTIR)")

        # Configuración inicial de reglas de autorización
        self.observer.authorize_surface(
            "Win32EditorSrc",
            hwnd=self.s1.hwnd,
            capture_allowed=True,
            permission_scope="may_transfer",
            window_title="Editor-Principal-FastAPI",
        )
        self.observer.authorize_surface(
            "Win32DocsSrc",
            hwnd=self.s2.hwnd,
            capture_allowed=False,  # Política estricta: NO CAPTURAR datos sensibles
            permission_scope="restricted",
            window_title="NotasPrivadasConfidenciales",
        )

    def close(self) -> None:
        with self._lock:
            if hasattr(self, 'project_memory'):
                try:
                    self.project_memory.close()
                except Exception:
                    pass
            if sys.platform == "win32" and not self.use_mock_surfaces:
                for h in (getattr(self, "host_s1", None), getattr(self, "host_s2", None), getattr(self, "host_target", None)):
                    if h:
                        try:
                            h.stop()
                        except Exception:
                            pass
            self.store.close()

    # --- Acciones del Panel ---

    def set_opt_in(self, enabled: bool) -> dict[str, Any]:
        """Activa o desactiva la captura Windows explícita (opt-in)."""
        with self._lock:
            self.observer.opt_in = bool(enabled)
            return {"opt_in": self.observer.opt_in}

    def configure_surface(
        self,
        hwnd: int,
        authorized: bool | None = None,
        capture_allowed: bool | None = None,
        permission_scope: str | None = None,
        application: str | None = None,
        window_title: str | None = None,
    ) -> dict[str, Any]:
        """Configura la autorización y políticas de captura/transferencia para un HWND de forma desacoplada."""
        with self._lock:
            hwnd = int(hwnd)
            is_auth, rule = self.observer.is_surface_authorized(hwnd)

            current_app = rule.application if rule else (application or "Win32App")
            current_capture = rule.capture_allowed if rule else True
            current_scope = rule.permission_scope if rule else "restricted"
            current_title = rule.window_title if rule else window_title
            current_auth = rule.authorized if rule else False

            new_auth = authorized if authorized is not None else (current_auth if rule else True)
            new_capture = capture_allowed if capture_allowed is not None else current_capture
            new_scope = permission_scope if permission_scope is not None else current_scope
            new_app = application if application is not None else current_app
            new_title = window_title if window_title is not None else current_title

            self.observer.authorize_surface(
                application=new_app,
                hwnd=hwnd,
                capture_allowed=new_capture,
                permission_scope=new_scope,
                is_external=True,
                window_title=new_title,
                authorized=new_auth,
            )
            return {
                "status": "configured" if new_auth else "revoked",
                "hwnd": hwnd,
                "is_authorized": new_auth,
                "capture_allowed": new_capture,
                "permission_scope": new_scope,
            }

    def set_surface_text(self, surface_id: str, text: str) -> dict[str, Any]:
        """Actualiza el texto contenido en una de las superficies de prueba."""
        with self._lock:
            target_surf = None
            if surface_id in ("s1", "editor", str(self.s1.hwnd)):
                target_surf = self.s1
            elif surface_id in ("s2", "docs", str(self.s2.hwnd)):
                target_surf = self.s2
            elif surface_id in ("target", "chat", str(self.target.hwnd)):
                target_surf = self.target

            if not target_surf:
                raise ValueError(f"Superficie desconocida: {surface_id}")

            target_surf.insert(text)
            return {"status": "updated", "surface": target_surf.name, "text_length": len(text)}

    def observe(self) -> dict[str, Any]:
        """Ejecuta el ciclo de observación de superficies autorizadas respetando políticas."""
        with self._lock:
            if not self.observer.opt_in:
                raise PermissionError("Captura desactivada: se requiere activación explícita (opt-in)")

            results = []
            for surf in (self.s1, self.s2):
                is_auth, rule = self.observer.is_surface_authorized(surf.hwnd)
                if is_auth:
                    if self.use_mock_surfaces or sys.platform != "win32":
                        ev_id = f"evt-mock-{uuid4().hex[:12]}"
                        content = "" if not rule.capture_allowed else (surf.inserted[-1] if hasattr(surf, "inserted") and surf.inserted else "")
                        event = ObservationEvent(
                            event_id=ev_id,
                            kind="content_observed",
                            application=rule.application,
                            content=content,
                            permission_scope=rule.permission_scope,
                            source_type="windows_read_only",
                            epistemic_status="observed",
                            ts=time.time(),
                        )
                        prov = WindowsProvenance(
                            event_id=ev_id,
                            hwnd=surf.hwnd,
                            pid=getattr(surf, "pid", 1234),
                            process_name="python.exe",
                            window_title=rule.window_title or "MockWindow",
                            class_name="Edit",
                            control_id=f"CTRL-0x{surf.hwnd:08X}",
                            window_id=f"HWND-0x{surf.hwnd:08X}",
                            target_id=surf.target_id,
                            capture_allowed=rule.capture_allowed,
                            read_method="WM_GETTEXT" if rule.capture_allowed else "NO_CAPTURE_POLICY",
                            captured_at=event.ts,
                        )
                    else:
                        event, prov = self.observer.observe(surf.hwnd)
                    self.store.add(event)
                    self.store.save_provenance(prov)
                    results.append({
                        "event_id": event.event_id,
                        "application": event.application,
                        "content": event.content,
                        "permission_scope": event.permission_scope,
                        "capture_allowed": prov.capture_allowed,
                        "read_method": prov.read_method,
                        "hwnd": prov.hwnd,
                        "pid": prov.pid,
                        "window_title": prov.window_title,
                    })

            # Evento sintético de foco/consulta en la app de destino
            ev_current = ObservationEvent(
                kind="window_focus",
                application=self.target.name,
                content=self.current_query,
                permission_scope="may_transfer",
                source_type="simulated_user_query",
                ts=time.time(),
            )
            self.store.add(ev_current)
            results.append({
                "event_id": ev_current.event_id,
                "application": ev_current.application,
                "content": ev_current.content,
                "permission_scope": ev_current.permission_scope,
                "capture_allowed": True,
                "read_method": "QUERY_FOCUS",
                "hwnd": self.target.hwnd,
                "pid": self.target.pid,
                "window_title": "Consulta de foco actual",
            })

            return {"status": "observed", "observations": results}

    def build_context(self, query: str | None = None) -> dict[str, Any]:
        """Ejecuta ContextBuilder para seleccionar fuentes pertinentes y registrar exclusiones."""
        with self._lock:
            if query:
                self.current_query = query

            all_events = self.store.all()
            matches = [e for e in all_events if e.application == self.target.name and e.content == self.current_query]
            if not matches:
                ev_current = ObservationEvent(
                    kind="window_focus",
                    application=self.target.name,
                    content=self.current_query,
                    permission_scope="may_transfer",
                    source_type="simulated_user_query",
                    ts=time.time(),
                )
                self.store.add(ev_current)
                all_events = self.store.all()

            episodes = build_episodes(all_events)
            builder = ContextBuilder(max_additional=8)
            self.package = builder.build(
                action="reply_with_muse",
                target_application=self.target.name,
                current_content=self.current_query,
                episodes=episodes,
                target_is_external=True,
            )

            outbound = provider_payload(self.package)

            # Verificación estricta de fuga
            outbound_json = json.dumps(outbound)
            leak_detected = ("sec_live" in outbound_json) or ("CLAVE_PRIVADA" in outbound_json)

            return {
                "status": "package_built",
                "package_hash": digest(self.package),
                "payload_hash": digest(outbound),
                "additional_context": self.package["additional_context"],
                "excluded_context": self.package["excluded_context"],
                "leak_detected": leak_detected,
            }

    def authorize_transfer(self, actor: str = "operador-humano (panel local)") -> dict[str, Any]:
        """Compuerta 1: Autoriza formalmente la transferencia del paquete al operador."""
        with self._lock:
            if not self.package:
                raise ValueError("Primero debe construirse el contexto con build_context()")

            self.transfer_approval = approve_transfer(self.package, self.operator, actor=actor)
            self.mission_request = self.operator.create_mission_request(package=self.package, surface=self.target)

            self.mission_info = self.operator.export_mission(
                self.mission_request,
                self.runs_dir,
                store=self.store,
                package=self.package,
                transfer_approval=self.transfer_approval,
            )

            return {
                "status": "transfer_approved",
                "mission_id": self.mission_request.mission_id,
                "package_hash": self.transfer_approval.package_hash,
                "payload_hash": self.transfer_approval.payload_hash,
                "actor": self.transfer_approval.actor,
                "mission_dir": str(self.mission_info["mission_dir"]),
            }

    def import_proposal(self) -> dict[str, Any]:
        """Importa y valida la propuesta existente en response.json SIN sobrescribirla."""
        with self._lock:
            if not self.mission_request or not self.mission_info:
                raise ValueError("Misión no exportada. Debe autorizar la transferencia primero.")

            mission_dir = self.mission_info["mission_dir"]
            res_file = mission_dir / "response.json"
            if not res_file.exists():
                return {
                    "status": "waiting_response",
                    "message": f"response.json no encontrado en {mission_dir.name}. Redacte el archivo como operador o genere un fixture de prueba.",
                }

            disk_content = json.loads(res_file.read_text(encoding="utf-8"))
            op_id = disk_content.get("operator_identity", "").lower()
            text_lower = disk_content.get("text", "").lower()
            declared_nature = disk_content.get("nature") or disk_content.get("naturaleza")

            if declared_nature:
                self.proposal_nature = f"archivo_importado ({declared_nature})"
            elif any(k in op_id for k in ("sintético", "sintetico", "fixture", "synthetic", "prueba", "mock")) or \
                 any(k in text_lower for k in ("sintético", "sintetico", "fixture", "synthetic")):
                self.proposal_nature = "archivo_importado_sintetico (fixture)"
            else:
                self.proposal_nature = "archivo_importado_sin_atribucion_verificada"

            self.proposal = self.operator.import_proposal(res_file, self.mission_request, store=self.store)

            prep = prepare_reply(
                store=self.store,
                package=self.package,
                provider=self.operator,
                surface=self.target,
                transfer_approval=self.transfer_approval,
            )
            if prep["status"] != "draft_ready":
                raise RuntimeError(f"Fallo al preparar borrador: {prep}")

            self.draft = prep["draft"]
            return {
                "status": "proposal_staged_and_draft_ready",
                "proposal_id": self.proposal.proposal_id,
                "draft_id": self.draft["draft_id"],
                "text": self.draft["text"],
                "citations": self.draft["citations"],
                "draft_hash": digest(self.draft),
                "nature": self.proposal_nature,
            }

    def generate_fixture_proposal(self, text: str | None = None, citations: list[str] | None = None) -> dict[str, Any]:
        """Genera un fixture de prueba sintético explícitamente etiquetado para response.json."""
        with self._lock:
            if not self.mission_request or not self.mission_info:
                raise ValueError("Misión no exportada. Debe autorizar la transferencia primero.")

            mission_dir = self.mission_info["mission_dir"]
            res_file = mission_dir / "response.json"

            allowed_sources = self.mission_request.allowed_sources
            pertinente_ids = [s for s in allowed_sources if s != "current_turn"]
            default_citation = pertinente_ids[0] if pertinente_ids else allowed_sources[0]

            proposal_text = text or (
                "El error HTTP 422 en FastAPI ocurre porque el endpoint espera un número entero "
                "para el parámetro 'limit' según el esquema Pydantic, pero la solicitud está enviando una cadena. "
                "Para corregirlo, asegúrese de enviar un valor numérico entero en el query parameter 'limit'."
            )
            proposal_citations = citations or [default_citation]

            res_data = {
                "proposal_id": f"prop-fixture-{self.mission_request.mission_id[-6:]}",
                "mission_id": self.mission_request.mission_id,
                "request_hash": self.mission_request.digest,
                "payload_hash": self.mission_request.payload_hash,
                "text": proposal_text,
                "citations": proposal_citations,
                "operator_identity": "antigravity-ide:agent (fixture sintético)",
                "actions_requested": [],
            }
            res_file.write_text(json.dumps(res_data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.proposal_nature = "respuesta_de_prueba_automatizada (fixture)"

            self.proposal = self.operator.import_proposal(res_file, self.mission_request, store=self.store)

            prep = prepare_reply(
                store=self.store,
                package=self.package,
                provider=self.operator,
                surface=self.target,
                transfer_approval=self.transfer_approval,
            )
            if prep["status"] != "draft_ready":
                raise RuntimeError(f"Fallo al preparar borrador: {prep}")

            self.draft = prep["draft"]
            return {
                "status": "proposal_staged_and_draft_ready",
                "proposal_id": self.proposal.proposal_id,
                "draft_id": self.draft["draft_id"],
                "text": self.draft["text"],
                "citations": self.draft["citations"],
                "draft_hash": digest(self.draft),
                "nature": self.proposal_nature,
            }

    def approve_insertion(self, actor: str = "operador-humano (panel local)") -> dict[str, Any]:
        """Compuerta 2: Aprueba la inserción exacta del borrador revisado en el destino."""
        with self._lock:
            if not self.draft:
                raise ValueError("No hay borrador preparado para aprobar")

            self.insertion_approval = approve_insertion(self.draft, actor=actor)
            return {
                "status": "insertion_approved",
                "draft_id": self.insertion_approval.draft_id,
                "draft_hash": self.insertion_approval.draft_hash,
                "target_id": self.insertion_approval.target_id,
                "actor": self.insertion_approval.actor,
            }

    def execute_insertion(self) -> dict[str, Any]:
        """Ejecuta la inserción en el control nativo Win32, verifica readback y comprueba ledger/cadena."""
        with self._lock:
            if not self.draft or not self.insertion_approval:
                raise ValueError("Se requiere borrador y aprobación de inserción previa")

            raw_delivery = insert_reply(
                store=self.store,
                draft=self.draft,
                surface=self.target,
                approval=self.insertion_approval,
            )

            delivery_ok = (raw_delivery.get("status") == "inserted_not_sent")
            readback_ok = self.target.verify_inserted(self.draft["text"]) if delivery_ok else False
            chain_valid = self.store.verify_chain()

            # Comprobar estado de misión
            m_record = self.store.get_mission(self.mission_request.mission_id) if self.mission_request else None
            mission_consumed = bool(m_record and m_record.get("state") == "consumed")

            self.delivery_result = {
                "status": raw_delivery["status"],
                "reason": raw_delivery.get("reason"),
                "readback_verified": readback_ok,
                "chain_valid": chain_valid,
                "mission_consumed": mission_consumed,
                "target_hwnd": self.target.hwnd,
                "surface_name": self.target.name,
            }
            return self.delivery_result

    def check_target_readback(self) -> dict[str, Any]:
        """Realiza una lectura WM_GETTEXT independiente sobre el destino y contrasta con el borrador."""
        with self._lock:
            if not self.draft:
                return {"readback_verified": False, "reason": "sin_borrador"}
            readback_ok = self.target.verify_inserted(self.draft["text"])
            reason = None if readback_ok else "discrepancia_texto_en_control"
            if self.delivery_result:
                self.delivery_result["readback_verified"] = readback_ok
                if not readback_ok:
                    self.delivery_result["reason"] = reason
            return {
                "readback_verified": readback_ok,
                "status": self.delivery_result.get("status") if self.delivery_result else "no_insertado",
                "reason": reason,
            }

    def tamper_provenance_test(self, tamper_type: str = "pid") -> dict[str, Any]:
        """Prueba interactiva sobre una copia temporal en memoria que NO altera la base compartida."""
        with self._lock:
            rows = self.store.db.execute("SELECT event_id, pid FROM observation_provenance LIMIT 1").fetchall()
            if not rows:
                return {"status": "error", "message": "No hay registros de procedencia en SQLite para demostrar alteración"}

            ev_id, original_pid = rows[0]

            # Crear copia temporal aislada en memoria sin tocar la base real
            temp_store = EventStore(":memory:")
            self.store.db.backup(temp_store.db)

            try:
                if tamper_type == "pid":
                    tampered_pid = original_pid + 9999
                    temp_store.db.execute("UPDATE observation_provenance SET pid=? WHERE event_id=?", (tampered_pid, ev_id))
                    temp_store.db.commit()
                    temp_chain_valid = temp_store.verify_chain()
                    shared_chain_valid = self.store.verify_chain()
                    self.last_tamper_log = (
                        f"[COPIA AISLADA] Alterado PID del evento {ev_id}: {original_pid} -> {tampered_pid}. "
                        f"verify_chain() en copia={temp_chain_valid} (DETECTADO). "
                        f"Base compartida={shared_chain_valid} (INTACTA)."
                    )
                    return {
                        "tamper_type": "pid",
                        "event_id": ev_id,
                        "original_pid": original_pid,
                        "tampered_pid": tampered_pid,
                        "chain_valid": temp_chain_valid,
                        "shared_chain_valid": shared_chain_valid,
                        "detected": not temp_chain_valid,
                        "isolated_demo": True,
                    }
                elif tamper_type == "delete":
                    temp_store.db.execute("DELETE FROM observation_provenance WHERE event_id=?", (ev_id,))
                    temp_store.db.commit()
                    temp_chain_valid = temp_store.verify_chain()
                    shared_chain_valid = self.store.verify_chain()
                    self.last_tamper_log = (
                        f"[COPIA AISLADA] Eliminada procedencia del evento {ev_id}. "
                        f"verify_chain() en copia={temp_chain_valid} (DETECTADO). "
                        f"Base compartida={shared_chain_valid} (INTACTA)."
                    )
                    return {
                        "tamper_type": "delete",
                        "event_id": ev_id,
                        "chain_valid": temp_chain_valid,
                        "shared_chain_valid": shared_chain_valid,
                        "detected": not temp_chain_valid,
                        "isolated_demo": True,
                    }
                return {"status": "error", "message": f"Tipo de alteración no soportado: {tamper_type}"}
            finally:
                temp_store.close()

    def get_state(self) -> dict[str, Any]:
        """Devuelve el estado completo del panel para renderizado en UI."""
        with self._lock:
            surfaces_info = []
            for key, s in [("s1", self.s1), ("s2", self.s2), ("target", self.target)]:
                is_auth, rule = self.observer.is_surface_authorized(s.hwnd)
                dest = getattr(s, "destination", None)
                win_title = rule.window_title if (rule and rule.window_title) else (getattr(dest, "title", "Win32 Control") if dest else s.name)
                surfaces_info.append({
                    "id": key,
                    "name": s.name,
                    "hwnd": s.hwnd,
                    "hwnd_hex": f"0x{s.hwnd:08X}" if s.hwnd else "N/A",
                    "pid": getattr(s, "pid", 0),
                    "is_authorized": is_auth,
                    "capture_allowed": rule.capture_allowed if rule else False,
                    "permission_scope": rule.permission_scope if rule else "unauthorized",
                    "window_title": win_title,
                    "is_target": key == "target",
                })

            all_events = self.store.all()
            obs_list = []
            for ev in all_events[-10:]:
                prov = self.store.get_provenance(ev.event_id)
                obs_list.append({
                    "event_id": ev.event_id,
                    "kind": ev.kind,
                    "application": ev.application,
                    "content": ev.content,
                    "permission_scope": ev.permission_scope,
                    "source_type": ev.source_type,
                    "epistemic_status": ev.epistemic_status,
                    "ts": ev.ts,
                    "provenance": prov,
                })

            chain_links = self.store.chain()
            chain_valid = self.store.verify_chain()

            return {
                "opt_in": self.observer.opt_in,
                "surfaces": surfaces_info,
                "current_query": self.current_query,
                "observations_count": len(all_events),
                "recent_observations": obs_list,
                "package_built": self.package is not None,
                "package_info": {
                    "additional_context": self.package.get("additional_context", []) if self.package else [],
                    "excluded_context": self.package.get("excluded_context", []) if self.package else [],
                    "package_hash": digest(self.package) if self.package else None,
                } if self.package else None,
                "transfer_approved": self.transfer_approval is not None,
                "transfer_approval_info": {
                    "actor": self.transfer_approval.actor,
                    "package_hash": self.transfer_approval.package_hash,
                    "provider_id": self.transfer_approval.provider_id,
                } if self.transfer_approval else None,
                "mission_exported": self.mission_request is not None,
                "mission_id": self.mission_request.mission_id if self.mission_request else None,
                "draft_ready": self.draft is not None,
                "draft_info": {
                    "draft_id": self.draft.get("draft_id"),
                    "text": self.draft.get("text"),
                    "citations": self.draft.get("citations"),
                    "draft_hash": digest(self.draft),
                    "nature": self.proposal_nature,
                } if self.draft else None,
                "insertion_approved": self.insertion_approval is not None,
                "insertion_approval_info": {
                    "actor": self.insertion_approval.actor,
                    "draft_id": self.insertion_approval.draft_id,
                    "target_id": self.insertion_approval.target_id,
                } if self.insertion_approval else None,
                "delivery_result": self.delivery_result,
                "chain_valid": chain_valid,
                "chain_links_count": len(chain_links),
                "last_chain_links": [{"kind": l["kind"], "hash": l["hash"][:12] + "…"} for l in chain_links[-6:]],
                "last_tamper_log": self.last_tamper_log,
            }

    def _init_demo_project_data_if_empty(self) -> None:
        try:
            count = self.project_memory.db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            if count == 0:
                self.project_memory.put(
                    "demo-latam",
                    "politica_descuentos_v24.md",
                    "Especificación v2.4 (2026): Para órdenes de región LATAM con cupón PROMO_REGIONAL, aplicar 15% de descuento sobre el subtotal antes de impuestos con tope máximo de 25.00 USD.",
                    "may_transfer"
                )
                self.project_memory.put(
                    "demo-latam",
                    "manual_descuentos_v10_obsoleto.md",
                    "Manual v1.0 (2024): Descuentos promocionales generales se calculan al 5% sin tope regional para clientes activos.",
                    "may_transfer"
                )
                self.project_memory.put(
                    "demo-latam",
                    "claves_privadas_infra.txt",
                    "STRIPE_API_KEY=sk_live_secret_sample_token_not_for_export; AWS_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "restricted"
                )
        except Exception:
            pass

    def get_meta_status(self) -> dict[str, Any]:
        import os
        has_key = bool(os.environ.get("MODEL_API_KEY"))
        model_name = os.environ.get("MODEL_NAME", "Llama-3.3-70B-Instruct")
        return {
            "available": has_key,
            "model": model_name if has_key else "Ninguno (Modo Asistido / Fixture)",
            "mode": "meta_cloud_inference" if has_key else "assisted_operator",
            "notice": "Credencial verificada en entorno local" if has_key else "Meta pendiente de conexión; operando en modo asistido local"
        }

    def get_projects_overview(self) -> dict[str, Any]:
        with self._lock:
            rows = self.project_memory.db.execute("SELECT DISTINCT project FROM sources ORDER BY project").fetchall()
            projects = [r[0] for r in rows]
            if not projects:
                projects = ["demo-latam"]
            data = []
            for p in projects:
                src_rows = self.project_memory.db.execute(
                    "SELECT source, revision, scope FROM sources WHERE project=? ORDER BY source", (p,)
                ).fetchall()
                sources = []
                for s in src_rows:
                    sources.append({"source": s["source"], "revision": s["revision"], "scope": s["scope"]})
                m_rows = self.project_memory.db.execute(
                    "SELECT id, goal, state, capability, artifact_path, artifact_hash FROM missions WHERE project=? ORDER BY rowid DESC LIMIT 5",
                    (p,)
                ).fetchall()
                missions = [dict(m) for m in m_rows]
                data.append({
                    "project": p,
                    "sources": sources,
                    "recent_missions": missions
                })
            return {"projects": data, "meta": self.get_meta_status()}

    def ingest_project_source(self, project: str, source_name: str, content: str, scope: str = "local-only") -> dict[str, Any]:
        with self._lock:
            rev = self.project_memory.put(project, source_name, content, scope)
            return {"project": project, "source": source_name, "revision": rev, "scope": scope}

    def query_and_checkpoint(self, project: str, query: str, capability: str = "deliverable_production", external: bool = True) -> dict[str, Any]:
        with self._lock:
            evidence = self.project_memory.search(project, query, external=external)
            if not evidence:
                rows = self.project_memory.db.execute(
                    "SELECT source, revision, scope, content FROM sources s JOIN revisions r ON s.project=r.project AND s.source=r.source AND s.revision=r.revision WHERE s.project=? AND s.scope != 'restricted'",
                    (project,)
                ).fetchall()
                refs = {r['source']: r['revision'] for r in rows}
                evidence = [{"source": r['source'], "revision": r['revision'], "scope": r['scope'], "content": r['content']} for r in rows]
            else:
                refs = {r['source']: r['revision'] for r in evidence}

            if not refs:
                raise ValueError(f"No hay fuentes autorizadas en el proyecto '{project}' con permiso 'may_transfer'.")

            mission_id = self.project_memory.checkpoint(project, query, refs, capability=capability)
            return {
                "mission_id": mission_id,
                "project": project,
                "query": query,
                "capability": capability,
                "evidence_count": len(evidence),
                "evidence": evidence
            }

    def run_capability_compare(self, mission_id: str) -> dict[str, Any]:
        with self._lock:
            from ..capabilities import compare_evidence
            return compare_evidence(self.project_memory, mission_id)

    def run_capability_propose_deliverable(self, mission_id: str, title: str = "Entregable Contextual", criteria: dict | None = None) -> dict[str, Any]:
        with self._lock:
            from ..capabilities import propose_deliverable
            return propose_deliverable(self.project_memory, mission_id, title=title, criteria=criteria)

    def run_capability_execute_deliverable(self, mission_id: str, target_dir: str = "artifacts", filename: str = "entregable.md", approved_draft_sha256: str = "") -> dict[str, Any]:
        with self._lock:
            from ..capabilities import execute_deliverable_action
            root = Path(__file__).resolve().parent.parent.parent.parent
            target_path = root / target_dir if not Path(target_dir).is_absolute() else Path(target_dir)
            target_path.mkdir(parents=True, exist_ok=True)
            return execute_deliverable_action(
                self.project_memory,
                mission_id,
                target_path,
                filename,
                approved_draft_sha256,
                user_approved=True
            )

    def reingest_source(self, project: str, source: str) -> dict[str, Any]:
        with self._lock:
            sf = self.project_memory.db.execute(
                "SELECT root_path, relative_path, file_hash FROM source_files WHERE project=? AND source=?",
                (project, source)
            ).fetchone()
            if sf and sf["root_path"] and sf["relative_path"]:
                disk_path = Path(sf["root_path"]) / sf["relative_path"]
                if disk_path.exists():
                    rev = self.project_memory.ingest_text(project, sf["root_path"], sf["relative_path"], scope="may_transfer")
                    return {"status": "reingested", "project": project, "source": source, "new_revision": rev}
            return {"status": "skipped", "message": "No hay archivo local asociado en disco para reingestar automáticamente"}
