"""Regression tests for authorization, persistence and actual dispatch outcomes."""
import copy
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from muse_env.observer import SimulatedObserver, DEMO_SCRIPT
from muse_env.events import ObservationEvent
from muse_env.store import EventStore
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.providers import LocalStubProvider, MetaMuseProvider
from muse_env.invoke import (prepare_reply, insert_reply, approve_transfer,
                             approve_insertion, FakeSurface)
from muse_env.gate import TrajectorySensor, policy_per_turn


def setup_case():
    store = EventStore()
    for event in SimulatedObserver(DEMO_SCRIPT).stream():
        store.add(event)
    package = ContextBuilder().build(action="reply_with_muse", target_application="Chat externo",
        current_content=DEMO_SCRIPT[-1]["content"], episodes=build_episodes(store.all()), target_is_external=True)
    surface = FakeSurface("Chat externo")
    return store, package, surface


def draft_case():
    store, package, surface = setup_case()
    result = prepare_reply(store=store, package=package, provider=LocalStubProvider(), surface=surface)
    assert result["status"] == "draft_ready"
    return store, result["draft"], surface


class RemoteSpy(LocalStubProvider):
    is_external = True
    def __init__(self):
        self.calls = []
    def reply(self, payload):
        self.calls.append(copy.deepcopy(payload))
        return super().reply(payload)


def test_contexto_transversal_y_exclusiones():
    _, package, _ = setup_case()
    assert any("Pydantic" in item["content"] for item in package["additional_context"])
    assert any(item["reason"] == "restricted_no_transfer" for item in package["excluded_context"])
    assert "Credencial" not in json.dumps(provider_payload(package))
    assert "Notas privadas" not in json.dumps(provider_payload(package))
    assert "excluded_context" not in provider_payload(package)


def test_sin_aprobacion_de_transferencia_no_se_llama_al_proveedor():
    store, package, surface = setup_case()
    provider = RemoteSpy()
    result = prepare_reply(store=store, package=package, provider=provider, surface=surface)
    assert result["status"] == "transfer_not_approved"
    assert provider.calls == [] and surface.inserted == []


def test_transferencia_ligada_a_paquete_y_proveedor():
    store, package, surface = setup_case()
    provider = RemoteSpy()
    grant = approve_transfer(package, provider, actor="operador")
    changed = copy.deepcopy(package)
    changed["excluded_context"].append({"reason": "new_local_information"})
    assert prepare_reply(store=store, package=changed, provider=provider, surface=surface,
                         transfer_approval=grant)["status"] == "transfer_not_approved"
    assert provider.calls == []
    assert prepare_reply(store=store, package=package, provider=provider, surface=surface,
                         transfer_approval=grant)["status"] == "draft_ready"
    assert len(provider.calls) == 1 and "Notas privadas" not in json.dumps(provider.calls)


def test_sin_aprobacion_del_borrador_no_hay_insercion_y_no_hay_replay():
    store, draft, surface = draft_case()
    assert insert_reply(store=store, draft=draft, surface=surface)["status"] == "not_approved"
    assert surface.inserted == []
    approval = approve_insertion(draft, actor="operador")
    result = insert_reply(store=store, draft=draft, surface=surface, approval=approval)
    assert result["status"] == "inserted_not_sent"
    assert len(surface.inserted) == 1
    assert insert_reply(store=store, draft=draft, surface=surface, approval=approval)["status"] == "blocked"
    assert len(surface.inserted) == 1


def test_cambiar_borrador_invalida_aprobacion():
    store, draft, surface = draft_case()
    approval = approve_insertion(draft, actor="operador")
    draft["text"] = "alterado"
    assert insert_reply(store=store, draft=draft, surface=surface, approval=approval)["status"] == "blocked"
    assert surface.inserted == []


def test_cambiar_destino_invalida_aprobacion():
    store, draft, surface = draft_case()
    approval = approve_insertion(draft, actor="operador")
    other = FakeSurface(surface.name)
    assert insert_reply(store=store, draft=draft, surface=other, approval=approval)["status"] == "blocked"
    assert other.inserted == []


def test_destino_inconsistente_bloquea_antes_del_proveedor():
    store, package, _ = setup_case()
    provider = RemoteSpy()
    result = prepare_reply(store=store, package=package, provider=provider,
        surface=FakeSurface("other"), transfer_approval=approve_transfer(package, provider, actor="operador"))
    assert result["status"] == "blocked" and provider.calls == []


