import tempfile
from pathlib import Path
import pytest

from muse_env.project_memory import ProjectMemory
from muse_env.mcp_server import MuseMeMCPServer


def test_context_compiler_v2_excludes_obsolete_spec():
    """Door N3: Outdated spec v1.0 must NOT enter active context when superseded by authoritative v2.4."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "pilot_memory.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            doc_dir = Path(td) / "sources"
            doc_dir.mkdir()
            
            # v1.0 outdated spec (similar to utility pilot fixture)
            v10 = doc_dir / "window_spec_v10_outdated.txt"
            v10.write_text(
                "=== ARCHIVO HISTÓRICO DE DESCUENTOS (OBSOLETO / DEPRECATED) ===\n"
                "Manual Promocional v1.0 (OBSOLETO). Regla antigua: descuento del 5% parejo a todas las regiones.",
                encoding="utf-8"
            )
            
            # v2.4 authoritative active spec
            v24 = doc_dir / "window_spec_v24.txt"
            v24.write_text(
                "=== ESPECIFICACIÓN VIGENTE DE DESCUENTOS v2.4 ===\n"
                "Política aprobada 2026: descuento escalonado según nivel de facturación (hasta 20%).",
                encoding="utf-8"
            )
            
            mem.ingest_text("pilot-proj", str(doc_dir), "window_spec_v10_outdated.txt", scope="may_transfer")
            mem.ingest_text("pilot-proj", str(doc_dir), "window_spec_v24.txt", scope="may_transfer")
            
            # Standard search
            active_results = mem.search("pilot-proj", "descuentos promocionales")
            selected_sources = [r["source"] for r in active_results]
            
            # DOOR N3 VERIFICATION:
            assert "window_spec_v24.txt" in selected_sources, "La especificación vigente debe ser seleccionada"
            assert "window_spec_v10_outdated.txt" not in selected_sources, "La especificación obsoleta NO debe entrar en el contexto activo"
            
            # Detailed exclusion explanation verification
            exclusions_report = mem.search_with_exclusions("pilot-proj", "descuentos promocionales")
            excluded_names = [e["source"] for e in exclusions_report["excluded"]]
            assert "window_spec_v10_outdated.txt" in excluded_names
            
            obsolete_exclusion = next(e for e in exclusions_report["excluded"] if e["source"] == "window_spec_v10_outdated.txt")
            assert "vigencia" in obsolete_exclusion["reason"].lower() or "obsoleto" in obsolete_exclusion["reason"].lower()
        finally:
            mem.close()