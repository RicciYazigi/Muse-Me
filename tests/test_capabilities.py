import json
import pytest
from pathlib import Path
from muse_env.project_memory import ProjectMemory
from muse_env.capabilities import (
    compare_evidence,
    propose_deliverable,
    execute_deliverable_action,
    CAPABILITY_EVIDENCE_COMPARISON,
    CAPABILITY_DELIVERABLE_PRODUCTION
)


def test_capability_evidence_comparison(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    memory = ProjectMemory(db_path)
    
    # Ingest two sources with divergent parameters
    rev_a = memory.put("proj1", "specs/v1.md", "Descuento regional LATAM fijado en 5% para clientes regulares.", "may_transfer")
    rev_b = memory.put("proj1", "specs/v2.md", "Descuento regional LATAM actualizado a 15% con tope de 25 USD.", "may_transfer")
    
    mission_id = memory.checkpoint("proj1", "Comparar políticas de descuento LATAM", {"specs/v1.md": rev_a, "specs/v2.md": rev_b})
    
    comparison = compare_evidence(memory, mission_id)
    
    assert comparison["capability"] == CAPABILITY_EVIDENCE_COMPARISON.id
    assert comparison["mission_id"] == mission_id
    assert len(comparison["sources_analyzed"]) == 2
    assert comparison["claims_extracted_count"] >= 2
    # Verify discrepancy was detected without picking by date
    assert comparison["discrepancies_detected_count"] >= 1
    disc = comparison["discrepancies"][0]
    assert "LATAM" in disc["source_a"] or "specs" in disc["source_a"]
    assert "Discrepancia detectada entre fuentes sin resolver automáticamente por fecha" in disc["epistemic_note"]
    assert comparison["reference_validation"]["all_references_valid"] is True

    # Test resume reflects proposal
    state = memory.resume(mission_id)
    assert state["state"] == "proposal_ready"
    assert state["capability"] == CAPABILITY_EVIDENCE_COMPARISON.id
    memory.close()


def test_capability_deliverable_production_and_verified_execution(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    memory = ProjectMemory(db_path)
    
    rev = memory.put("proj1", "brief.txt", "Objetivo del sprint: Lanzamiento v1.0 el viernes con pagos Stripe.", "may_transfer")
    mission_id = memory.checkpoint("proj1", "Generar plan de lanzamiento", {"brief.txt": rev})
    
    # Propose deliverable
    proposal = propose_deliverable(
        memory,
        mission_id,
        title="Plan de Lanzamiento Q4",
        criteria={"formato": "Markdown", "auditor": "Seguridad"}
    )
    
    assert proposal["capability"] == CAPABILITY_DELIVERABLE_PRODUCTION.id
    assert proposal["requires_gate2_approval"] is True
    draft_sha = proposal["draft_sha256"]
    assert len(draft_sha) == 64
    
    # Execution rejects if Gate 2 is not approved
    target_dir = tmp_path / "artifacts"
    target_dir.mkdir()
    with pytest.raises(PermissionError, match="Compuerta 2 rechazada"):
        execute_deliverable_action(memory, mission_id, target_dir, "plan.md", draft_sha, user_approved=False)
        
    # Execution rejects if approved hash does not match proposal
    with pytest.raises(ValueError, match="hash de aprobación no coincide"):
        execute_deliverable_action(memory, mission_id, target_dir, "plan.md", "forged_hash_12345", user_approved=True)

    # Execution rejects path traversal escaping target_dir
    with pytest.raises(PermissionError, match="escapa del directorio autorizado"):
        execute_deliverable_action(memory, mission_id, target_dir, "../escape.md", draft_sha, user_approved=True)

    # Legitimate execution writes file and passes readback check
    result = execute_deliverable_action(memory, mission_id, target_dir, "plan.md", draft_sha, user_approved=True)
    assert result["status"] == "completed"
    assert result["file_created_verified"] is True
    assert result["user_approved"] is True
    assert result["readback_verified"] is True
    
    out_file = Path(result["artifact_path"])
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == proposal["draft_markdown"]
    
    # Idempotency / Non-duplication test: repeating call does NOT overwrite or create duplicate
    repeat_result = execute_deliverable_action(memory, mission_id, target_dir, "plan.md", draft_sha, user_approved=True)
    assert repeat_result["status"] == "already_completed_idempotent"
    assert repeat_result["readback_verified"] is True

    memory.close()


def test_file_modification_on_disk_blocks_transfer_and_action(tmp_path):
    doc_root = tmp_path / "docs_root"
    doc_root.mkdir()
    doc_file = doc_root / "spec.txt"
    doc_file.write_text("Versión 1.0 de la especificación", encoding="utf-8")
    
    db_path = tmp_path / "memory.sqlite"
    memory = ProjectMemory(db_path)
    
    rev = memory.ingest_text("p1", doc_root, "spec.txt", scope="may_transfer")
    mission_id = memory.checkpoint("p1", "Construir entregable", {"spec.txt": rev})
    
    assert not memory.resume(mission_id)["needs_review"]
    
    # Modify file on disk
    doc_file.write_text("Versión 2.0 modificada en disco externamente", encoding="utf-8")
    
    # resume detects disk change
    resume_state = memory.resume(mission_id)
    assert resume_state["needs_review"] is True
    assert "spec.txt" in resume_state["changed_sources"]
    
    # Payload transfer is blocked
    with pytest.raises(ValueError, match="fuentes cambiaron"):
        memory.payload(mission_id)
        
    # Deliverable proposal is blocked
    with pytest.raises(ValueError, match="requiere revisión"):
        propose_deliverable(memory, mission_id)
        
    memory.close()
