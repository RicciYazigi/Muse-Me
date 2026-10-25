"""Smoke Test Fixture del Arnés Experimental.

AVISO METODOLÓGICO:
Este script utiliza fixtures deterministas pregrabados EXCLUSIVAMENTE para
validar la mecánica de tuberías, sandbox de pruebas, empaquetado y evaluador.
NO constituye una medición empírica de utilidad ni de esfuerzo humano:
- Las respuestas son fixtures estáticos.
- Los tiempos reales y acciones no observadas se reportan estrictamente como null.
- Para mediciones con operador independiente y controles reales, use run_assisted_experiment.py.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
MUSE_SRC_DIR = EXPERIMENTS_DIR.parent.parent / "src"
sys.path.insert(0, str(EXPERIMENTS_DIR / "evaluation"))
sys.path.insert(0, str(MUSE_SRC_DIR))

import evaluator
from muse_env.store import digest, EventStore
from muse_env.events import ObservationEvent
from muse_env.context_builder import ContextBuilder
from muse_env.episodes import build_episodes


def load_task_sources() -> dict[str, str]:
    sources_dir = EXPERIMENTS_DIR / "task_definition" / "sources"
    return {
        "target_editor": (sources_dir / "window_target_editor.txt").read_text(encoding="utf-8"),
        "spec_v24": (sources_dir / "window_spec_v24.txt").read_text(encoding="utf-8"),
        "spec_v10_outdated": (sources_dir / "window_spec_v10_outdated.txt").read_text(encoding="utf-8"),
        "private_notes_restricted": (sources_dir / "window_private_notes.txt").read_text(encoding="utf-8"),
    }


def fixture_response_condition_a() -> dict[str, Any]:
    """Fixture pregrabado para Condición A: intenta corregir tipos sin conocer la regla v2.4."""
    code = (
        "def apply_regional_discount(order: dict, coupon_code: str) -> dict:\n"
        "    subtotal = order.get('subtotal', Decimal('0.00'))\n"
        "    region = order.get('region', 'GLOBAL')\n"
        "    if coupon_code == 'PROMO_REGIONAL':\n"
        "        discount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
        "        order['discount_amount'] = discount\n"
        "    else:\n"
        "        order['discount_amount'] = Decimal('0.00')\n"
        "    order['final_total'] = calculate_order_total(subtotal, order.get('tax_rate', Decimal('0.16')), order['discount_amount'])\n"
        "    return order\n"
    )
    return {
        "nature": "fixture_pregrabado_simulador",
        "code": code,
        "citations": [],
        "explanation": "Fixture A: corrección de tipo float a Decimal sin acceso a especificación v2.4."
    }


def fixture_response_condition_b() -> dict[str, Any]:
    """Fixture pregrabado para Condición B: aplica la regla de negocio v2.4."""
    code = (
        "def apply_regional_discount(order: dict, coupon_code: str) -> dict:\n"
        "    subtotal = order.get('subtotal', Decimal('0.00'))\n"
        "    region = order.get('region', 'GLOBAL')\n"
        "    if coupon_code == 'PROMO_REGIONAL' and region == 'LATAM':\n"
        "        discount = (subtotal * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
        "        if subtotal > Decimal('100.00') and discount > Decimal('25.00'):\n"
        "            discount = Decimal('25.00')\n"
        "        order['discount_amount'] = discount\n"
        "    else:\n"
        "        order['discount_amount'] = Decimal('0.00')\n"
        "    order['final_total'] = calculate_order_total(subtotal, order.get('tax_rate', Decimal('0.16')), order['discount_amount'])\n"
        "    return order\n"
    )
    return {
        "nature": "fixture_pregrabado_simulador",
        "code": code,
        "citations": ["Docs-Tecnicos-v24"],
        "explanation": "Fixture B: regla v2.4 (15% Decimal para LATAM, cap 25.00 USD) citando Docs-Tecnicos-v24."
    }


def run_smoke_test(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = load_task_sources()

    # 1. Condición A
    resp_a = fixture_response_condition_a()
    eval_corr_a = evaluator.evaluate_code_correctness(resp_a["code"])
    eval_leak_a = evaluator.evaluate_leak(resp_a["code"])
    eval_cite_a = evaluator.evaluate_citations_and_claims(resp_a["explanation"], resp_a["citations"], allowed_sources=[])

    res_a = {
        "condition": "A_ventana_sola",
        "modo_ejecucion": "smoke_test_fixture (pruebas de tubería)",
        "context_sources_used": [],
        "context_chars_count": 0,
        "action_count": None,  # null porque no fue medido con humano real
        "human_time_seconds": None,  # null
        "model_latency_seconds": None,  # null
        "total_elapsed_seconds": None,  # null
        "eval_correctness": eval_corr_a["tests_passed"],
        "eval_leak_detected": eval_leak_a["leak_detected"],
        "coincidencias_lexicas": eval_cite_a["coincidencias_lexicas"],
        "verificacion_citas": eval_cite_a["verificacion_citas"],
        "code_delivered": resp_a["code"],
        "citations_delivered": resp_a["citations"],
        "test_suite_output": eval_corr_a.get("test_output", ""),
    }

    # 2. Condición B (Con ContextBuilder)
    db_file = out_dir / "temp_events.sqlite"
    if db_file.exists():
        db_file.unlink()
    store = EventStore(str(db_file))
    t_base = 1000.0
    store.add(ObservationEvent(kind="content_observed", application="Docs-Tecnicos-v24", content=sources["spec_v24"], permission_scope="may_transfer", source_type="windows_read_only", ts=t_base - 10.0))
    store.add(ObservationEvent(kind="content_observed", application="Docs-Obsoletos-v10", content=sources["spec_v10_outdated"], permission_scope="may_transfer", source_type="windows_read_only", ts=t_base - 20.0))
    store.add(ObservationEvent(kind="content_observed", application="Notas-Privadas-Infra", content=sources["private_notes_restricted"], permission_scope="restricted", source_type="windows_read_only", ts=t_base - 5.0))
    store.add(ObservationEvent(kind="content_observed", application="Editor-Python", content=sources["target_editor"], permission_scope="may_transfer", source_type="windows_read_only", ts=t_base))

    episodes = build_episodes(store.all())
    builder = ContextBuilder(max_additional=4, max_chars=2500)
    package = builder.build(action="reply_with_muse", target_application="Editor-Python", current_content=sources["target_editor"], episodes=episodes, target_is_external=True)
    allowed_sources_b = [c["app"] for c in package["additional_context"]]

    resp_b = fixture_response_condition_b()
    eval_corr_b = evaluator.evaluate_code_correctness(resp_b["code"])
    eval_leak_b = evaluator.evaluate_leak(resp_b["code"] + sources["spec_v24"])
    eval_cite_b = evaluator.evaluate_citations_and_claims(resp_b["explanation"], resp_b["citations"], allowed_sources=allowed_sources_b)

    res_b = {
        "condition": "B_seleccion_automatica",
        "modo_ejecucion": "smoke_test_fixture (pruebas de tubería)",
        "context_sources_used": allowed_sources_b,
        "excluded_sources": [e["app"] for e in package["excluded_context"]],
        "context_chars_count": sum(len(c["content"]) for c in package["additional_context"]),
        "action_count": None,  # null
        "human_time_seconds": None,  # null
        "model_latency_seconds": None,  # null
        "total_elapsed_seconds": None,  # null
        "eval_correctness": eval_corr_b["tests_passed"],
        "eval_leak_detected": eval_leak_b["leak_detected"],
        "coincidencias_lexicas": eval_cite_b["coincidencias_lexicas"],
        "verificacion_citas": eval_cite_b["verificacion_citas"],
        "code_delivered": resp_b["code"],
        "citations_delivered": resp_b["citations"],
        "test_suite_output": eval_corr_b.get("test_output", ""),
    }

    # 3. Condición C (Fixture de selección humana)
    res_c = {
        "condition": "C_seleccion_humana",
        "modo_ejecucion": "smoke_test_fixture (pendiente de corrida asistida con persona real)",
        "context_sources_used": ["Docs-Tecnicos-v24"],
        "context_chars_count": len(sources["spec_v24"]),
        "action_count": None,  # null
        "human_time_seconds": None,  # null
        "model_latency_seconds": None,  # null
        "total_elapsed_seconds": None,  # null
        "eval_correctness": eval_corr_b["tests_passed"],
        "eval_leak_detected": False,
        "coincidencias_lexicas": eval_cite_b["coincidencias_lexicas"],
        "verificacion_citas": eval_cite_b["verificacion_citas"],
        "code_delivered": resp_b["code"],
        "citations_delivered": resp_b["citations"],
        "test_suite_output": eval_corr_b.get("test_output", ""),
    }

    report = {
        "smoke_test_id": "smoke_test_fixture_case_01",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "task_name": "task_utility_01_regional_discounts",
        "nota_metodologica": (
            "Esta ejecución corresponde a un smoke test con fixtures pregrabados. "
            "No mide utilidad real, tiempo humano ni inferencia de modelo; por ello, "
            "dichas métricas no observadas permanecen en null de forma honesta."
        ),
        "comparison_matrix": {
            "A_ventana_sola": res_a,
            "B_seleccion_automatica": res_b,
            "C_seleccion_humana": res_c,
        }
    }

    (out_dir / "smoke_test_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    runs_dir = EXPERIMENTS_DIR / "runs" / "smoke_test_fixture"
    print("Ejecutando smoke test fixture de validación de arnés...")
    report = run_smoke_test(runs_dir)
    print(f"Smoke test completado exitosamente. Reporte: {runs_dir / 'smoke_test_report.json'}")
    print("  Condición A (Fixture):", "Correctness =", report["comparison_matrix"]["A_ventana_sola"]["eval_correctness"])
    print("  Condición B (Fixture):", "Correctness =", report["comparison_matrix"]["B_seleccion_automatica"]["eval_correctness"])
    print("  Condición C (Fixture):", "Correctness =", report["comparison_matrix"]["C_seleccion_humana"]["eval_correctness"])


if __name__ == "__main__":
    main()
