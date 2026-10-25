"""Tests for Operator Contract, Antigravity Assisted Adapter, and Verifiable Surfaces.

Comprehensive regression coverage for all Codex findings:
- R01: Regression parity (retains all earlier tests).
- R02: Exclusion of restricted sources before export/dispatch.
- R03: Transfer authorization mandatory before export and revalidation against EventStore.
- R04: Strict binding between response, request digest, and payload hash (including SQLite match).
- R07: Win32ControlSurface physical handle binding (rejects HWND swapping) and read-only WindowsProbeSurface.
- R08: Idempotent mission consumption, replay prevention across restarts.
- Focus loss, readback failure, citations out-of-bounds, payload divergence rejection.
"""
import copy
import json
import pathlib
import sys
import tempfile
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from muse_env.store import EventStore, digest
from muse_env.events import ObservationEvent
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.invoke import prepare_reply, insert_reply, approve_transfer, approve_insertion
from muse_env.operators.contract import MissionRequest, OperatorProposal
from muse_env.operators.antigravity import AntigravityAssistedOperator
from muse_env.surfaces.base import TargetDestination
from muse_env.surfaces.test_control import VerifiableControlSurface
from muse_env.surfaces.windows_probe import WindowsProbeSurface
from muse_env.surfaces.win32_control import Win32ControlSurface
from muse_env.surfaces.test_host import Win32TestHost


def setup_operator_case():
    store = EventStore()
    e1 = ObservationEvent(kind="content_observed", application="VS Code", ts=100.0,
                          content="FastAPI devuelve 422 por validación de enteros", permission_scope="may_transfer")
    e2 = ObservationEvent(kind="content_observed", application="Notas privadas", ts=110.0,
                          content="TOKEN_SECRETO=12345", permission_scope="restricted")
    e3 = ObservationEvent(kind="window_focus", application="Chat externo", ts=120.0,
                          content="¿Por qué FastAPI devuelve 422?", permission_scope="may_transfer")
    for ev in (e1, e2, e3):
        store.add(ev)
    episodes = build_episodes(store.all())
    package = ContextBuilder().build(
        action="reply_with_muse",
        target_application="Chat externo",
        current_content=e3.content,
        episodes=episodes,
        target_is_external=True
    )
    dest = TargetDestination(
        application_name="Chat externo",
        window_id="win-1001",
        process_name="slack.exe",
        control_id="input-box-main",
        is_external=True,
        title="Chat del Equipo"
    )
    surface = VerifiableControlSurface(dest)
    return store, package, surface, e1, e2, e3


def test_mission_request_and_proposal_creation_and_digests():
    _, package, surface, e1, _, _ = setup_operator_case()
    operator = AntigravityAssistedOperator()
    req = operator.create_mission_request(package=package, surface=surface, task="Explicar error 422")
    assert req.mission_id.startswith("msn-")
    assert req.mode == "asistido"
    assert e1.event_id in req.allowed_sources
    assert req.digest is not None
    assert len(req.digest) == 64


def test_export_without_transfer_approval_fails():
    store, package, surface, _, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        with pytest.raises(PermissionError, match="autorización de transferencia explícita"):
            operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=None)


def test_export_with_mismatched_transfer_approval_fails():
    store, package, surface, _, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        fake_pkg = copy.deepcopy(package)
        fake_pkg["action"] = "action_fake"
        bad_approval = approve_transfer(fake_pkg, operator, actor="operador-humano")
        with pytest.raises(PermissionError, match="la autorización de transferencia no corresponde"):
            operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=bad_approval)


def test_export_with_restricted_source_fails_checkpoint():
    store, package, surface, _, e2, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        bad_package = copy.deepcopy(package)
        bad_package["additional_context"].append({
            "source": e2.event_id,
            "app": e2.application,
            "status": e2.epistemic_status,
            "content": e2.content
        })
        req = operator.create_mission_request(package=bad_package, surface=surface)
        t_approval = approve_transfer(bad_package, operator, actor="operador-humano")
        with pytest.raises(PermissionError, match="exportación rechazada por política"):
            operator.export_mission(req, tmpdir, store=store, package=bad_package, transfer_approval=t_approval)


