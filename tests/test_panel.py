"""Pruebas del Panel Local de Revisión y Servidor HTTP Seguro.

Verifica rigurosamente:
1. Servidor HTTP interactuando con controles Win32 reales (vía Win32TestHost) sin bloqueos en SendMessageW.
2. Seguridad y autenticación de sesión:
   - Rechazo de peticiones sin token de sesión (403 Forbidden).
   - Rechazo de peticiones con origen o Host ajeno/malicioso (403 Forbidden).
   - Aceptación únicamente de peticiones autenticadas y de origen local idéntico (same-origin).
3. Importación auditable de response.json:
   - Si response.json existe, se conserva intacto y no se sobrescribe con texto de fixture.
   - Generador de fixture sintético separado y etiquetado.
4. Aislamiento de demostraciones de manipulación:
   - Las pruebas de alteración de PID o borrado de procedencia operan sobre copias temporales aisladas.
   - El historial compartido en SQLite permanece íntegro e inalterado (verify_chain() == True).
5. Manejo explícito de rechazo y repetición:
   - Los fallos e intentos de replay reportan delivery_result['status'] == 'blocked' y readback_verified == False.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
import urllib.error
import urllib.request
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from muse_env.panel.engine import PanelEngine
from muse_env.panel.server import ReviewPanelServer


def make_request(base_url: str, path: str, method: str = "GET", data: dict | None = None, headers: dict | None = None):
    url = f"{base_url}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req_headers = {"Connection": "close"}
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    r = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(r, timeout=8.0) as resp:
        return resp.status, resp.read().decode("utf-8")


@pytest.mark.skipif(sys.platform != "win32", reason="Requiere Windows para controles Win32 reales")
def test_panel_http_server_with_real_win32_controls(tmp_path):
    """Comprueba el ciclo HTTP completo sobre controles nativos Win32 reales (Win32TestHost) sin bloqueos."""
    db_file = tmp_path / "panel_real_win32.sqlite"
    runs_dir = tmp_path / "runs_real"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=False)
    server = ReviewPanelServer(host="127.0.0.1", port=8994, engine=engine)
    server.start_background()
    time.sleep(0.3)

    base_url = "http://127.0.0.1:8994"
    auth_headers = {"X-Session-Token": server.session_token}

    try:
        # 1. GET / (HTML con token inyectado)
        status, html = make_request(base_url, "/")
        assert status == 200
        assert server.session_token in html

        # 2. GET /api/state (Petición de solo lectura)
        status, state_raw = make_request(base_url, "/api/state")
        assert status == 200
        state = json.loads(state_raw)
        assert state["opt_in"] is False
        assert len(state["surfaces"]) == 3
        # HWNDs reales del sistema
        assert state["surfaces"][0]["hwnd"] > 0
        assert state["surfaces"][0]["pid"] > 0

        # 3. POST /api/opt_in (Con autenticación)
        status, opt_raw = make_request(base_url, "/api/opt_in", method="POST", data={"enabled": True}, headers=auth_headers)
        assert status == 200
        assert json.loads(opt_raw)["opt_in"] is True

        # 4. POST /api/observe (Observación nativa real de Windows sin bloqueo)
        status, obs_raw = make_request(base_url, "/api/observe", method="POST", headers=auth_headers)
        assert status == 200
        obs = json.loads(obs_raw)
        assert obs["status"] == "observed"
        assert len(obs["observations"]) >= 2

        # 5. POST /api/build_context
        status, ctx_raw = make_request(base_url, "/api/build_context", method="POST", data={"query": "FastAPI error 422 limit"}, headers=auth_headers)
        assert status == 200
        ctx = json.loads(ctx_raw)
        assert ctx["status"] == "package_built"

        # 6. POST /api/authorize_transfer (Compuerta 1)
        status, t_raw = make_request(base_url, "/api/authorize_transfer", method="POST", data={"actor": "test-operator"}, headers=auth_headers)
        assert status == 200
        t = json.loads(t_raw)
        assert t["status"] == "transfer_approved"

        # 7. POST /api/generate_fixture_proposal (Generación separada de fixture)
        status, prop_raw = make_request(base_url, "/api/generate_fixture_proposal", method="POST", headers=auth_headers)
        assert status == 200
        prop = json.loads(prop_raw)
        assert prop["status"] == "proposal_staged_and_draft_ready"
        assert prop["nature"] == "respuesta_de_prueba_automatizada (fixture)"

        # 8. POST /api/approve_insertion (Compuerta 2)
        status, ins_raw = make_request(base_url, "/api/approve_insertion", method="POST", data={"actor": "test-operator"}, headers=auth_headers)
        assert status == 200
        ins = json.loads(ins_raw)
        assert ins["status"] == "insertion_approved"

        # 9. POST /api/execute_insertion (Inserción Win32 real en HWND y readback verificado)
        status, exec_raw = make_request(base_url, "/api/execute_insertion", method="POST", headers=auth_headers)
        assert status == 200
        exec_res = json.loads(exec_raw)
        assert exec_res["status"] == "inserted_not_sent"
        assert exec_res["readback_verified"] is True
        assert exec_res["chain_valid"] is True
        assert exec_res["mission_consumed"] is True

        # 10. Replay prevention: reintentar inserción debe ser bloqueado por el ledger
        status, replay_raw = make_request(base_url, "/api/execute_insertion", method="POST", headers=auth_headers)
        assert status == 200
        replay_res = json.loads(replay_raw)
        assert replay_res["status"] == "blocked"
        assert replay_res["reason"] == "borrador_alterado_o_ya_intentado"
        assert replay_res["readback_verified"] is False

    finally:
        server.close()


def test_panel_security_session_and_origin_validation(tmp_path):
    """Comprueba el rechazo de peticiones sin token o con origen ajeno."""
    db_file = tmp_path / "panel_sec.sqlite"
    runs_dir = tmp_path / "runs_sec"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    server = ReviewPanelServer(host="127.0.0.1", port=8995, engine=engine)
    server.start_background()
    time.sleep(0.3)

    base_url = "http://127.0.0.1:8995"

    try:
        # 1. Petición POST sin token de sesión debe ser rechazada con 403
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            make_request(base_url, "/api/opt_in", method="POST", data={"enabled": True})
        assert exc_info.value.code == 403

        # 2. Petición POST con token de sesión inválido debe ser rechazada con 403
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            make_request(base_url, "/api/opt_in", method="POST", data={"enabled": True}, headers={"X-Session-Token": "token-falso-invalido"})
        assert exc_info.value.code == 403

        # 3. Petición con origen ajeno (CSRF / DNS rebinding) debe ser rechazada con 403
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            make_request(base_url, "/api/opt_in", method="POST", data={"enabled": True},
                         headers={"X-Session-Token": server.session_token, "Origin": "http://sitio-malicioso.com"})
        assert exc_info.value.code == 403

        # 4. Petición legítima con token y origen local debe ser aceptada (200 OK)
        status, res_raw = make_request(base_url, "/api/opt_in", method="POST", data={"enabled": True},
                                      headers={"X-Session-Token": server.session_token, "Origin": f"http://127.0.0.1:8995"})
        assert status == 200
        assert json.loads(res_raw)["opt_in"] is True

    finally:
        server.close()


def test_panel_proposal_import_does_not_overwrite_existing(tmp_path):
    """Comprueba que response.json redactado por el operador se conserva intacto al importarlo."""
    db_file = tmp_path / "panel_prop.sqlite"
    runs_dir = tmp_path / "runs_prop"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    try:
        engine.set_opt_in(True)
        engine.observe()
        engine.build_context()
        engine.authorize_transfer(actor="operador-humano")

        mission_dir = engine.mission_info["mission_dir"]
        res_file = mission_dir / "response.json"

        # Escribir una respuesta personalizada del operador (NO el fixture fijo)
        texto_operador_autentico = "RESPUESTA PERSONALIZADA Y AUTENTICA DEL OPERADOR HUMANO PARA VALIDACION"
        custom_data = {
            "proposal_id": f"prop-custom-{engine.mission_request.mission_id[-6:]}",
            "mission_id": engine.mission_request.mission_id,
            "request_hash": engine.mission_request.digest,
            "payload_hash": engine.mission_request.payload_hash,
            "text": texto_operador_autentico,
            "citations": [engine.mission_request.allowed_sources[0]],
            "operator_identity": "operador-manual:antigravity",
            "actions_requested": []
        }
        res_file.write_text(json.dumps(custom_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Importar la propuesta existente
        import_res = engine.import_proposal()
        assert import_res["status"] == "proposal_staged_and_draft_ready"
        assert import_res["text"] == texto_operador_autentico
        # El archivo en disco no acredita autoría humana; se etiqueta con honestidad
        assert import_res["nature"] == "archivo_importado_sin_atribucion_verificada"

        # Comprobar que el archivo en disco NO fue sobrescrito
        disk_content = json.loads(res_file.read_text(encoding="utf-8"))
        assert disk_content["text"] == texto_operador_autentico
        assert "FastAPI devuelve error 422" not in disk_content["text"]

    finally:
        engine.close()


def test_panel_proposal_import_synthetic_fixture_honest_label(tmp_path):
    """Comprueba que un archivo explícitamente sintético es etiquetado como fixture sintético al importarlo."""
    db_file = tmp_path / "panel_synth.sqlite"
    runs_dir = tmp_path / "runs_synth"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    try:
        engine.set_opt_in(True)
        engine.observe()
        engine.build_context()
        engine.authorize_transfer(actor="operador-humano")

        mission_dir = engine.mission_info["mission_dir"]
        res_file = mission_dir / "response.json"

        synthetic_data = {
            "proposal_id": f"prop-fixture-{engine.mission_request.mission_id[-6:]}",
            "mission_id": engine.mission_request.mission_id,
            "request_hash": engine.mission_request.digest,
            "payload_hash": engine.mission_request.payload_hash,
            "text": "Respuesta sintética generada automáticamente para pruebas (fixture mock)",
            "citations": [engine.mission_request.allowed_sources[0]],
            "operator_identity": "mock:synthetic-fixture-generator",
            "actions_requested": []
        }
        res_file.write_text(json.dumps(synthetic_data, indent=2, ensure_ascii=False), encoding="utf-8")

        import_res = engine.import_proposal()
        assert import_res["status"] == "proposal_staged_and_draft_ready"
        assert import_res["nature"] == "archivo_importado_sintetico (fixture)"

    finally:
        engine.close()


def test_panel_decoupled_surface_permissions(tmp_path):
    """Comprueba que modificar autorización o captura NO altera ni fuerza permission_scope."""
    db_file = tmp_path / "panel_decoupled.sqlite"
    runs_dir = tmp_path / "runs_decoupled"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    try:
        engine.set_opt_in(True)
        # Obtenemos la primera superficie
        hwnd = engine.s1.hwnd

        # 1. Configurar inicialmente a restricted
        r1 = engine.configure_surface(hwnd=hwnd, authorized=True, capture_allowed=False, permission_scope="restricted")
        assert r1["is_authorized"] is True
        assert r1["capture_allowed"] is False
        assert r1["permission_scope"] == "restricted"

        # 2. Modificar ÚNICAMENTE capture_allowed: no debe tocar permission_scope ni authorized
        r2 = engine.configure_surface(hwnd=hwnd, capture_allowed=True)
        assert r2["capture_allowed"] is True
        assert r2["is_authorized"] is True
        assert r2["permission_scope"] == "restricted", "permission_scope debió permanecer intacto como restricted"

        # 3. Modificar ÚNICAMENTE authorized a False: no debe tocar permission_scope
        r3 = engine.configure_surface(hwnd=hwnd, authorized=False)
        assert r3["is_authorized"] is False
        assert r3["capture_allowed"] is True
        assert r3["permission_scope"] == "restricted"

        # 4. Modificar ÚNICAMENTE permission_scope a local-only: no debe tocar authorized ni capture_allowed
        r4 = engine.configure_surface(hwnd=hwnd, permission_scope="local-only")
        assert r4["permission_scope"] == "local-only"
        assert r4["is_authorized"] is False
        assert r4["capture_allowed"] is True

    finally:
        engine.close()


def test_panel_exact_host_and_port_rejection(tmp_path):
    """Comprueba que peticiones HTTP con puerto incorrecto o Host impreciso son rechazadas con 403."""
    db_file = tmp_path / "panel_host_sec.sqlite"
    runs_dir = tmp_path / "runs_host_sec"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    port = 8996
    server = ReviewPanelServer(host="127.0.0.1", port=port, engine=engine)
    server.start_background()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{port}"
    auth_headers = {"X-Session-Token": server.session_token}

    try:
        # 1. Host con puerto falso/diferente debe ser rechazado con 403
        bad_headers = dict(auth_headers)
        bad_headers["Host"] = f"127.0.0.1:{port}0"  # ej. 89960
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            make_request(base_url, "/api/state", headers=bad_headers)
        assert exc_info.value.code == 403

        # 2. Host sin puerto debe ser rechazado con 403
        bad_headers["Host"] = "127.0.0.1"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            make_request(base_url, "/api/state", headers=bad_headers)
        assert exc_info.value.code == 403

        # 3. Host exacto debe ser aceptado
        good_headers = dict(auth_headers)
        good_headers["Host"] = f"127.0.0.1:{port}"
        status, _ = make_request(base_url, "/api/state", headers=good_headers)
        assert status == 200

    finally:
        server.close()


def test_panel_check_readback_endpoint_and_discrepancy(tmp_path):
    """Comprueba el endpoint /api/check_readback y la detección estricta de readback_verified."""
    db_file = tmp_path / "panel_readback.sqlite"
    runs_dir = tmp_path / "runs_readback"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    server = ReviewPanelServer(host="127.0.0.1", port=8997, engine=engine)
    server.start_background()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{port_placeholder}" if False else f"http://127.0.0.1:8997"
    auth_headers = {"X-Session-Token": server.session_token}

    try:
        engine.set_opt_in(True)
        engine.observe()
        engine.build_context()
        engine.authorize_transfer(actor="operador-humano")
        engine.generate_fixture_proposal()
        engine.approve_insertion(actor="operador-humano")

        # Inserción normal con readback exitoso
        status, exec_raw = make_request(base_url, "/api/execute_insertion", method="POST", headers=auth_headers)
        assert status == 200
        exec_res = json.loads(exec_raw)
        assert exec_res["status"] == "inserted_not_sent"
        assert exec_res["readback_verified"] is True

        # Reverificación de readback vía endpoint
        status, chk_raw = make_request(base_url, "/api/check_readback", method="POST", headers=auth_headers)
        assert status == 200
        chk_res = json.loads(chk_raw)
        assert chk_res["readback_verified"] is True

        # Simular discrepancia alterando el texto del control de destino
        engine.target.insert("Texto alterado por un proceso concurrente o usuario externo")

        # Al reverificar, readback_verified DEBE ser False
        status, chk_fail_raw = make_request(base_url, "/api/check_readback", method="POST", headers=auth_headers)
        assert status == 200
        chk_fail = json.loads(chk_fail_raw)
        assert chk_fail["readback_verified"] is False
        assert chk_fail["reason"] == "discrepancia_texto_en_control"

        # Verificar que el estado expone delivery_result con readback_verified=False
        state = engine.get_state()
        assert state["delivery_result"]["readback_verified"] is False

    finally:
        server.close()


def test_panel_tamper_demo_does_not_modify_shared_history(tmp_path):
    """Comprueba que las demostraciones de alteración operan sobre copias aisladas y no tocan la base compartida."""
    db_file = tmp_path / "panel_tamper.sqlite"
    runs_dir = tmp_path / "runs_tamper"

    engine = PanelEngine(db_path=db_file, runs_dir=runs_dir, use_mock_surfaces=True)
    try:
        engine.set_opt_in(True)
        engine.observe()

        # Comprobar estado inicial del ledger
        assert engine.store.verify_chain() is True

        # Ejecutar demostración interactiva de alteración de PID
        tamper_res = engine.tamper_provenance_test("pid")
        assert tamper_res["detected"] is True
        assert tamper_res["chain_valid"] is False  # En la copia temporal aislada es False
        assert tamper_res["shared_chain_valid"] is True  # En la base compartida es True

        # Verificar que la base de datos compartida NO fue alterada
        assert engine.store.verify_chain() is True, "La base compartida no debe sufrir alteraciones por la demo"

        # Ejecutar demostración interactiva de eliminación
        delete_res = engine.tamper_provenance_test("delete")
        assert delete_res["detected"] is True
        assert delete_res["chain_valid"] is False
        assert delete_res["shared_chain_valid"] is True

        # La base compartida sigue completamente íntegra
        assert engine.store.verify_chain() is True

    finally:
        engine.close()


def test_panel_engine_instantiates_fuse_and_evaluates_on_deliverable(tmp_path):
    """A2: Verify PanelEngine instantiates TrajectorySensor and evaluates it on execute_deliverable."""
    db_p = tmp_path / "panel_obs.sqlite"
    pm_p = tmp_path / "panel_pm.sqlite"
    engine = PanelEngine(db_path=db_p, runs_dir=tmp_path, use_mock_surfaces=True, project_memory_path=pm_p)
    try:
        assert engine.fuse_sensor is not None, "fuse_sensor must be instantiated in PanelEngine"
        assert engine._fuse_session_start is not None

        engine.ingest_project_source("proj_fuse", "spec.md", "Reglas y especificaciones operativas.", scope="may_transfer")
        res_cp = engine.query_and_checkpoint("proj_fuse", "especificaciones", capability="deliverable_production")
        mid = res_cp["mission_id"]
        prop = engine.run_capability_propose_deliverable(mid, title="Doc Fuse")

        # Execute deliverable through panel engine
        res = engine.run_capability_execute_deliverable(
            mid, target_dir="artifacts", filename="fuse_doc.md", approved_draft_sha256=prop["draft_sha256"]
        )
        assert res["readback_verified"] is True
        assert Path(res["artifact_path"]).exists()

        # Check that session turn index incremented and sensor observed the session
        assert engine._fuse_turn_index >= 1

        # Test B2 reset mechanism:
        res_reset = engine.reset_fuse_session()
        assert res_reset["status"] == "ok"

    finally:
        engine.store.close()
        engine.project_memory.close()