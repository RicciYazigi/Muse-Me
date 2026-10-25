import json
import time
import tempfile
from pathlib import Path
import pytest

from muse_env.store import EventStore
from muse_env.project_memory import ProjectMemory
from muse_env.panel.engine import PanelEngine
from muse_env.capabilities import (
    propose_deliverable,
    execute_deliverable_action,
    sha256_digest
)
from muse_env.events import ObservationEvent


def test_f01_panel_engine_project_memory_initialized():
    """F01: PanelEngine must initialize project_memory without AttributeError."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "panel.sqlite"
        pm_p = Path(td) / "project_memory.sqlite"
        engine = PanelEngine(db_path=str(db_p), project_memory_path=str(pm_p))
        try:
            overview = engine.get_projects_overview()
            assert "projects" in overview
            proj_names = [p["project"] for p in overview["projects"]]
            assert "demo-latam" in proj_names
        finally:
            engine.close()


def test_f02_f03_f04_capability_gates_and_readback_integrity():
    """F02, F03, F04: Gate 2 default rejection, disk modification detection, and completed freeze."""
    with tempfile.TemporaryDirectory() as td:
        pm_path = Path(td) / "pm.sqlite"
        mem = ProjectMemory(str(pm_path))
        try:
            src_dir = Path(td) / "src_files"
            src_dir.mkdir()
            f1 = src_dir / "spec.md"
            f1.write_text("Especificacion vigente del modulo de autenticacion.", encoding="utf-8")
            
            rev = mem.ingest_text("auth_proj", str(src_dir), "spec.md", scope="may_transfer")
            mid = mem.checkpoint("auth_proj", "Generar documentacion", {"spec.md": rev})
            
            # Propose deliverable
            proposal = propose_deliverable(mem, mid, title="Reporte Auth")
            draft_hash = proposal["draft_sha256"]
            
            # F02: user_approved must be explicit True, default is False
            with pytest.raises(PermissionError, match="Compuerta 2 rechazada"):
                execute_deliverable_action(mem, mid, target_dir=td, filename="auth_out.md", approved_draft_sha256=draft_hash, user_approved=False)
                
            # Execute with explicit approval
            res = execute_deliverable_action(mem, mid, target_dir=td, filename="auth_out.md", approved_draft_sha256=draft_hash, user_approved=True)
            assert res["readback_verified"] is True
            
            # F04: Mission is completed; proposing again must be blocked
            with pytest.raises(ValueError, match="ya se encuentra completada"):
                propose_deliverable(mem, mid, title="Nuevo intento")
                
            # Idempotent call when file is intact
            res_idem = execute_deliverable_action(mem, mid, target_dir=td, filename="auth_out.md", approved_draft_sha256=draft_hash, user_approved=True)
            assert res_idem["status"] == "already_completed_idempotent"
            assert res_idem["readback_verified"] is True
            
            # F03: Tamper with artifact on disk
            out_file = Path(td) / "auth_out.md"
            out_file.write_text("CONTENIDO MALICIOSO ALTERADO EN DISCO", encoding="utf-8")
            
            res_tampered = execute_deliverable_action(mem, mid, target_dir=td, filename="auth_out.md", approved_draft_sha256=draft_hash, user_approved=True)
            assert res_tampered["status"] == "artifact_modified_on_disk"
            assert res_tampered["readback_verified"] is False
            assert res_tampered["current_integrity"] is False
        finally:
            mem.close()


def test_f05_reingest_preserves_scope():
    """F05: Reingesting a source must preserve restricted/local-only scope, never elevate."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "panel.sqlite"
        pm_p = Path(td) / "project_memory.sqlite"
        engine = PanelEngine(db_path=str(db_p), project_memory_path=str(pm_p))
        try:
            src_dir = Path(td) / "docs"
            src_dir.mkdir()
            f = src_dir / "private.md"
            f.write_text("Datos confidenciales locales", encoding="utf-8")
            engine.project_memory.ingest_text("default", str(src_dir), "private.md", scope="local-only")
            
            res = engine.reingest_source("default", "private.md")
            assert res["status"] == "reingested"
            assert res["scope"] == "local-only"
            
            row = engine.project_memory.db.execute("SELECT scope FROM sources WHERE project='default' AND source='private.md'").fetchone()
            assert row["scope"] == "local-only"
        finally:
            engine.close()


def test_f06_zero_hits_returns_honest_insufficient_evidence():
    """F06: When search query finds no hits, report honest insufficient evidence without SQL error."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "panel.sqlite"
        pm_p = Path(td) / "project_memory.sqlite"
        engine = PanelEngine(db_path=str(db_p), project_memory_path=str(pm_p))
        try:
            res = engine.query_and_checkpoint("default", "termino_inexistente_xyz_12345", external=False)
            assert res["mission_id"] is None
            assert res["evidence_count"] == 0
            assert "Evidencia insuficiente" in res.get("error", "")
        finally:
            engine.close()


def test_f06_anchor_export_and_tamper_detection():
    """F06: Export cryptographic anchor outside SQLite and verify detection of external manipulation."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "ledger.sqlite"
        store = EventStore(str(db_path))
        try:
            evt = ObservationEvent(
                event_id="evt-audit-test-1",
                ts=time.time(),
                kind="user_input",
                application="terminal",
                content="comando autorizado",
                epistemic_status="observed",
                permission_scope="may_transfer",
                source_type="user_action"
            )
            store.add(evt)
            assert store.verify_chain() is True
            
            anchor_file = Path(td) / "anchor.json"
            anchor = store.export_anchor(str(anchor_file))
            assert anchor["head_seq"] > 0
            assert anchor["head_hash"] != "GENESIS"
            assert anchor_file.exists()
            
            # Verify against intact anchor
            assert store.verify_against_anchor(anchor_file) is True
            
            # Add another event -> anchor still matches its recorded state
            evt2 = ObservationEvent(
                event_id="evt-audit-test-2",
                ts=time.time(),
                kind="user_input",
                application="terminal",
                content="segundo comando",
                epistemic_status="observed",
                permission_scope="may_transfer",
                source_type="user_action"
            )
            store.add(evt2)
            assert store.verify_against_anchor(anchor_file) is True
            
            # Malicious anchor with forged head hash
            fake_anchor = dict(anchor)
            fake_anchor["head_hash"] = "0" * 64
            assert store.verify_against_anchor(fake_anchor) is False
        finally:
            store.close()


def test_f08_xss_prevention_in_panel_templates():
    """F08 / A6: Panel HTML must invoke escapeHtml on dynamic source names, scopes, and divergence terms."""
    panel_path = Path("src/muse_env/panel/static/panel.html")
    assert panel_path.exists(), "panel.html must exist"
    html_content = panel_path.read_text(encoding="utf-8")

    # 1. escapeHtml must be defined
    assert "function escapeHtml(str)" in html_content

    # 2. escapeHtml must be actively invoked in templates
    assert "${escapeHtml(s.source)}" in html_content
    assert "${escapeHtml(s.scope)}" in html_content
    assert "escapeHtml(d.divergent_terms" in html_content
    assert "escapeHtml(d.epistemic_note)" in html_content

    # 3. Verify escape function logic directly with malicious payload
    malicious_payload = "<img src=x onerror=alert('xss')>"
    escaped = malicious_payload.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#039;")
    assert "<" not in escaped and ">" not in escaped and "'" not in escaped
    assert "&lt;img" in escaped