def test_export_fails_if_request_outbound_payload_diverges_from_package():
    store, package, surface, _, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        t_approval = approve_transfer(package, operator, actor="operador-humano")

        # Simular alteración del outbound_payload en memoria antes de exportar
        tampered_req = MissionRequest(
            mission_id=req.mission_id,
            task=req.task,
            action=req.action,
            package_hash=req.package_hash,
            payload_hash=req.payload_hash,
            target_application=req.target_application,
            target_id=req.target_id,
            allowed_sources=req.allowed_sources,
            outbound_payload={"action": req.action, "current_context": {}, "additional_context": [{"fake": "data"}]},
            operator_target=req.operator_target,
            mode=req.mode
        )
        with pytest.raises(ValueError, match="outbound_payload de la solicitud fue alterado"):
            operator.export_mission(tampered_req, tmpdir, store=store, package=package, transfer_approval=t_approval)


def test_assisted_export_and_import_flow():
    store, package, surface, e1, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        t_approval = approve_transfer(package, operator, actor="operador-humano")
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)
        assert exported["request_file"].exists()
        assert exported["prompt_file"].exists()

        res_data = {
            "proposal_id": "prop-test-01",
            "mission_id": req.mission_id,
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "El error 422 se debe al esquema Pydantic en FastAPI.",
            "citations": [e1.event_id],
            "operator_identity": "antigravity-ide:agent",
            "actions_requested": []
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        proposal = operator.import_proposal(res_file, req, store=store)
        assert proposal.mission_id == req.mission_id
        assert proposal.request_hash == req.digest
        assert proposal.payload_hash == req.payload_hash
        assert proposal.citations == [e1.event_id]
        assert proposal.mode == "asistido"


def test_response_with_mismatched_request_hash_fails_import():
    store, package, surface, e1, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        t_approval = approve_transfer(package, operator, actor="operador-humano")
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

        res_data = {
            "proposal_id": "prop-test-01",
            "mission_id": req.mission_id,
            "request_hash": "hash_falso_que_no_coincide_con_el_digest_de_la_solicitud_exacta",
            "payload_hash": req.payload_hash,
            "text": "Texto",
            "citations": [e1.event_id],
            "operator_identity": "antigravity-ide:agent"
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        with pytest.raises(ValueError, match="request_hash no coincide"):
            operator.import_proposal(res_file, req, store=store)


def test_response_with_unrelated_mission_fails_import():
    store, package, surface, e1, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        t_approval = approve_transfer(package, operator, actor="operador-humano")
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

        res_data = {
            "proposal_id": "prop-test-01",
            "mission_id": "msn-UNRELATED",
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "Texto",
            "citations": [e1.event_id],
            "operator_identity": "antigravity-ide:agent"
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        with pytest.raises(ValueError, match="misión no coincide"):
            operator.import_proposal(res_file, req, store=store)


def test_operator_citations_out_of_bounds_rejected():
    store, package, surface, _, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        t_approval = approve_transfer(package, operator, actor="operador-humano")
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

        res_data = {
            "proposal_id": "prop-bad-01",
            "mission_id": req.mission_id,
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "Respuesta con fuente no autorizada",
            "citations": ["evt-forged-99999999999999999999999999999999"],
            "operator_identity": "antigravity-ide:agent"
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        with pytest.raises(ValueError, match="fuentes autorizadas"):
            operator.import_proposal(res_file, req, store=store)


def test_import_proposal_rejects_hashes_mismatched_with_sqlite_record():
    store, package, surface, e1, _, _ = setup_operator_case()
    with tempfile.TemporaryDirectory() as tmpdir:
        operator = AntigravityAssistedOperator(run_dir=tmpdir, store=store)
        req = operator.create_mission_request(package=package, surface=surface)
        t_approval = approve_transfer(package, operator, actor="operador-humano")
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

        # Modificar en memoria la tarea en el objeto request manteniendo mission_id
        mutated_req = MissionRequest(
            mission_id=req.mission_id,
            task="Tarea modificada a espaldas de SQLite",
            action=req.action,
            package_hash=req.package_hash,
            payload_hash=req.payload_hash,
            target_application=req.target_application,
            target_id=req.target_id,
            allowed_sources=req.allowed_sources,
            outbound_payload=req.outbound_payload,
            operator_target=req.operator_target,
            mode=req.mode
        )
        res_data = {
            "proposal_id": "prop-mutated",
            "mission_id": req.mission_id,
            "request_hash": mutated_req.digest,
            "payload_hash": mutated_req.payload_hash,
            "text": "Texto",
            "citations": [e1.event_id],
            "operator_identity": "antigravity-ide:agent"
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        # import_proposal debe rechazar porque el digest difiere del guardado en SQLite
        with pytest.raises(ValueError, match="no coinciden con el registro persistente"):
            operator.import_proposal(res_file, mutated_req, store=store)


def test_e2e_antigravity_assisted_flow_complete():
    store, package, surface, e1, e2, _ = setup_operator_case()
    outbound = provider_payload(package)
    assert "TOKEN_SECRETO" not in json.dumps(outbound)
    assert any(ex["reason"] == "restricted_no_transfer" for ex in package["excluded_context"])

    operator = AntigravityAssistedOperator(store=store)
    req = operator.create_mission_request(package=package, surface=surface)
    t_approval = approve_transfer(package, operator, actor="operador-humano")

    with tempfile.TemporaryDirectory() as tmpdir:
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

        res_data = {
            "proposal_id": "prop-live-01",
            "mission_id": req.mission_id,
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "Corregir validación en api.py según evidencia.",
            "citations": [e1.event_id],
            "operator_identity": operator.operator_identity,
            "actions_requested": []
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        proposal = operator.import_proposal(res_file, req, store=store)
        prep = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
        assert prep["status"] == "draft_ready"
        draft = prep["draft"]

        ins_approval = approve_insertion(draft, actor="operador-humano")
        res = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
        assert res["status"] == "inserted_not_sent"
        assert surface.verify_inserted(draft["text"]) is True
        assert store.verify_chain() is True


def test_e2e_antigravity_focus_loss_blocks_insertion():
    store, package, surface, e1, _, _ = setup_operator_case()
    operator = AntigravityAssistedOperator(store=store)
    req = operator.create_mission_request(package=package, surface=surface)
    t_approval = approve_transfer(package, operator, actor="operador-humano")

    with tempfile.TemporaryDirectory() as tmpdir:
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)
        res_data = {
            "proposal_id": "prop-focus-01",
            "mission_id": req.mission_id,
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "Texto",
            "citations": [e1.event_id],
            "operator_identity": operator.operator_identity
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        operator.import_proposal(res_file, req, store=store)
        prep = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
        draft = prep["draft"]
        ins_approval = approve_insertion(draft, actor="operador-humano")

        # Simular pérdida de foco o cambio de ventana en el sistema
        surface.set_active(False)

        res = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
        assert res["status"] == "blocked"
        assert res["reason"] == "destino_inactivo"


def test_e2e_antigravity_tampered_readback_fails_insertion():
    store, package, surface, e1, _, _ = setup_operator_case()
    operator = AntigravityAssistedOperator(store=store)
    req = operator.create_mission_request(package=package, surface=surface)
    t_approval = approve_transfer(package, operator, actor="operador-humano")

    with tempfile.TemporaryDirectory() as tmpdir:
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)
        res_data = {
            "proposal_id": "prop-tamper-01",
            "mission_id": req.mission_id,
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "Texto original",
            "citations": [e1.event_id],
            "operator_identity": operator.operator_identity
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        operator.import_proposal(res_file, req, store=store)
        prep = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
        draft = prep["draft"]
        ins_approval = approve_insertion(draft, actor="operador-humano")

        # Simular que el texto leído en el control difiere del enviado
        surface.simulate_tampering(True)

        res = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
        assert res["status"] == "insert_failed"


def test_e2e_antigravity_replay_blocked():
    store, package, surface, e1, _, _ = setup_operator_case()
    operator = AntigravityAssistedOperator(store=store)
    req = operator.create_mission_request(package=package, surface=surface)
    t_approval = approve_transfer(package, operator, actor="operador-humano")

    with tempfile.TemporaryDirectory() as tmpdir:
        exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)
        res_data = {
            "proposal_id": "prop-replay-01",
            "mission_id": req.mission_id,
            "request_hash": req.digest,
            "payload_hash": req.payload_hash,
            "text": "Texto de un solo uso",
            "citations": [e1.event_id],
            "operator_identity": operator.operator_identity
        }
        res_file = exported["mission_dir"] / "response.json"
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        operator.import_proposal(res_file, req, store=store)
        prep = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
        draft = prep["draft"]
        ins_approval = approve_insertion(draft, actor="operador-humano")

        res1 = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
        assert res1["status"] == "inserted_not_sent"

        # Reintento con el mismo borrador debe ser bloqueado
        res2 = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
        assert res2["status"] == "blocked"
        assert res2["reason"] == "borrador_alterado_o_ya_intentado"


def test_mission_consumption_prevents_proposal_reuse_across_reopen():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = pathlib.Path(tmpdir) / "test_store.sqlite"
        store = EventStore(str(db_path))
        reopened_store = None
        try:
            e1 = ObservationEvent(kind="content_observed", application="VS Code", ts=100.0,
                                  content="FastAPI endpoint error 422 en validación", permission_scope="may_transfer")
            e2 = ObservationEvent(kind="window_focus", application="Chat externo", ts=105.0,
                                  content="¿Por qué FastAPI devuelve error 422?", permission_scope="may_transfer")
            store.add(e1)
            store.add(e2)
            episodes = build_episodes(store.all())
            package = ContextBuilder().build(action="reply_with_muse", target_application="Chat externo",
                                             current_content=e2.content, episodes=episodes, target_is_external=True)
            dest = TargetDestination("Chat externo", "win-1", "chat.exe", "ctrl-1")
            surface = VerifiableControlSurface(dest)

            operator = AntigravityAssistedOperator(store=store)
            req = operator.create_mission_request(package=package, surface=surface)
            t_approval = approve_transfer(package, operator, actor="operador-humano")
            exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

            res_data = {
                "proposal_id": "prop-01",
                "mission_id": req.mission_id,
                "request_hash": req.digest,
                "payload_hash": req.payload_hash,
                "text": "Respuesta técnica basada en FastAPI 422",
                "citations": [e1.event_id],
                "operator_identity": operator.identity
            }
            res_file = exported["mission_dir"] / "response.json"
            res_file.write_text(json.dumps(res_data), encoding="utf-8")

            operator.import_proposal(res_file, req, store=store)

            # Primer prepare_reply consume la misión
            prep1 = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
            assert prep1["status"] == "draft_ready"

            # Cerrar el almacén y reabrirlo
            store.close()
            reopened_store = EventStore(str(db_path))
            operator_reopened = AntigravityAssistedOperator(store=reopened_store)

            # Intentar reutilizar la misma propuesta en el almacén reabierto DEBE fallar (consumida)
            with pytest.raises(ValueError, match="ya fue consumida previamente"):
                operator_reopened.import_proposal(res_file, req, store=reopened_store)
        finally:
            try:
                store.close()
            except Exception:
                pass
            if reopened_store:
                try:
                    reopened_store.close()
                except Exception:
                    pass


def test_windows_probe_surface_insert_raises_not_implemented():
    dest = TargetDestination("TestApp", "HWND-1", "test.exe", "ctrl-1")
    probe = WindowsProbeSurface(dest)
    with pytest.raises(NotImplementedError, match="únicamente un sensor de lectura"):
        probe.insert("texto")


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ControlSurface")
def test_real_win32_control_surface_insertion_and_readback():
    dest = TargetDestination("TestApp", "HWND-WIN32", "test.exe", "edit-01")
    surface = Win32ControlSurface(dest, auto_create=True)
    try:
        assert surface.is_target_active() is True
        sample_text = "Prueba de inserción real en control EDIT Win32 de Windows."
        inserted = surface.insert(sample_text)
        assert inserted is True
        verified = surface.verify_inserted(sample_text)
        assert verified is True
        assert surface.verify_inserted("Otro texto") is False
    finally:
        surface.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32ControlSurface")
def test_win32_control_hwnd_swap_fails_insertion():
    """Contraejemplo de Codex: si se cambia el HWND de la superficie tras aprobar, la inserción debe ser bloqueada."""
    store, package, _, e1, _, _ = setup_operator_case()
    dest_a = TargetDestination("Chat externo", "HWND-A", "python.exe", "ctrl-A", is_external=True)
    dest_b = TargetDestination("Chat externo", "HWND-B", "python.exe", "ctrl-B", is_external=True)

    surface_a = Win32ControlSurface(dest_a, auto_create=True)
    surface_b = Win32ControlSurface(dest_b, auto_create=True)

    try:
        # Preparamos y aprobamos para la superficie A
        operator = AntigravityAssistedOperator(store=store)
        req = operator.create_mission_request(package=package, surface=surface_a)
        t_approval = approve_transfer(package, operator, actor="operador-humano")

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)
            res_data = {
                "proposal_id": "prop-swap-01",
                "mission_id": req.mission_id,
                "request_hash": req.digest,
                "payload_hash": req.payload_hash,
                "text": "Texto para A",
                "citations": [e1.event_id],
                "operator_identity": operator.identity
            }
            res_file = exported["mission_dir"] / "response.json"
            res_file.write_text(json.dumps(res_data), encoding="utf-8")

            operator.import_proposal(res_file, req, store=store)
            prep = prepare_reply(store=store, package=package, provider=operator, surface=surface_a, transfer_approval=t_approval)
            draft = prep["draft"]
            ins_approval = approve_insertion(draft, actor="operador-humano")

            # Simulamos el sondeo de Codex: alterar surface_a.hwnd para apuntar al control B
            surface_a.hwnd = surface_b.hwnd

            # La inserción DEBE ser bloqueada porque is_target_active() detecta el handle swap
            res = insert_reply(store=store, draft=draft, surface=surface_a, approval=ins_approval)
            assert res["status"] == "blocked"

            # Y el control B NO debe tener el texto
            assert surface_b.verify_inserted(draft["text"]) is False
    finally:
        surface_a.close()
        surface_b.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32TestHost")
def test_interprocess_win32_assisted_flow_complete():
    """Recorrido asistido completo con control nativo en proceso host independiente persistente."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        status_file = tmp_path / "host_status.json"
        db_path = tmp_path / "assisted_memory.sqlite"
        store = EventStore(str(db_path))

        e1 = ObservationEvent(kind="content_observed", application="VS Code", ts=100.0,
                              content="FastAPI endpoint error 422 en validación", permission_scope="may_transfer")
        e2 = ObservationEvent(kind="window_focus", application="Win32TestHost", ts=105.0,
                              content="¿Por qué FastAPI devuelve error 422?", permission_scope="may_transfer")
        store.add(e1)
        store.add(e2)
        episodes = build_episodes(store.all())
        package = ContextBuilder().build(action="reply_with_muse", target_application="Win32TestHost",
                                         current_content=e2.content, episodes=episodes, target_is_external=True)

        host = Win32TestHost(status_file=status_file, title="TestHostWindow")
        host.start()
        try:
            assert host.is_alive() is True
            surface = Win32ControlSurface(host.destination, hwnd=host.hwnd)

            operator = AntigravityAssistedOperator(store=store)
            req = operator.create_mission_request(package=package, surface=surface)
            t_approval = approve_transfer(package, operator, actor="operador-humano")

            # Paso 1: Exportar misión
            exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

            # Paso 2: Operador genera respuesta válida
            res_data = {
                "proposal_id": "prop-interproc-01",
                "mission_id": req.mission_id,
                "request_hash": req.digest,
                "payload_hash": req.payload_hash,
                "text": "Solución técnica para el error 422 validada.",
                "citations": [e1.event_id],
                "operator_identity": operator.identity
            }
            res_file = exported["mission_dir"] / "response.json"
            res_file.write_text(json.dumps(res_data), encoding="utf-8")

            # Paso 3: Continuación (importar, preparar, aprobar e insertar en proceso separado/continuación)
            proposal = operator.import_proposal(res_file, req, store=store)
            prep = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
            draft = prep["draft"]
            ins_approval = approve_insertion(draft, actor="operador-humano")

            res = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
            assert res["status"] == "inserted_not_sent"
            assert surface.verify_inserted(draft["text"]) is True

            # Verificar que el control en el host independiente recibió y contiene el texto
            assert store.verify_chain() is True

            # Rechazo de repetición
            res_replay = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
            assert res_replay["status"] == "blocked"
        finally:
            host.stop()
            store.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para Win32TestHost")
def test_interprocess_win32_destination_closed_rejects_continuation():
    """Si el destino Win32 desaparece tras la aprobación, la continuación debe rechazar sin recrearlo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        status_file = tmp_path / "host_status.json"
        db_path = tmp_path / "assisted_memory.sqlite"
        store = EventStore(str(db_path))

        e1 = ObservationEvent(kind="content_observed", application="VS Code", ts=100.0,
                              content="FastAPI endpoint error 422 en validación", permission_scope="may_transfer")
        e2 = ObservationEvent(kind="window_focus", application="Win32TestHost", ts=105.0,
                              content="¿Por qué FastAPI devuelve error 422?", permission_scope="may_transfer")
        store.add(e1)
        store.add(e2)
        episodes = build_episodes(store.all())
        package = ContextBuilder().build(action="reply_with_muse", target_application="Win32TestHost",
                                         current_content=e2.content, episodes=episodes, target_is_external=True)

        host = Win32TestHost(status_file=status_file, title="TestHostWindowClosing")
        host.start()
        try:
            assert host.is_alive() is True
            surface = Win32ControlSurface(host.destination, hwnd=host.hwnd)

            operator = AntigravityAssistedOperator(store=store)
            req = operator.create_mission_request(package=package, surface=surface)
            t_approval = approve_transfer(package, operator, actor="operador-humano")

            # Paso 1: Exportar misión con control vivo
            exported = operator.export_mission(req, tmpdir, store=store, package=package, transfer_approval=t_approval)

            # Paso 2: El destino desaparece (se cierra la ventana o cae el proceso)
            host.stop()
            assert host.is_alive() is False

            # Paso 3: Operador entrega respuesta
            res_data = {
                "proposal_id": "prop-interproc-closed",
                "mission_id": req.mission_id,
                "request_hash": req.digest,
                "payload_hash": req.payload_hash,
                "text": "Texto para control desaparecido",
                "citations": [e1.event_id],
                "operator_identity": operator.identity
            }
            res_file = exported["mission_dir"] / "response.json"
            res_file.write_text(json.dumps(res_data), encoding="utf-8")

            # Paso 4: Continuación comprueba que el destino está muerto y RECHAZA sin recrearlo
            assert surface.is_target_active() is False

            # Si se intenta preparar/insertar, se bloquea por destino_inactivo
            operator.import_proposal(res_file, req, store=store)
            prep = prepare_reply(store=store, package=package, provider=operator, surface=surface, transfer_approval=t_approval)
            draft = prep["draft"]
            ins_approval = approve_insertion(draft, actor="operador-humano")

            res = insert_reply(store=store, draft=draft, surface=surface, approval=ins_approval)
            assert res["status"] == "blocked"
            assert res["reason"] == "destino_inactivo"
        finally:
            if host.is_alive():
                host.stop()
            store.close()

