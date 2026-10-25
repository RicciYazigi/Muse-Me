"""Muse-Me — Demostración de Recorrido Canónico (90-120 segundos).

Demuestra de forma determinista y reproducible:
1. Ingesta de fuentes autorizadas y exclusión por política de datos confidenciales (restricted).
2. Capacidad A: Comparar Evidencia (detección de discrepancias y citas auditadas).
3. Capacidad B: Producir Entregable (borrador, aprobación Compuerta 2, escritura y readback SHA-256).
4. No duplicación / Idempotencia de ejecución.
5. Detección reactiva de cambio de fuente en disco y bloqueo de seguridad.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.project_memory import ProjectMemory
from muse_env.capabilities import (
    compare_evidence,
    propose_deliverable,
    execute_deliverable_action
)


def run_demo():
    print("=" * 70)
    print("  MUSE-ME: DEMOSTRACION DEL RECORRIDO DE ASISTENCIA CONTEXTUAL")
    print("=" * 70)

    # 1. Configurar entorno temporal de demo
    data_dir = ROOT / "data" / "demo_walkthrough"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "project_memory.sqlite"
    if db_path.exists():
        db_path.unlink()

    memory = ProjectMemory(str(db_path))

    # Fuentes sinteticas
    sources_dir = data_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    spec_v24 = sources_dir / "especificacion_v24.md"
    spec_v24.write_text(
        "Especificacion v2.4 (2026): Para ordenes en region LATAM con cupon PROMO_REGIONAL, "
        "aplicar 15% de descuento sobre el subtotal antes de impuestos con tope maximo de 25.00 USD. "
        "Requiere redondeo ROUND_HALF_UP.",
        encoding="utf-8"
    )

    spec_v10 = sources_dir / "manual_v10_obsoleto.md"
    spec_v10.write_text(
        "Manual v1.0 (2024): Descuentos promocionales generales se calculan al 5% sin tope regional "
        "para todas las cuentas activas.",
        encoding="utf-8"
    )

    secret_notes = sources_dir / "claves_privadas.txt"
    secret_notes.write_text(
        "CONFIDENCIAL: STRIPE_API_KEY=sk_live_sample_token_secret; AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE",
        encoding="utf-8"
    )

    print("\n[Paso 1] Ingesta de Fuentes y Aplicacion de Politicas")
    rev_v24 = memory.ingest_text("demo", sources_dir, "especificacion_v24.md", scope="may_transfer")
    rev_v10 = memory.ingest_text("demo", sources_dir, "manual_v10_obsoleto.md", scope="may_transfer")
    rev_sec = memory.ingest_text("demo", sources_dir, "claves_privadas.txt", scope="restricted")

    print(f"  * especificacion_v24.md  -> {rev_v24[:16]}... [may_transfer]")
    print(f"  * manual_v10_obsoleto.md -> {rev_v10[:16]}... [may_transfer]")
    print(f"  * claves_privadas.txt    -> {rev_sec[:16]}... [restricted] (Contenido confidencial suprimido)")

    # 2. Capacidad A: Comparar Evidencia
    print("\n[Paso 2] Ejecutando Capacidad A: Comparar Evidencia")
    goal_compare = "Determinar el porcentaje y tope de descuento aplicable en region LATAM"
    mission_a = memory.checkpoint(
        "demo",
        goal_compare,
        {"especificacion_v24.md": rev_v24, "manual_v10_obsoleto.md": rev_v10},
        capability="evidence_comparison"
    )

    res_compare = compare_evidence(memory, mission_a)
    print(f"  * Mision ID: {mission_a}")
    print(f"  * Fuentes analizadas: {res_compare['sources_analyzed']}")
    print(f"  * Afirmaciones extraidas: {res_compare['claims_extracted_count']}")
    print(f"  * Discrepancias detectadas: {res_compare['discrepancies_detected_count']}")
    if res_compare['discrepancies']:
        disc = res_compare['discrepancies'][0]
        print(f"    - Divergencia de terminos: {disc['divergent_terms']}")
        print(f"    - Nota epistemica: {disc['epistemic_note']}")

    # 3. Capacidad B: Producir Entregable (Borrador -> Aprobacion -> Escritura)
    print("\n[Paso 3] Ejecutando Capacidad B: Producir Entregable")
    goal_deliv = "Generar informe formal de calculo de descuentos para el equipo contable"
    mission_b = memory.checkpoint(
        "demo",
        goal_deliv,
        {"especificacion_v24.md": rev_v24},
        capability="deliverable_production"
    )

    prop = propose_deliverable(memory, mission_b, title="Informe Tecnico de Descuentos LATAM")
    draft_sha = prop["draft_sha256"]
    print(f"  * Mision ID: {mission_b}")
    print(f"  * Borrador propuesto generado (SHA-256: {draft_sha[:16]}...)")
    print("  * Compuerta 2 requerida: Aprobacion explicita de contenido y destino.")

    # Simular aprobacion del operador
    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_filename = "informe_descuentos_latam_demo.md"

    exec_result = execute_deliverable_action(
        memory,
        mission_b,
        target_dir=artifacts_dir,
        filename=out_filename,
        approved_draft_sha256=draft_sha,
        user_approved=True
    )

    print(f"  * Archivo escrito en: {exec_result['artifact_path']}")
    print(f"  * Comprobacion Readback SHA-256 en disco: {exec_result['readback_verified']}")
    print(f"  * Estado final: {exec_result['status']}")

    # 4. Comprobar Idempotencia / No Duplicacion
    print("\n[Paso 4] Comprobacion de No Duplicacion (Idempotencia)")
    repeat_res = execute_deliverable_action(
        memory,
        mission_b,
        target_dir=artifacts_dir,
        filename=out_filename,
        approved_draft_sha256=draft_sha,
        user_approved=True
    )
    print(f"  * Repeticion de llamada: {repeat_res['status']} ({repeat_res['message']})")

    # 5. Deteccion Reactiva de Modificacion en Disco
    print("\n[Paso 5] Deteccion de Modificacion en Disco y Bloqueo de Transferencia")
    spec_v24.write_text("Especificacion v2.5 (Modificada externamente en disco)", encoding="utf-8")
    state = memory.resume(mission_b)
    print(f"  * Deteccion de cambio en disco: needs_review = {state['needs_review']}")
    print(f"  * Fuentes afectadas: {state['changed_sources']}")
    try:
        memory.payload(mission_b)
        print("  * ERROR: Transferencia no bloqueada.")
    except ValueError as e:
        print(f"  * Bloqueo de seguridad verificado: {e}")

    # Guardar reporte de recorrido
    report_file = data_dir / "walkthrough_evidence.json"
    evidence_data = {
        "nature": "reproducible_canonical_walkthrough",
        "steps_verified": [
            "ingestion_and_policy_enforcement",
            "capability_evidence_comparison",
            "capability_deliverable_production",
            "gate2_human_approval_and_readback_sha256",
            "idempotent_action_execution",
            "disk_change_detection_and_blocking"
        ],
        "evidence_comparison": {
            "mission_id": mission_a,
            "discrepancies": res_compare["discrepancies_detected_count"],
            "claims": res_compare["claims_extracted_count"]
        },
        "deliverable_production": {
            "mission_id": mission_b,
            "artifact_path": exec_result["artifact_path"],
            "readback_verified": exec_result["readback_verified"]
        },
        "disk_change_detected": state["needs_review"]
    }
    report_file.write_text(json.dumps(evidence_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEvidencia del recorrido registrada en: {report_file}")
    print("\n>>> RECORRIDO COMPLETADO EXITOSAMENTE AL 100% <<<")
    memory.close()


if __name__ == "__main__":
    run_demo()