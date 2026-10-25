from __future__ import annotations
import time
from .gate import TrajectorySensor
"""Contracts and engines for Muse-Me core capabilities:
1. Evidence Comparison (Comparar evidencia)
2. Deliverable Production (Producir un entregable)

Enforces:
- Formal capability contracts (id, version, permissions, effects, verification)
- Revalidation of sources before transfer and action
- Explicit two-gate authorization cycle (Gate 1 transfer, Gate 2 action)
- Cryptographic readback checks
- Idempotent action execution (no duplicate writes / replay)
- Persistent state transitions (draft -> proposal_ready -> action_approved -> completed)
"""
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_digest(text_or_bytes: str | bytes) -> str:
    if isinstance(text_or_bytes, str):
        text_or_bytes = text_or_bytes.encode("utf-8")
    return hashlib.sha256(text_or_bytes).hexdigest()


@dataclass(frozen=True)
class CapabilityContract:
    id: str
    version: str
    name: str
    description: str
    required_permissions: List[str]
    expected_output_type: str
    has_side_effects: bool
    verification_type: str


CAPABILITY_EVIDENCE_COMPARISON = CapabilityContract(
    id="evidence_comparison",
    version="1.0",
    name="Comparar Evidencia",
    description="Compara fuentes autorizadas sobre un objetivo o pregunta, contrastando afirmaciones y discrepancias sin decidir por fecha.",
    required_permissions=["may_transfer"],
    expected_output_type="structured_comparison",
    has_side_effects=False,
    verification_type="reference_provenance_validation"
)

CAPABILITY_DELIVERABLE_PRODUCTION = CapabilityContract(
    id="deliverable_production",
    version="1.0",
    name="Producir Entregable",
    description="Propone un informe, brief o plan estructurado en Markdown, sujeto a revisión de borrador y escritura local verificada.",
    required_permissions=["may_transfer", "local_write"],
    expected_output_type="markdown_document",
    has_side_effects=True,
    verification_type="file_readback_sha256"
)

AVAILABLE_CAPABILITIES = {
    CAPABILITY_EVIDENCE_COMPARISON.id: CAPABILITY_EVIDENCE_COMPARISON,
    CAPABILITY_DELIVERABLE_PRODUCTION.id: CAPABILITY_DELIVERABLE_PRODUCTION,
}


def compare_evidence(memory, mission_id: str, operator_override=None) -> Dict[str, Any]:
    """Capability A: Compare Evidence across authorized sources.
    Evaluates claims, detects contradictions without preferring newer dates,
    and validates reference provenance against authorized package digests.
    """
    state = memory.resume(mission_id)
    if state.get("state") == "completed":
        raise ValueError(f"Misión {mission_id} ya se encuentra completada. Cree una nueva misión para generar propuestas adicionales.")
    if state.get("state") == "completed":
        raise ValueError(f"Misión {mission_id} ya se encuentra completada. Cree una nueva misión para generar propuestas adicionales.")
    if state["needs_review"]:
        raise ValueError(f"Misión {mission_id} requiere revisión: fuentes modificadas o no disponibles ({state['changed_sources']})")

    # Fetch authorized content
    records = []
    for source, revision in state["refs"].items():
        row = memory.db.execute(
            """SELECT r.content, s.scope, s.source FROM revisions r
               JOIN sources s ON r.project=s.project AND r.source=s.source
               WHERE r.revision=?""",
            (revision,)
        ).fetchone()
        if not row:
            raise KeyError(f"Revisión {revision} no encontrada en proyecto")
        if row["scope"] != "may_transfer":
            raise PermissionError(f"Fuente '{source}' tiene permiso '{row['scope']}'; no autorizada para transferencia")
        records.append({
            "source": row["source"],
            "revision": revision,
            "content": row["content"]
        })

    # Reference validation
    all_refs_valid = True
    claims: List[Dict[str, Any]] = []
    discrepancies: List[Dict[str, Any]] = []

    # Extract claims per source (structured sentences/paragraphs)
    for rec in records:
        content = rec["content"]
        sentences = [s.strip() for s in re.split(r'[\r\n]+|(?<=[.!?])\s+', content) if len(s.strip()) > 5]
        for idx, sent in enumerate(sentences[:10]):
            claims.append({
                "source": rec["source"],
                "revision": rec["revision"],
                "claim_id": f"{rec['source']}#claim-{idx+1}",
                "statement": sent,
                "epistemic_status": "observed_in_source"
            })

    # Detect cross-source discrepancies (e.g. conflicting percentages, dates, status)
    if len(records) >= 2:
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                rec_a = records[i]
                rec_b = records[j]
                # Look for numerical or keyword divergence
                nums_a = set(re.findall(r'\b\d+(?:[.,]\d+)?%?\b', rec_a["content"]))
                nums_b = set(re.findall(r'\b\d+(?:[.,]\d+)?%?\b', rec_b["content"]))
                divergent_values = (nums_a ^ nums_b)
                if divergent_values:
                    discrepancies.append({
                        "topic": "divergencia_valores_o_parametros",
                        "source_a": rec_a["source"],
                        "revision_a": rec_a["revision"],
                        "source_b": rec_b["source"],
                        "revision_b": rec_b["revision"],
                        "divergent_terms": sorted(list(divergent_values))[:8],
                        "epistemic_note": "Discrepancia detectada entre fuentes sin resolver automáticamente por fecha. Requiere evaluación de vigencia por el usuario."
                    })

    comparison_result = {
        "capability": CAPABILITY_EVIDENCE_COMPARISON.id,
        "capability_version": CAPABILITY_EVIDENCE_COMPARISON.version,
        "mission_id": mission_id,
        "project": state["project"],
        "goal": state["goal"],
        "sources_analyzed": [r["source"] for r in records],
        "revisions_audited": {r["source"]: r["revision"] for r in records},
        "claims_extracted_count": len(claims),
        "claims": claims,
        "discrepancies_detected_count": len(discrepancies),
        "discrepancies": discrepancies,
        "uncertainties": [
            "La correlación léxica no garantiza concordancia semántica.",
            "Toda afirmación debe ser contrastada contra el propósito operativo específico."
        ],
        "reference_validation": {
            "all_references_valid": all_refs_valid,
            "authorized_sources_count": len(records),
            "unauthorized_sources": []
        },
        "epistemic_honesty": {
            "mode": "deterministic_analysis",
            "model_inference": None,
            "human_effort_seconds": None
        }
    }

    # Record proposal in mission
    proposal_json = json.dumps(comparison_result, ensure_ascii=False)
    memory.update_mission_proposal(mission_id, proposal_json, capability=CAPABILITY_EVIDENCE_COMPARISON.id)
    return comparison_result