@pytest.mark.parametrize("scope", ["restricted", "local-only"])
def test_ventana_actual_no_autorizada_no_se_empaqueta(scope):
    event = ObservationEvent(kind="content_observed", application="Private", content="private current", permission_scope=scope)
    with pytest.raises(PermissionError):
        ContextBuilder().build(action="reply_with_muse", target_application="Private", current_content=event.content,
            episodes=build_episodes([event]), target_is_external=True)


def test_paquete_forjado_no_concede_permiso():
    store, package, surface = setup_case()
    private = next(event for event in store.all() if event.permission_scope == "restricted")
    package["additional_context"].append({"source": private.event_id, "app": private.application,
        "status": private.epistemic_status, "content": private.content})
    provider = RemoteSpy()
    result = prepare_reply(store=store, package=package, provider=provider, surface=surface,
        transfer_approval=approve_transfer(package, provider, actor="operador"))
    assert result["status"] == "blocked" and provider.calls == []


def test_contenido_forged_no_coincide_con_fuente():
    store, package, surface = setup_case()
    package["additional_context"][0]["content"] = "forged fact"
    assert prepare_reply(store=store, package=package, provider=LocalStubProvider(), surface=surface)["status"] == "blocked"


def test_proveedor_externo_no_recibe_datos_local_only_aunque_destino_sea_local():
    store = EventStore()
    event = store.add(ObservationEvent(kind="content_observed", application="Local", content="local data"))
    package = ContextBuilder().build(action="reply_with_muse", target_application="Local", current_content=event.content,
        episodes=build_episodes([event]), target_is_external=False)
    provider = RemoteSpy()
    result = prepare_reply(store=store, package=package, provider=provider, surface=FakeSurface("Local", is_external=False),
        transfer_approval=approve_transfer(package, provider, actor="operador"))
    assert result["status"] == "blocked" and provider.calls == []


def test_cadena_detecta_manipulacion_de_eventos_y_payloads():
    store, package, surface = setup_case()
    prepare_reply(store=store, package=package, provider=LocalStubProvider(), surface=surface)
    assert store.verify_chain()
    store.db.execute("UPDATE observations SET content='alterado' WHERE event_id=?", (package["current_context"]["source"],))
    store.db.commit()
    assert not store.verify_chain()
    second = EventStore()
    second.append_intervention("example", {"value": 1})
    second.db.execute("UPDATE interventions SET payload='{}'")
    second.db.commit()
    assert not second.verify_chain()


def test_cadena_registra_borrador_y_paquete_exactos():
    store, draft, _ = draft_case()
    logged = next(link["payload"]["draft"] for link in store.chain() if link["kind"] == "draft_ready")
    assert logged == draft
    proposed = next(link["payload"] for link in store.chain() if link["kind"] == "proposed")
    assert proposed["package"] == draft["package"]
    assert "Pydantic" in json.dumps(proposed["payload"])


def test_eventos_no_se_reemplazan_y_persisten_entre_procesos(tmp_path):
    database = str(tmp_path / "events.sqlite")
    code = "import sys; sys.path.insert(0,sys.argv[1]); from muse_env.store import EventStore; from muse_env.events import ObservationEvent; s=EventStore(sys.argv[2]); s.add(ObservationEvent(kind='content_observed',application='test',content=sys.argv[3])); s.close()"
    for content in ("first session", "second session"):
        subprocess.run([sys.executable, "-B", "-c", code, str(ROOT / "src"), database, content], check=True)
    store = EventStore(database)
    assert {event.content for event in store.all()} == {"first session", "second session"}
    assert store.verify_chain()
    with pytest.raises(sqlite3.IntegrityError):
        store.add(store.all()[0])
    assert len(store.all()) == 2 and store.verify_chain()
    store.close()


def test_ventana_temporal_se_respeta():
    events = [ObservationEvent(kind="content_observed", application="a", content="shared token", ts=1),
              ObservationEvent(kind="content_observed", application="b", content="shared token", ts=100000)]
    assert len(build_episodes(events, window_s=1)) == 2


def test_sensor_multiturno_corta_y_bloquea_insercion_real_del_stub():
    store, draft, surface = draft_case()
    sensor = TrajectorySensor()
    for t, score in enumerate([0.68, 0.72, 0.78]):
        assert not policy_per_turn(score)
        stopped = sensor.observe(score, effect="read", t=float(t))
    assert stopped
    result = insert_reply(store=store, draft=draft, surface=surface,
        approval=approve_insertion(draft, actor="operador"), sensor=sensor, risk_score=0.0, t=3)
    assert result["status"] == "blocked" and surface.inserted == []
    assert any(link["kind"] == "blocked_sensor" for link in store.chain())


