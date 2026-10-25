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


def test_mcp_server_blocks_local_only_leak():
    """A1 RED TEST: An external MCP host must NEVER receive local-only sources."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "test_pm_leak.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            src_dir = Path(td) / "docs"
            src_dir.mkdir()
            f1 = src_dir / "internal_secrets.md"
            f1.write_text("Informacion estrictamente confidencial de uso local.", encoding="utf-8")
            mem.ingest_text("secret-proj", str(src_dir), "internal_secrets.md", scope="local-only")
        finally:
            mem.close()

        server = MuseMeMCPServer(db_path=str(db_p))
        try:
            # Test default invocation:
            pkg = server.handle_call_tool("get_context_package", {
                "project": "secret-proj",
                "goal": "informacion confidencial local",
                "token_budget": 500
            })
            sources_delivered = [ev["source"] for ev in pkg.get("authorized_evidence", [])]
            assert "internal_secrets.md" not in sources_delivered, "CRITICAL LEAK: local-only source delivered to MCP host!"
            assert any(ex["source"] == "internal_secrets.md" for ex in pkg.get("excluded_sources", []))

            # B1 Invariant: Caller attempting external=False explicitly MUST NOT bypass the boundary!
            pkg_hostile = server.handle_call_tool("get_context_package", {
                "project": "secret-proj",
                "goal": "informacion confidencial local",
                "token_budget": 500,
                "external": False
            })
            hostile_delivered = [ev["source"] for ev in pkg_hostile.get("authorized_evidence", [])]
            assert "internal_secrets.md" not in hostile_delivered, "CRITICAL LEAK B1: caller bypassed boundary with external=False!"
        finally:
            server.memory.close()
