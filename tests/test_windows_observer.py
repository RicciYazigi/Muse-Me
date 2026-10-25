"""Pruebas de Observación Windows de Solo Lectura con Autorización Estricta y Política de No Captura.

Verifica rigurosamente:
1. Requisito de activación explícita (opt-in); sin ella, la observación se rechaza.
2. Autorización por identidad exacta de HWND: dos ventanas con el mismo título NO heredan permisos.
3. Comprobación previa sin lectura: controles no autorizados son rechazados ANTES de leer texto o títulos.
4. Política de NO CAPTURA para fuentes sensibles (capture_allowed=False):
   - El texto sensible NUNCA se lee del control.
   - event.content es cadena vacía.
   - window_title no duplica ni filtra el contenido del control EDIT.
   - read_method registra 'NO_CAPTURE_POLICY'.
   - Comprobación en memoria, SQLite y JSON: ausencia total de la cadena confidencial.
5. Captura de procedencia real e identidad de ventana/control (HWND, PID, clase EDIT, control_id, window_id) vinculada por event_id.
6. Circuito completo de selección y exclusión:
   - Fuente pertinente autorizada (may_transfer) -> seleccionada en el contexto.
   - Fuente irrelevante (may_transfer) -> excluida con reason='not_relevant_to_current_action'.
   - Fuente restringida con no-captura (restricted, capture_allowed=False) -> excluida con reason='restricted_no_transfer'.
7. Separación clara de evidencias:
   - Observaciones reales: source_type='windows_read_only', epistemic_status='observed'
   - Inferencias: epistemic_status='inferred'
   - Datos sintéticos: etiquetados explícitamente
"""
from __future__ import annotations
import json
import pathlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from muse_env.events import ObservationEvent
from muse_env.store import EventStore
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.invoke import approve_transfer, approve_insertion, prepare_reply, insert_reply
from muse_env.surfaces.base import TargetDestination
from muse_env.surfaces.win32_control import Win32ControlSurface
from muse_env.surfaces.win32_observer import Win32ReadonlyObserver, WindowsProvenance
from muse_env.operators.antigravity import AntigravityAssistedOperator


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_requires_explicit_opt_in():
    """Sin activación explícita (opt-in), cualquier intento de observación falla."""
    dest = TargetDestination("AppPrueba", "HWND-0x1", "python.exe", "CTRL-0x1", is_external=True)
    surface = Win32ControlSurface(dest, auto_create=True)
    try:
        surface.insert("Contenido de prueba")
        observer = Win32ReadonlyObserver(opt_in=False)
        observer.authorize_surface("AppPrueba", hwnd=surface.hwnd, permission_scope="may_transfer")

        with pytest.raises(PermissionError, match="activación explícita"):
            observer.observe(surface.hwnd)

        # Tras activación explícita, se permite
        observer.activate()
        assert observer.opt_in is True
        event, prov = observer.observe(surface.hwnd)
        assert event.content == "Contenido de prueba"
        assert prov.hwnd == surface.hwnd
    finally:
        surface.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_rejects_unauthorized_surface():
    """Superficies no autorizadas en allowlist son bloqueadas tajantemente sin leer sus datos."""
    dest1 = TargetDestination("AppAutorizada", "HWND-0x1", "python.exe", "CTRL-0x1", is_external=True)
    dest2 = TargetDestination("AppNoAutorizada", "HWND-0x2", "python.exe", "CTRL-0x2", is_external=True)
    s1 = Win32ControlSurface(dest1, auto_create=True)
    s2 = Win32ControlSurface(dest2, auto_create=True)
    try:
        s1.insert("Texto permitido")
        s2.insert("Texto secreto ajeno que no debe ser leído")

        observer = Win32ReadonlyObserver(opt_in=True)
        observer.authorize_surface("AppAutorizada", hwnd=s1.hwnd, permission_scope="may_transfer")

        # La superficie autorizada puede leerse
        event, _ = observer.observe(s1.hwnd)
        assert event.content == "Texto permitido"

        # La superficie ajena no autorizada es rechazada
        with pytest.raises(PermissionError, match="no está en la lista de superficies autorizadas"):
            observer.observe(s2.hwnd)
    finally:
        s1.close()
        s2.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_exact_identity_no_title_inheritance():
    """Control B con el mismo título que Control A NO hereda permisos si no está en la allowlist."""
    dest_a = TargetDestination("AppA", "HWND-A", "python.exe", "CTRL-A", is_external=True, title="TituloCompartido")
    dest_b = TargetDestination("AppB", "HWND-B", "python.exe", "CTRL-B", is_external=True, title="TituloCompartido")
    sa = Win32ControlSurface(dest_a, auto_create=True)
    sb = Win32ControlSurface(dest_b, auto_create=True)
    try:
        sa.insert("Contenido de A autorizado")
        sb.insert("Contenido de B no autorizado")

        observer = Win32ReadonlyObserver(opt_in=True)
        # Solo se autoriza sa.hwnd con permisos may_transfer
        observer.authorize_surface("AppA", hwnd=sa.hwnd, permission_scope="may_transfer", window_title="TituloCompartido")

        # sa es autorizada y capturada correctamente
        ev_a, prov_a = observer.observe(sa.hwnd)
        assert ev_a.application == "AppA"
        assert ev_a.content == "Contenido de A autorizado"

        # sb tiene el mismo título, pero su HWND es diferente: DEBE ser rechazada
        assert sa.hwnd != sb.hwnd
        with pytest.raises(PermissionError, match="no está en la lista de superficies autorizadas"):
            observer.observe(sb.hwnd)
    finally:
        sa.close()
        sb.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_never_reads_content_before_authorization(monkeypatch):
    """Comprueba que jamás se llama a read_control_text ni a WM_GETTEXT antes de verificar la allowlist."""
    dest = TargetDestination("AppNoAutorizada", "HWND-NOAUTH", "python.exe", "CTRL-NOAUTH", is_external=True)
    s = Win32ControlSurface(dest, auto_create=True)
    try:
        s.insert("DATOS_PRIVADOS_QUE_NO_DEBEN_LEERSE")
        observer = Win32ReadonlyObserver(opt_in=True)

        read_attempts = []
        original_read = observer.read_control_text

        def spied_read(hwnd):
            read_attempts.append(hwnd)
            return original_read(hwnd)

        monkeypatch.setattr(observer, "read_control_text", spied_read)

        # Intentar observar control no autorizado
        with pytest.raises(PermissionError, match="no está en la lista de superficies autorizadas"):
            observer.observe(s.hwnd)

        # Verificar que NUNCA se intentó leer texto
        assert len(read_attempts) == 0, "Se intentó leer el texto de un control no autorizado"
    finally:
        s.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_strict_no_capture_policy():
    """Política explícita de NO CAPTURA (capture_allowed=False):

    El texto sensible NUNCA se lee del control, no entra al evento, no se almacena en SQLite ni en JSON.
    """
    dest = TargetDestination("NotasPrivadas", "HWND-SEC", "python.exe", "CTRL-SEC", is_external=True, title="NotasPrivadas")
    surface = Win32ControlSurface(dest, auto_create=True)
    try:
        secret_token = "SUPER_SECRET_TOKEN_XYZ_9948271"
        surface.insert(secret_token)

        observer = Win32ReadonlyObserver(opt_in=True)
        # Autorizar explícitamente con política de NO CAPTURA
        observer.authorize_surface(
            "NotasPrivadas",
            hwnd=surface.hwnd,
            capture_allowed=False,  # NO CAPTURAR
            permission_scope="restricted",
            window_title="NotasPrivadasSeguras"
        )

        event, prov = observer.observe(surface.hwnd)

        # 1. Comprobación en memoria del evento y la procedencia
        assert event.content == "", "El contenido debe ser vacío bajo política de no captura"
        assert secret_token not in event.content
        assert secret_token not in prov.window_title
        assert prov.capture_allowed is False
        assert prov.read_method == "NO_CAPTURE_POLICY"
        assert prov.event_id == event.event_id

        # 2. Comprobación en SQLite
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_no_capture.sqlite"
            store = EventStore(str(db_path))
            try:
                store.add(event)
                store.save_provenance(prov)

                stored_ev = store.get(event.event_id)
                assert stored_ev.content == "", "SQLite no debe contener texto sensible"
                stored_prov = store.get_provenance(event.event_id)
                assert stored_prov["capture_allowed"] is False
                assert stored_prov["read_method"] == "NO_CAPTURE_POLICY"
                assert secret_token not in stored_prov["window_title"]

                # Inspección binaria/raw de SQLite: el secreto jamás fue escrito en la base de datos
                raw_db = db_path.read_bytes()
                assert secret_token.encode("utf-8") not in raw_db, "El secreto se filtró físicamente en el archivo SQLite"
            finally:
                store.close()

        # 3. Comprobación en JSON
        json_output = json.dumps({"event": event.to_dict(), "provenance": prov.to_dict()})
        assert secret_token not in json_output, "El secreto se filtró en el volcado JSON"
    finally:
        surface.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_real_provenance_and_readonly():
    """Verifica procedencia real (HWND, PID, clase EDIT, control_id) y lectura no destructiva."""
    dest = TargetDestination("EditorNativo", "HWND-0x1", "python.exe", "CTRL-0x1", is_external=True)
    surface = Win32ControlSurface(dest, auto_create=True)
    try:
        original_text = "FastAPI endpoint error 422 en validación Pydantic"
        surface.insert(original_text)

        observer = Win32ReadonlyObserver(opt_in=True)
        observer.authorize_surface("EditorNativo", hwnd=surface.hwnd, capture_allowed=True, permission_scope="may_transfer")

        event, prov = observer.observe(surface.hwnd)

        # Procedencia real del sistema operativo
        assert prov.event_id == event.event_id
        assert prov.hwnd == surface.hwnd
        assert prov.pid > 0
        assert "python" in prov.process_name.lower()
        assert prov.class_name.lower() == "edit"
        assert prov.control_id == f"CTRL-0x{surface.hwnd:08X}"
        assert prov.window_id == f"HWND-0x{surface.hwnd:08X}"
        assert prov.read_method == "WM_GETTEXT"
        assert prov.target_id.startswith("target-")
        assert prov.capture_allowed is True

        # Evento epistemológico
        assert event.epistemic_status == "observed"
        assert event.source_type == "windows_read_only"
        assert event.content == original_text
        assert event.permission_scope == "may_transfer"

        # No destructivo: el control conserva su texto intacto
        assert surface.verify_inserted(original_text) is True
    finally:
        surface.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_selection_and_exclusion_circuit():
    """Circuito completo demostrando selección de fuente pertinente y exclusión de irrelevante y restringida.

    - Superficie 1 (Editor): Contenido pertinente ("FastAPI devuelve 422...") -> may_transfer, capture_allowed=True
    - Superficie 2 (Doc/Logs): Contenido irrelevante ("Monitor del sistema...") -> may_transfer, capture_allowed=True
    - Superficie 2 (Notas): Contenido restringido ("CLAVE_SECRETA_PRODUCCION...") -> restricted, capture_allowed=False
    """
    dest_editor = TargetDestination("Win32Editor", "HWND-ED", "python.exe", "CTRL-ED", is_external=True, title="Editor-FastAPI")
    dest_docs = TargetDestination("Win32Docs", "HWND-DOC", "python.exe", "CTRL-DOC", is_external=True, title="Docs-Notas")

    s_editor = Win32ControlSurface(dest_editor, auto_create=True)
    s_docs = Win32ControlSurface(dest_docs, auto_create=True)

    try:
        text_pertinente = "FastAPI devuelve 422: el esquema Pydantic espera entero en query param 'limit'"
        text_irrelevante = "Monitor de sistema: uso de CPU al 12% y memoria estable"
        text_restringido = "CLAVE_PRIVADA_DESPLIEGUE = sec_live_9948271 (CONFIDENCIAL NO TRANSFERIR)"

        # 1. Configurar observador con activación explícita y autorización por HWND exacto
        observer = Win32ReadonlyObserver(opt_in=True)
        observer.authorize_surface("Win32Editor", hwnd=s_editor.hwnd, capture_allowed=True, permission_scope="may_transfer")
        observer.authorize_surface("Win32Docs", hwnd=s_docs.hwnd, capture_allowed=True, permission_scope="may_transfer")

        # 2. Observación real de Fuente 1 (Pertinente) en Superficie 1
        s_editor.insert(text_pertinente)
        event_pertinente, prov_ed = observer.observe(s_editor.hwnd)

        # 3. Observación real de Fuente 2 (Irrelevante) en Superficie 2
        s_docs.insert(text_irrelevante)
        event_irrelevante, prov_doc = observer.observe(s_docs.hwnd)

        # 4. Observación real de Fuente 3 (Restringida bajo política de NO CAPTURA)
        observer.authorize_surface(
            "Win32NotasPrivadas",
            hwnd=s_docs.hwnd,
            capture_allowed=False,  # NO CAPTURA
            permission_scope="restricted",
            window_title="NotasPrivadasConfidenciales"
        )
        s_docs.insert(text_restringido)
        event_restringido, prov_res = observer.observe(s_docs.hwnd)

        # Validar procedencias reales y política de no captura
        assert prov_ed.hwnd == s_editor.hwnd
        assert prov_doc.hwnd == s_docs.hwnd
        assert prov_res.hwnd == s_docs.hwnd
        assert event_pertinente.permission_scope == "may_transfer"
        assert event_irrelevante.permission_scope == "may_transfer"
        assert event_restringido.permission_scope == "restricted"
        assert event_restringido.content == "", "El contenido de la fuente restringida no debe capturarse"
        assert prov_res.capture_allowed is False

        # 5. Registrar en EventStore SQLite
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_memory.sqlite"
            store = EventStore(str(db_path))

            try:
                store.add(event_pertinente)
                store.save_provenance(prov_ed)

                store.add(event_irrelevante)
                store.save_provenance(prov_doc)

                store.add(event_restringido)
                store.save_provenance(prov_res)

                # Evento de consulta actual (en foco)
                ev_current = ObservationEvent(
                    kind="window_focus",
                    application="Win32Editor",
                    content="¿Por qué mi endpoint de FastAPI devuelve error 422?",
                    permission_scope="may_transfer",
                    source_type="windows_read_only",
                    ts=event_pertinente.ts + 1.0,
                )
                store.add(ev_current)

                episodes = build_episodes(store.all())

                # 6. Construir paquete con ContextBuilder
                builder = ContextBuilder(max_additional=8)
                package = builder.build(
                    action="reply_with_muse",
                    target_application="Win32Editor",
                    current_content=ev_current.content,
                    episodes=episodes,
                    target_is_external=True,
                )

                # 7. Demostración de Selección y Exclusión:
                # a) La fuente pertinente DEBE estar seleccionada en additional_context
                additional_sources = [item["source"] for item in package["additional_context"]]
                assert event_pertinente.event_id in additional_sources, "La fuente pertinente debe estar seleccionada"

                # b) La fuente irrelevante DEBE estar en excluded_context con razón 'not_relevant_to_current_action'
                excluded_reasons = {item["source"]: item["reason"] for item in package["excluded_context"]}
                assert event_irrelevante.event_id in excluded_reasons, "La fuente irrelevante debe estar excluida"
                assert excluded_reasons[event_irrelevante.event_id] == "not_relevant_to_current_action"

                # c) La fuente restringida DEBE estar en excluded_context con razón 'restricted_no_transfer'
                assert event_restringido.event_id in excluded_reasons, "La fuente restringida debe estar excluida"
                assert excluded_reasons[event_restringido.event_id] == "restricted_no_transfer"

                # d) El outbound_payload JAMÁS contiene datos restringidos ni irrelevantes
                outbound = provider_payload(package)
                outbound_str = json.dumps(outbound)
                assert text_restringido not in outbound_str
                assert text_irrelevante not in outbound_str
                assert "sec_live" not in outbound_str
                assert text_pertinente in outbound_str
            finally:
                store.close()
    finally:
        s_editor.close()
        s_docs.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ReadonlyObserver")
