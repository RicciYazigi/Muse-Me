import tempfile
from pathlib import Path
import pytest

from muse_env.gesture import MuseDesktopGesture
from muse_env.project_memory import ProjectMemory


def test_muse_desktop_gesture_unauthorized_and_authorized():
    """A4: Verify desktop gesture requires explicit authorization and relevant evidence (no blind dumps)."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "gesture_mem.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            doc_dir = Path(td) / "docs"
            doc_dir.mkdir()
            f = doc_dir / "politica_precios.md"
            f.write_text("Especificación de precios y tarifas aprobada.", encoding="utf-8")
            mem.ingest_text("test-proj", str(doc_dir), "politica_precios.md", scope="may_transfer")
        finally:
            mem.close()

        gesture = MuseDesktopGesture(memory_path=str(db_p))
        try:
            # 1. Trigger over unauthorized window HWND 0x1234 -> blocked
            res_unauth = gesture.trigger_gesture(target_hwnd=0x1234, project="test-proj")
            assert res_unauth["status"] == "blocked"
            assert res_unauth["gesture_action"] == "authorization_required"

            # 2. Authorize window HWND 0x1234
            gesture.observer.authorize_surface("Facturación App", hwnd=0x1234, permission_scope="may_transfer", window_title="Facturación Precios")

            # 3. Trigger without matching evidence -> must return insufficient_evidence, NEVER blind dump
            res_no_match = gesture.trigger_gesture(target_hwnd=0x1234, project="test-proj", goal="término completamente ajeno zzz")
            assert res_no_match["status"] == "insufficient_evidence"

            # 4. Trigger with legitimate relevant evidence matching 'precios'
            res_auth = gesture.trigger_gesture(target_hwnd=0x1234, project="test-proj", goal="consulta de precios y tarifas")
            assert res_auth["status"] == "proposal_ready"
            assert res_auth["gesture_action"] == "reply_with_muse"
            assert res_auth["requires_gate2_human_approval"] is True
            assert len(res_auth["draft_sha256"]) == 64
        finally:
            gesture.memory.close()