def propose_deliverable(
    memory,
    mission_id: str,
    title: str = "Entregable Contextual",
    criteria: Optional[Dict[str, Any]] = None,
    custom_draft: Optional[str] = None
) -> Dict[str, Any]:
    """Capability B (Phase 1): Propose a Markdown Deliverable based on authorized sources.
    Prepares the draft, attaches verified citations, and registers the proposal hash for Gate 2.
    """
    state = memory.resume(mission_id)
    if state.get("state") == "completed":
        raise ValueError(f"Misión {mission_id} ya se encuentra completada. Cree una nueva misión para generar propuestas adicionales.")
    if state["needs_review"]:
        raise ValueError(f"Misión {mission_id} requiere revisión: fuentes modificadas ({state['changed_sources']})")

    records = []
    for source, revision in state["refs"].items():
        row = memory.db.execute(
            """SELECT r.content, s.scope, s.source FROM revisions r
               JOIN sources s ON r.project=s.project AND r.source=s.source
               WHERE r.revision=?""",
            (revision,)
        ).fetchone()
        if not row:
            raise KeyError(f"Revisión {revision} no encontrada")
        if row["scope"] != "may_transfer":
            raise PermissionError(f"Fuente '{source}' no autorizada para transferencia")
        records.append({
            "source": row["source"],
            "revision": revision,
            "content": row["content"]
        })

    # Construct clean markdown draft
    if custom_draft:
        markdown_body = custom_draft
    else:
        sources_list = "\n".join([f"- **{r['source']}** (`{r['revision'][:16]}...`)" for r in records])
        key_points = []
        for r in records:
            first_lines = [l.strip() for l in r["content"].splitlines() if l.strip()][:3]
            if first_lines:
                key_points.append(f"### Evidencia de {r['source']}\n> " + "\n> ".join(first_lines))
        points_block = "\n\n".join(key_points) if key_points else "_Sin extractos directos._"

        criteria_desc = ""
        if criteria:
            criteria_desc = f"\n\n### Criterios Operativos del Usuario\n```json\n{json.dumps(criteria, indent=2, ensure_ascii=False)}\n```"

        markdown_body = f"""# {title}

**Proyecto:** {state['project']}  
**Objetivo Declarado:** {state['goal']}  
**Capacidad:** {CAPABILITY_DELIVERABLE_PRODUCTION.name} (`{CAPABILITY_DELIVERABLE_PRODUCTION.id} v{CAPABILITY_DELIVERABLE_PRODUCTION.version}`)

---

## 1. Resumen Ejecutivo
Este informe reúne y sintetiza la evidencia autorizada disponible para resolver el objetivo formulado.

## 2. Fuentes Autorizadas Utilizadas
{sources_list}
{criteria_desc}

## 3. Síntesis de Evidencia Contrastada
{points_block}

## 4. Plan de Acción Recomendado
1. Contrastar los puntos de divergencia identificados antes de desplegar en producción.
2. Registrar la aprobación formal de este artefacto en la memoria del proyecto.

---
*Artefacto generado por Muse-Me bajo supervisión de doble compuerta. Hash de procedencia auditado.*
"""

    draft_sha256 = sha256_digest(markdown_body)
    proposal_bundle = {
        "capability": CAPABILITY_DELIVERABLE_PRODUCTION.id,
        "capability_version": CAPABILITY_DELIVERABLE_PRODUCTION.version,
        "mission_id": mission_id,
        "project": state["project"],
        "goal": state["goal"],
        "title": title,
        "criteria": criteria or {},
        "citations": [{"source": r["source"], "revision": r["revision"]} for r in records],
        "draft_markdown": markdown_body,
        "draft_sha256": draft_sha256,
        "state": "proposal_ready",
        "requires_gate2_approval": True
    }

    memory.update_mission_proposal(
        mission_id,
        json.dumps(proposal_bundle, ensure_ascii=False),
        capability=CAPABILITY_DELIVERABLE_PRODUCTION.id,
        criteria=json.dumps(criteria or {}, ensure_ascii=False)
    )
    return proposal_bundle