def test_windows_observer_e2e_circuit_with_destination_insertion():
    """Recorrido E2E completo: observación Windows real -> selección -> operador -> inserción y readback."""
    dest_src1 = TargetDestination("Win32EditorSrc", "HWND-S1", "python.exe", "CTRL-S1", is_external=True, title="EditorSrc")
    dest_src2 = TargetDestination("Win32DocsSrc", "HWND-S2", "python.exe", "CTRL-S2", is_external=True, title="DocsSrc")
    dest_target = TargetDestination("Win32TargetControl", "HWND-TGT", "python.exe", "CTRL-TGT", is_external=True, title="TargetControl")

    s1 = Win32ControlSurface(dest_src1, auto_create=True)
    s2 = Win32ControlSurface(dest_src2, auto_create=True)
    tgt_surface = Win32ControlSurface(dest_target, auto_create=True)

    try:
        # 1. Observación real de superficies con allowlist estricta
        observer = Win32ReadonlyObserver(opt_in=True)
        observer.authorize_surface("Win32EditorSrc", hwnd=s1.hwnd, capture_allowed=True, permission_scope="may_transfer")
        observer.authorize_surface("Win32DocsSrc", hwnd=s2.hwnd, capture_allowed=False, permission_scope="restricted", window_title="DocsPrivados")

        text_valido = "FastAPI error 422: Pydantic ValidationError en parámetro"
        text_privado = "TOKEN_CONFIDENCIAL_12345"
        s1.insert(text_valido)
        s2.insert(text_privado)

        ev_valido, prov_valido = observer.observe(s1.hwnd)
        ev_privado, prov_privado = observer.observe(s2.hwnd)

        assert ev_valido.content == text_valido
        assert ev_privado.content == "", "Fuente con no-captura no debe contener texto"
        assert prov_privado.capture_allowed is False

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / "e2e_obs.sqlite"
            store = EventStore(str(db_path))

            try:
                store.add(ev_valido)
                store.save_provenance(prov_valido)

                store.add(ev_privado)
                store.save_provenance(prov_privado)

                ev_focus = ObservationEvent(
                    kind="window_focus",
                    application="Win32TargetControl",
                    content="¿Cómo resolver el error 422 en FastAPI?",
                    permission_scope="may_transfer",
                    source_type="windows_read_only",
                    ts=ev_valido.ts + 1.0,
                )
                store.add(ev_focus)

                episodes = build_episodes(store.all())
                package = ContextBuilder(max_additional=8).build(
                    action="reply_with_muse",
                    target_application="Win32TargetControl",
                    current_content=ev_focus.content,
                    episodes=episodes,
                    target_is_external=True,
                )

                # Verificar exclusión estricta de la fuente restringida
                assert any(item["source"] == ev_privado.event_id for item in package["excluded_context"])

                # 2. Operador prepara misión
                operator = AntigravityAssistedOperator(store=store)
                req = operator.create_mission_request(package=package, surface=tgt_surface)
                t_approval = approve_transfer(package, operator, actor="operador-humano")

                exported = operator.export_mission(req, tmp_path, store=store, package=package, transfer_approval=t_approval)

                # 3. Operador redacta respuesta citando únicamente la fuente pertinente observada
                proposal_text = "El error 422 se resuelve corrigiendo el tipo enviado para satisfacer el modelo Pydantic."
                res_data = {
                    "proposal_id": f"prop-obs-{req.mission_id[-6:]}",
                    "mission_id": req.mission_id,
                    "request_hash": req.digest,
                    "payload_hash": req.payload_hash,
                    "text": proposal_text,
                    "citations": [ev_valido.event_id],
                    "operator_identity": "antigravity-ide:agent",
                    "actions_requested": []
                }
                res_file = exported["mission_dir"] / "response.json"
                res_file.write_text(json.dumps(res_data, indent=2), encoding="utf-8")

                # 4. Importar propuesta, preparar borrador e insertar en control nativo real
                proposal = operator.import_proposal(res_file, req, store=store)
                assert proposal.text == proposal_text
                assert proposal.citations == [ev_valido.event_id]

                prep = prepare_reply(store=store, package=package, provider=operator, surface=tgt_surface, transfer_approval=t_approval)
                assert prep["status"] == "draft_ready"
                draft = prep["draft"]
                assert draft["text"] == proposal_text

                ins_approval = approve_insertion(draft, actor="operador-humano")

                delivery = insert_reply(store=store, draft=draft, surface=tgt_surface, approval=ins_approval)

                # 5. Comprobación de inserción y lectura directa en el control de destino
                assert delivery["status"] == "inserted_not_sent"
                assert tgt_surface.verify_inserted(proposal_text) is True

                # 6. Separación clara de evidencias
                evidence = {
                    "observaciones_reales": [
                        {
                            "event_id": ev_valido.event_id,
                            "source_type": ev_valido.source_type,
                            "epistemic_status": ev_valido.epistemic_status,
                            "provenance": prov_valido.to_dict(),
                        },
                        {
                            "event_id": ev_privado.event_id,
                            "source_type": ev_privado.source_type,
                            "epistemic_status": ev_privado.epistemic_status,
                            "provenance": prov_privado.to_dict(),
                        }
                    ],
                    "inferencias": [
                        {
                            "proposal_id": proposal.proposal_id,
                            "epistemic_status": "inferred",
                            "text": proposal.text,
                            "citations": proposal.citations,
                        }
                    ],
                    "destino_verificado": {
                        "surface": tgt_surface.mode,
                        "target_id": tgt_surface.target_id,
                        "status": delivery["status"],
                        "readback_verified": tgt_surface.verify_inserted(proposal_text),
                    }
                }

                assert evidence["observaciones_reales"][0]["source_type"] == "windows_read_only"
                assert evidence["observaciones_reales"][0]["epistemic_status"] == "observed"
                assert evidence["inferencias"][0]["epistemic_status"] == "inferred"
                assert evidence["destino_verificado"]["readback_verified"] is True
            finally:
                store.close()
    finally:
        s1.close()
        s2.close()
        tgt_surface.close()


