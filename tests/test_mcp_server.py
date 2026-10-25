import json
import tempfile
from pathlib import Path
import pytest

from muse_env.mcp_server import MuseMeMCPServer
from muse_env.project_memory import ProjectMemory


def test_mcp_server_tools_list_and_context_package():
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "test_pm.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            # Seed project
            src_dir = Path(td) / "docs"
            src_dir.mkdir()
            f1 = src_dir / "politica_vigente.md"
            f1.write_text("Descuento del 15% aprobado para clientes enterprise.", encoding="utf-8")
            f2 = src_dir / "claves_secretas.txt"
            f2.write_text("API_SECRET_KEY=12345_CONFIDENCIAL", encoding="utf-8")
            
            mem.ingest_text("demo-proj", str(src_dir), "politica_vigente.md", scope="may_transfer")
            mem.ingest_text("demo-proj", str(src_dir), "claves_secretas.txt", scope="restricted")
        finally:
            mem.close()

        server = MuseMeMCPServer(db_path=str(db_p))
        try:
            # Test Tool 1: get_context_package
            pkg = server.handle_call_tool("get_context_package", {
                "project": "demo-proj",
                "goal": "descuento clientes enterprise",
                "token_budget": 500
            })
            assert pkg["status"] == "authorized_package_ready"
            assert pkg["evidence_count"] >= 1
            assert "politica_vigente.md" in [ev["source"] for ev in pkg["authorized_evidence"]]
            
            # Verify restricted source exclusion
            assert any(ex["source"] == "claves_secretas.txt" for ex in pkg["excluded_sources"])
            mission_id = pkg["mission_id"]

            # Test Tool 2: propose_insertion
            prop = server.handle_call_tool("propose_insertion", {
                "mission_id": mission_id,
                "title": "Propuesta de descuento",
                "custom_draft": "# Resumen Aprobado\nDescuento fijado al 15%."
            })
            assert prop["status"] == "proposal_registered"
            assert prop["requires_gate2_human_approval"] is True
            assert len(prop["approved_draft_sha256"]) == 64

            # Test Tool 3: verify_state
            st = server.handle_call_tool("verify_state", {
                "mission_id": mission_id,
                "project": "demo-proj"
            })
            assert st["status"] == "ok"
            assert st["mission_status"]["state"] == "proposal_ready"
            assert len(st["project_summary"]["sources"]) == 2
        finally:
            server.memory.close()