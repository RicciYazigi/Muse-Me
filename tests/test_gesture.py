import tempfile
from pathlib import Path
import pytest

from muse_env.gesture import MuseDesktopGesture
from muse_env.project_memory import ProjectMemory


def test_muse_desktop_gesture_unauthorized_and_authorized():
    """F05: Verify 'Responder con Muse' desktop gesture behavior."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "gesture_mem.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            doc_dir = Path(td) / "docs"
            doc_dir.mkdir()
            f = doc_dir / "politica.md"
            f.write_text("Especificación de precios aprobada.", encoding="utf-8")
            mem.ingest_text("test-proj", str(doc_dir), "politica.md", scope="may_transfer")
        finally:
            mem.close()

        gesture = MuseDesktopGesture(memory_path=str(db_p))
        try:
            # 1. Trigger over unauthorized window HWND 0x1234
            res_unauth = gesture.trigger_gesture(target_hwnd=0x1234, project="test-proj")
            assert res_unauth["status"] == "blocked"
            assert res_unauth["gesture_action"] == "authorization_required"
            assert "seguridad" in res_unauth["message"].lower()

            # 2. Authorize window HWND 0x1234 in the observer allowlist
            gesture.observer.authorize_surface("TestApp", hwnd=0x1234, permission_scope="may_transfer")

            # 3. Trigger again over authorized window
            res_auth = gesture.trigger_gesture(target_hwnd=0x1234, project="test-proj")
            assert res_auth["status"] == "proposal_ready"
            assert res_auth["gesture_action"] == "reply_with_muse"
            assert res_auth["requires_gate2_human_approval"] is True
            assert "mission_id" in res_auth
            assert len(res_auth["draft_sha256"]) == 64
        finally:
            gesture.memory.close()