def test_sensor_antes_del_proveedor_y_error_de_senal():
    store, package, surface = setup_case()
    provider = RemoteSpy()
    sensor = TrajectorySensor()
    result = prepare_reply(store=store, package=package, provider=provider, surface=surface,
        transfer_approval=approve_transfer(package, provider, actor="operador"), sensor=sensor, risk_score=float("nan"), t=1)
    assert result["status"] == "blocked" and provider.calls == []


def test_fallo_de_insercion_y_readback_no_se_reporta_como_exito():
    for fail_readback in (False, True):
        store, draft, surface = draft_case()
        if fail_readback:
            surface.verify_inserted = lambda text: False
        else:
            surface.insert = lambda text: False
        result = insert_reply(store=store, draft=draft, surface=surface,
                              approval=approve_insertion(draft, actor="operador"))
        assert result["status"] == "insert_failed"
        assert store.chain()[-1]["kind"] == "insert_failed"


def test_meta_sin_clave_falla(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        MetaMuseProvider()


def test_meta_parsea_http_no_inventa_citas_y_no_envia_exclusiones(monkeypatch):
    store, package, surface = setup_case()
    monkeypatch.setenv("MODEL_API_KEY", "DUMMY_NOT_A_KEY")
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({"status": "completed", "output": [{"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": "Respuesta sin citas"}]}]}).encode()
    def mocked(req, timeout):
        captured.append(json.loads(req.data))
        return Response()
    monkeypatch.setattr("urllib.request.urlopen", mocked)
    provider = MetaMuseProvider()
    result = prepare_reply(store=store, package=package, provider=provider, surface=surface,
        transfer_approval=approve_transfer(package, provider, actor="operador"))
    assert result["draft"]["text"] == "Respuesta sin citas"
    assert result["draft"]["citations"] == []
    assert result["draft"]["provided_sources"]
    assert captured[0]["store"] is False
    assert "Notas privadas" not in captured[0]["input"] and "excluded_context" not in captured[0]["input"]


def test_citas_ajenas_bloquean_borrador():
    class InvalidProvider(LocalStubProvider):
        def reply(self, payload):
            return {"text": "unsupported", "citations": ["invented-id"]}
    store, package, surface = setup_case()
    assert prepare_reply(store=store, package=package, provider=InvalidProvider(), surface=surface)["status"] == "provider_failed"
    assert surface.inserted == []


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf")])
def test_eventos_y_fuse_rechazan_tiempos_no_finitos(timestamp):
    with pytest.raises(ValueError):
        ObservationEvent(kind="content_observed", application="test", ts=timestamp)
    with pytest.raises(ValueError):
        TrajectorySensor().observe(0.5, effect="read", t=timestamp)


def test_calibracion_no_trunca_pesos_silenciosamente():
    from muse_env._fusible_vendor import calibrate_threshold
    with pytest.raises(ValueError):
        calibrate_threshold([[0.5, 0.6]], "i2t", benign_weights=[[1.0]])


def test_error_del_proveedor_no_produce_borrador_ni_insercion():
    class BrokenProvider(LocalStubProvider):
        def reply(self, payload):
            raise RuntimeError("failure")
    store, package, surface = setup_case()
    result = prepare_reply(store=store, package=package, provider=BrokenProvider(), surface=surface)
    assert result["status"] == "provider_failed" and surface.inserted == []
    assert store.chain()[-1]["kind"] == "provider_failed"


def test_visor_escapa_html_observado():
    import importlib.util
    spec = importlib.util.spec_from_file_location("viewer_module", ROOT / "make_viewer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store, draft, surface = draft_case()
    malicious = "<script>alert('test')</script>"
    data = {"activity": [{"application": malicious, "kind": "content_observed", "ts": 1,
             "permission_scope": "restricted", "content": "PRIVATE_BODY", "epistemic_status": "observed"}],
        "package": draft["package"], "meta_calls": 0, "persistence": {"reopened_ok": True, "after": 1},
        "invoke": {"draft": draft, "status": "draft_ready"},
        "ab": {"fuse_stop": 2, "attempt_status": "blocked", "blocked_insertions": 0},
        "chain_valid": True, "chain": store.chain()}
    html = module.render(data)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "PRIVATE_BODY" not in html