def test_verify_chain_detects_provenance_pid_tampering():
    """Modificar el PID en la tabla observation_provenance invalida la cadena de integridad."""
    store = EventStore(":memory:")
    try:
        ev = ObservationEvent(kind="content_observed", application="Win32Test", content="prueba", epistemic_status="observed", permission_scope="may_transfer", source_type="windows_read_only")
        store.add(ev)

        prov = WindowsProvenance(
            event_id=ev.event_id,
            hwnd=123456,
            pid=4321,
            process_name="python.exe",
            window_title="TestWindow",
            class_name="Edit",
            control_id="CTRL-0x0001E240",
            window_id="HWND-0x0001E240",
            target_id="target-abcdef1234567890",
            capture_allowed=True,
            read_method="WM_GETTEXT",
            captured_at=ev.ts,
        )
        store.save_provenance(prov)

        # Cadena válida antes de manipular
        assert store.verify_chain() is True
        assert store.get_provenance(ev.event_id)["pid"] == 4321

        # Manipulación maliciosa del PID en la tabla de procedencia
        store.db.execute("UPDATE observation_provenance SET pid=99999 WHERE event_id=?", (ev.event_id,))
        store.db.commit()

        # get_provenance devuelve el dato alterado, pero verify_chain() DEBE fallar
        assert store.get_provenance(ev.event_id)["pid"] == 99999
        assert store.verify_chain() is False, "verify_chain() debió detectar la alteración del PID en observation_provenance"
    finally:
        store.close()