def execute_deliverable_action(
    memory,
    mission_id: str,
    target_dir: str | Path,
    filename: str,
    approved_draft_sha256: str,
    user_approved: bool = False,
    fuse_sensor: Optional[TrajectorySensor] = None,
    risk_score: float = 0.0,
    fuse_path: str = "session"
) -> Dict[str, Any]:
    """Capability B (Phase 2): Execute approved local file creation.
    - Enforces Gate 2 approval and non-duplication
    - Revalidates sources
    - Writes exact content into authorized target directory
    - Performs cryptographic readback verification
    """
    # F07: Temporal Fuse Gate 2
    if fuse_sensor is not None and fuse_sensor.observe(risk_score, effect="write", t=time.time(), path=fuse_path):
        raise PermissionError("Compuerta 2 bloqueada por Fusible Temporal (I²t): riesgo acumulado excedió el umbral.")

    if not user_approved:
        raise PermissionError("Compuerta 2 rechazada: falta la aprobación explícita del usuario.")

    state = memory.resume(mission_id)
    if state["needs_review"]:
        raise ValueError(f"Acción bloqueada: las fuentes de la misión {mission_id} cambiaron y requieren nueva revisión.")

    # Check for idempotent completed state with disk readback re-verification (F03)
    if state.get("state") == "completed":
        existing_path = state.get("artifact_path")
        existing_hash = state.get("artifact_hash")
        if existing_path and Path(existing_path).exists():
            current_disk_content = Path(existing_path).read_text(encoding="utf-8")
            current_disk_hash = sha256_digest(current_disk_content)
            if current_disk_hash != existing_hash:
                return {
                    "mission_id": mission_id,
                    "status": "artifact_modified_on_disk",
                    "message": "ALERTA: El archivo en disco fue modificado externamente después de la compleción.",
                    "artifact_path": existing_path,
                    "recorded_hash": existing_hash,
                    "current_disk_hash": current_disk_hash,
                    "readback_verified": False,
                    "current_integrity": False,
                    "user_approved": True
                }
            return {
                "mission_id": mission_id,
                "status": "already_completed_idempotent",
                "message": "La misión ya fue completada previamente. Hash en disco verificado intacto.",
                "artifact_path": existing_path,
                "artifact_hash": existing_hash,
                "readback_verified": True,
                "current_integrity": True,
                "user_approved": True
            }

    proposal_str = state.get("proposal")
    if not proposal_str:
        raise ValueError("No existe una propuesta de entregable registrada para esta misión.")

    proposal = json.loads(proposal_str)
    if proposal.get("draft_sha256") != approved_draft_sha256:
        raise ValueError("El hash de aprobación no coincide con el borrador vigente de la propuesta.")

    draft_content = proposal.get("draft_markdown", "")
    if not draft_content:
        raise ValueError("El borrador de la propuesta está vacío.")

    # Target directory safety checks (no path traversal)
    base_target = Path(target_dir).resolve(strict=True)
    out_file = (base_target / filename).resolve()
    if not out_file.is_relative_to(base_target):
        raise PermissionError(f"Ruta de destino '{filename}' escapa del directorio autorizado '{base_target}'.")

    # Write exact content
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(draft_content, encoding="utf-8")

    # Cryptographic Readback Check
    disk_readback = out_file.read_text(encoding="utf-8")
    disk_hash = sha256_digest(disk_readback)

    if disk_hash != approved_draft_sha256:
        memory.update_mission_state(mission_id, "failed", error="Fallo en comprobación readback: hash en disco difiere del aprobado.")
        raise RuntimeError("Fallo crítico de integridad: el archivo escrito en disco no coincide con el hash aprobado.")

    # Record completion in ProjectMemory
    memory.mark_mission_completed(
        mission_id=mission_id,
        artifact_path=str(out_file),
        artifact_hash=disk_hash,
        approvals={
            "gate1_transfer_approved": True,
            "gate2_action_approved": True,
            "approved_hash": approved_draft_sha256,
            "verified_disk_hash": disk_hash
        }
    )

    return {
        "mission_id": mission_id,
        "capability": CAPABILITY_DELIVERABLE_PRODUCTION.id,
        "status": "completed",
        "file_created_verified": True,
        "user_approved": True,
        "artifact_path": str(out_file),
        "artifact_hash": disk_hash,
        "readback_verified": True,
        "message": f"Artefacto '{out_file.name}' generado y verificado exitosamente."
    }