def test_verify_chain_detects_provenance_deletion():
    """Eliminar un registro de observation_provenance invalida la cadena de integridad."""
    store = EventStore(":memory:")
    try:
        ev = ObservationEvent(kind="content_observed", application="Win32Test", content="prueba2", epistemic_status="observed", permission_scope="may_transfer", source_type="windows_read_only")
        store.add(ev)

        prov = WindowsProvenance(
            event_id=ev.event_id,
            hwnd=654321,
            pid=8765,
            process_name="python.exe",
            window_title="TestWindow2",
            class_name="Edit",
            control_id="CTRL-0x0009FBF1",
            window_id="HWND-0x0009FBF1",
            target_id="target-1234567890abcdef",
            capture_allowed=True,
            read_method="WM_GETTEXT",
            captured_at=ev.ts,
        )
        store.save_provenance(prov)

        assert store.verify_chain() is True

        # Eliminación de la fila en observation_provenance
        store.db.execute("DELETE FROM observation_provenance WHERE event_id=?", (ev.event_id,))
        store.db.commit()

        assert store.get_provenance(ev.event_id) is None
        assert store.verify_chain() is False, "verify_chain() debió detectar la eliminación del registro de procedencia"
    finally:
        store.close()


def test_verify_chain_detects_rogue_provenance_insertion():
    """Insertar una procedencia falsa sin su correspondiente registro en el ledger es detectado."""
    store = EventStore(":memory:")
    try:
        ev = ObservationEvent(kind="content_observed", application="Win32Test", content="prueba3", epistemic_status="observed", permission_scope="may_transfer", source_type="windows_read_only")
        store.add(ev)

        # Inserción directa en la tabla SQL sin pasar por el ledger
        store.db.execute(
            "INSERT INTO observation_provenance VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ev.event_id, 11111, 2222, "fake.exe", "FakeTitle", "Edit", "CTRL-0x1", "HWND-0x1", "target-fake", 1, "WM_GETTEXT", ev.ts)
        )
        store.db.commit()

        # Debe fallar porque no existe el enlace 'provenance_recorded' en el ledger
        assert store.verify_chain() is False, "verify_chain() debió detectar la procedencia espuria no registrada en el ledger"
    finally:
        store.close()


def test_verify_chain_detects_provenance_unlinked_to_observation():
    """Una procedencia cuyo event_id no existe en observations es detectada."""
    store = EventStore(":memory:")
    try:
        # Guardar procedencia para un evento inexistente
        prov = WindowsProvenance(
            event_id="evt-nonexistent",
            hwnd=77777,
            pid=8888,
            process_name="python.exe",
            window_title="NoEventWindow",
            class_name="Edit",
            control_id="CTRL-0x7",
            window_id="HWND-0x7",
            target_id="target-nonexistent",
            capture_allowed=True,
            read_method="WM_GETTEXT",
            captured_at=100.0,
        )
        store.save_provenance(prov)

        # Debe fallar porque no corresponde a ninguna observación registrada
        assert store.verify_chain() is False, "verify_chain() debió detectar procedencia sin observación asociada"
    finally:
        store.close()

