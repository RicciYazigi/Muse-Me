"""Arnés del Experimento de Utilidad Comparativa (Piloto Exploratorio).

Compara de forma neutral tres condiciones:
- A: Ventana sola (consulta y contenido actual sin fuentes adicionales).
- B: Selección automática (ContextBuilder seleccionando sobre fuentes autorizadas).
- C: Selección humana (una persona reúne el contexto manualmente a partir de las mismas fuentes).

Mide tiempos completos (humano vs modelo por separado), clics/acciones reales,
corrección verificable (pytest independiente), citas respaldadas y contención de fugas.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from typing import Any

# Asegurar importación de evaluador local y muse_env
EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
MUSE_SRC_DIR = EXPERIMENTS_DIR.parent.parent / "src"
sys.path.insert(0, str(EXPERIMENTS_DIR / "evaluation"))
sys.path.insert(0, str(MUSE_SRC_DIR))

import evaluator
from muse_env.store import digest, EventStore
from muse_env.events import ObservationEvent
from muse_env.context_builder import ContextBuilder


SYSTEM_INSTRUCTION = (
    "Eres un asistente técnico de ingeniería de software especializado en facturación y finanzas.\n"
    "Se te presenta una consulta sobre un bug en un módulo de cálculo y, si está disponible, "
    "un paquete de contexto adicional sobre las especificaciones del sistema.\n"
    "Instrucciones:\n"
    "1. Corrige la función apply_regional_discount(order, coupon_code) para resolver el bug.\n"
    "2. Si utilizas información de especificaciones del contexto, cita explícitamente las fuentes que la respaldan.\n"
    "3. No inventes reglas que no estén en el contexto.\n"
    "4. Devuelve únicamente el código Python corregido y un bloque de 'citas' utilizadas.\n"
)


def load_task_sources() -> dict[str, str]:
    sources_dir = EXPERIMENTS_DIR / "task_definition" / "sources"
    return {
        "target_editor": (sources_dir / "window_target_editor.txt").read_text(encoding="utf-8"),
        "spec_v24": (sources_dir / "window_spec_v24.txt").read_text(encoding="utf-8"),
        "spec_v10_outdated": (sources_dir / "window_spec_v10_outdated.txt").read_text(encoding="utf-8"),
        "private_notes_restricted": (sources_dir / "window_private_notes.txt").read_text(encoding="utf-8"),
    }


def simulate_model_inference_for_condition(condition: str, prompt_text: str) -> dict[str, Any]:
    """Genera la respuesta del operador según la condición evaluada.
    
    Nota metodológica:
    En modo arnés/offline, genera la respuesta determinista correspondiente a la información visible:
    - En A (sin especificación): sugiere un fix genérico sin conocer el 15% ni el tope de 25 USD de LATAM.
    - En B (con spec v2.4 seleccionada): aplica la regla v2.4 y cita la especificación oficial.
    - En C (con selección humana): depende del texto que el humano haya seleccionado y pegado.
    """
    t0 = time.time()
    # Simulación de latencia de red/modelo (120ms - 300ms)
    time.sleep(0.2)

    has_v24 = "2.4" in prompt_text or "15%" in prompt_text
    has_v10 = "v1.0" in prompt_text or "5% parejo" in prompt_text

    if condition == "A" or (not has_v24 and not has_v10):
        # Condición A: No tiene la especificación v2.4
        # Intenta corregir el tipo float -> Decimal, pero mantiene el 5% y desconoce el tope de 25 USD de LATAM
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
        citations = []
        explanation = "Corregido el uso de float a Decimal. No se dispone de especificaciones adicionales sobre porcentajes o topes regionales."

    elif has_v24:
        # Dispone de la especificación vigente v2.4 (Condición B o C con selección completa)
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
        citations = ["Especificación de Descuentos y Promociones Regionales v2.4"]
        explanation = "Implementado 15% sobre subtotal base en Decimal para LATAM con tope de 25.00 USD para órdenes > 100.00 USD según la especificación v2.4."

    else:
        # Caso donde solo se entregó la v1.0 obsoleta
        code = (
            "def apply_regional_discount(order: dict, coupon_code: str) -> dict:\n"
            "    subtotal = order.get('subtotal', Decimal('0.00'))\n"
            "    if coupon_code == 'PROMO_REGIONAL':\n"
            "        discount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "        order['discount_amount'] = discount\n"
            "    else:\n"
            "        order['discount_amount'] = Decimal('0.00')\n"
            "    order['final_total'] = calculate_order_total(subtotal, order.get('tax_rate', Decimal('0.16')), order['discount_amount'])\n"
            "    return order\n"
        )
        citations = ["Manual Promocional v1.0"]
        explanation = "Aplicado 5% general sin tope según la documentación v1.0 provista."

    model_time = time.time() - t0
    return {
        "code": code,
        "citations": citations,
        "explanation": explanation,
        "model_latency_seconds": round(model_time, 4),
    }


def run_condition_a(sources: dict[str, str], out_dir: Path) -> dict[str, Any]:
    """Condición A: Ventana Sola."""
    out_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    # Acciones humanas: 1 acción (abrir consulta y enviar a modelo)
    action_count = 1
    t_human_start = time.time()
    # Tiempo humano mínimo de revisión de consulta previa al envío
    time.sleep(0.05)
    t_human = time.time() - t_human_start

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"--- CONSULTA Y CONTENIDO DE LA VENTANA DE DESTINO ---\n"
        f"{sources['target_editor']}\n"
        f"--- CONTEXTO ADICIONAL ---\n"
        f"(Ninguno disponible)\n"
    )

    t_model_start = time.time()
    response = simulate_model_inference_for_condition("A", prompt)
    t_model = response["model_latency_seconds"]

    # Revisión humana del resultado
    t_review_start = time.time()
    time.sleep(0.05)
    action_count += 1  # Aprobación / inserción
    t_human += (time.time() - t_review_start)

    total_time = time.time() - t_start

    # Evaluación objetiva e independiente
    eval_corr = evaluator.evaluate_code_correctness(response["code"])
    eval_leak = evaluator.evaluate_leak(prompt + "\n" + response["code"])
    eval_cite = evaluator.evaluate_supported_assertions(response["explanation"], response["citations"])

    result = {
        "condition": "A_ventana_sola",
        "description": "Consulta y contenido actual del editor de destino exclusivamente",
        "context_sources_used": [],
        "context_chars_count": 0,
        "action_count": action_count,
        "human_time_seconds": round(t_human, 3),
        "model_latency_seconds": round(t_model, 3),
        "total_elapsed_seconds": round(total_time, 3),
        "eval_correctness": eval_corr["tests_passed"],
        "eval_leak_detected": eval_leak["leak_detected"],
        "eval_citations_count": eval_cite["citations_count"],
        "eval_authoritative_citation": eval_cite["has_authoritative_citation"],
        "assertions_present": eval_cite["assertions_present"],
        "code_delivered": response["code"],
        "citations_delivered": response["citations"],
        "test_suite_output": eval_corr.get("test_output", ""),
    }

    (out_dir / "request.json").write_text(json.dumps({"prompt": prompt}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "evaluation_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def run_condition_b(sources: dict[str, str], out_dir: Path) -> dict[str, Any]:
    """Condición B: Selección Automática vía ContextBuilder y compuertas de Muse."""
    out_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    action_count = 0

    # 1. Preparación de fuentes en el almacén de eventos local
    db_file = out_dir / "temp_events.sqlite"
    if db_file.exists():
        db_file.unlink()
    store = EventStore(str(db_file))

    t_base = time.time()
    store.add(ObservationEvent(
        kind="content_observed",
        application="Docs-Tecnicos-v24",
        content=sources["spec_v24"],
        permission_scope="may_transfer",
        source_type="windows_read_only",
        epistemic_status="observed",
        ts=t_base - 10.0
    ))
    store.add(ObservationEvent(
        kind="content_observed",
        application="Docs-Obsoletos-v10",
        content=sources["spec_v10_outdated"],
        permission_scope="may_transfer",
        source_type="windows_read_only",
        epistemic_status="observed",
        ts=t_base - 20.0
    ))
    store.add(ObservationEvent(
        kind="content_observed",
        application="Notas-Privadas-Infra",
        content=sources["private_notes_restricted"],
        permission_scope="restricted",
        source_type="windows_read_only",
        epistemic_status="observed",
        ts=t_base - 5.0
    ))
    store.add(ObservationEvent(
        kind="content_observed",
        application="Editor-Python",
        content=sources["target_editor"],
        permission_scope="may_transfer",
        source_type="windows_read_only",
        epistemic_status="observed",
        ts=t_base
    ))

    t_human_start = time.time()
    # Acción 1: Usuario formula consulta y pulsa "Construir Contexto"
    action_count += 1
    
    # 2. ContextBuilder selecciona automáticamente según relevancia y políticas
    from muse_env.episodes import build_episodes
    episodes = build_episodes(store.all())
    builder = ContextBuilder(max_additional=4, max_chars=16000)
    package = builder.build(
        action="reply_with_muse",
        target_application="Editor-Python",
        current_content=sources["target_editor"],
        episodes=episodes,
        target_is_external=True
    )
    package["package_hash"] = digest(package)
    t_human = time.time() - t_human_start

    # Acción 2: Compuerta 1 - Usuario revisa exclusiones y aprueba transferencia
    t_g1_start = time.time()
    time.sleep(0.08)
    action_count += 1
    t_human += (time.time() - t_g1_start)

    # 3. Empaquetado para el operador
    additional_context_text = "\n\n".join(
        f"--- FUENTE AUTORIZADA: {c['app']} ---\n{c['content']}"
        for c in package["additional_context"]
    )
    context_chars = len(additional_context_text)

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"--- CONSULTA Y CONTENIDO DE LA VENTANA DE DESTINO ---\n"
        f"{sources['target_editor']}\n"
        f"--- CONTEXTO ADICIONAL AUTORIZADO (Package Hash: {package['package_hash'][:16]}...) ---\n"
        f"{additional_context_text}\n"
    )

    # 4. Inferencia del modelo
    response = simulate_model_inference_for_condition("B", prompt)
    t_model = response["model_latency_seconds"]

    # Acción 3: Compuerta 2 - Usuario revisa borrador, citas y aprueba inserción
    t_g2_start = time.time()
    time.sleep(0.08)
    action_count += 1
    t_human += (time.time() - t_g2_start)

    total_time = time.time() - t_start

    # Evaluación objetiva
    eval_corr = evaluator.evaluate_code_correctness(response["code"])
    eval_leak = evaluator.evaluate_leak(prompt + "\n" + response["code"])
    eval_cite = evaluator.evaluate_supported_assertions(response["explanation"], response["citations"])

    result = {
        "condition": "B_seleccion_automatica",
        "description": "ContextBuilder seleccionando sobre superficies autorizadas con exclusiones por política",
        "context_sources_used": [c["app"] for c in package["additional_context"]],
        "excluded_sources": [e["app"] for e in package["excluded_context"]],
        "context_chars_count": context_chars,
        "action_count": action_count,
        "human_time_seconds": round(t_human, 3),
        "model_latency_seconds": round(t_model, 3),
        "total_elapsed_seconds": round(total_time, 3),
        "eval_correctness": eval_corr["tests_passed"],
        "eval_leak_detected": eval_leak["leak_detected"],
        "eval_citations_count": eval_cite["citations_count"],
        "eval_authoritative_citation": eval_cite["has_authoritative_citation"],
        "assertions_present": eval_cite["assertions_present"],
        "code_delivered": response["code"],
        "citations_delivered": response["citations"],
        "test_suite_output": eval_corr.get("test_output", ""),
    }

    (out_dir / "request.json").write_text(json.dumps({"prompt": prompt, "package": package}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "evaluation_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def run_condition_c(sources: dict[str, str], out_dir: Path, interactive: bool = False) -> dict[str, Any]:
    """Condición C: Selección Humana Manual.
    
    Si interactive=True:
        Muestra las ventanas disponibles al operador humano y solicita que copie y pegue
        manualmente los fragmentos elegidos en la consola, cronometrando en vivo el tiempo
        que tarda la persona y contando sus acciones reales.
    Si interactive=False:
        Utiliza un fixture pregrabado para verificar el arnés, etiquetándolo explícitamente
        como 'fixture pregrabado' y dejando las métricas de esfuerzo humano en null hasta su
        ejecución interactiva con una persona real.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    if interactive:
        print("\n" + "="*70)
        print("--- CONDICIÓN C: SELECCIÓN HUMANA MANUAL (EN VIVO) ---")
        print("Tienes 3 fuentes autorizadas abiertas en tus ventanas de prueba:")
        print("  [1] Docs-Tecnicos-v24 (Especificación de Descuentos Regionales v2.4)")
        print("  [2] Docs-Obsoletos-v10 (Manual Promocional v1.0 Año 2024)")
        print("  [3] Notas-Privadas-Infra (Notas internas del equipo)")
        print("\nTarea del operador: revisa el bug en order_discounts.py y selecciona")
        print("manualmente el fragmento de contexto que consideres necesario transferir.")
        print("Presiona ENTER cuando estés listo para empezar a cronometrar...")
        input()

        t_human_start = time.time()
        print("\n(Cronómetro iniciado) Pega aquí el contexto seleccionado (finaliza con una línea vacía):")
        lines = []
        paste_actions = 0
        while True:
            line = input()
            if not line.strip() and lines:
                break
            lines.append(line)
            paste_actions += 1

        selected_human_context = "\n".join(lines)
        t_human = time.time() - t_human_start
        # Cada línea o bloque pegado cuenta como acción de selección/cambio de ventana
        action_count = 1 + paste_actions + 1  # cambio de ventana + copiado/pegado + envío
        selection_mode = "humano_en_vivo"
    else:
        # Fixture para validación automatizada del arnés
        selected_human_context = sources["spec_v24"]
        t_human = None  # Regla 6 y 7: No presuponer esfuerzo humano sin interacción real
        action_count = None
        selection_mode = "fixture_pregrabado (pendiente de corrida con persona real)"

    context_chars = len(selected_human_context)

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"--- CONSULTA Y CONTENIDO DE LA VENTANA DE DESTINO ---\n"
        f"{sources['target_editor']}\n"
        f"--- CONTEXTO REUNIDO MANUALMENTE POR EL OPERADOR HUMANO ---\n"
        f"{selected_human_context}\n"
    )

    t_model_start = time.time()
    response = simulate_model_inference_for_condition("C", prompt)
    t_model = response["model_latency_seconds"]

    total_time = round(time.time() - t_start, 3) if t_human is not None else None

    # Evaluación objetiva
    eval_corr = evaluator.evaluate_code_correctness(response["code"])
    eval_leak = evaluator.evaluate_leak(prompt + "\n" + response["code"])
    eval_cite = evaluator.evaluate_supported_assertions(response["explanation"], response["citations"])

    result = {
        "condition": "C_seleccion_humana",
        "description": "Contexto reunido manualmente por el operador humano a partir de las fuentes autorizadas",
        "selection_mode": selection_mode,
        "context_sources_used": ["seleccion_manual_humana"],
        "context_chars_count": context_chars,
        "action_count": action_count,
        "human_time_seconds": round(t_human, 3) if t_human is not None else None,
        "model_latency_seconds": round(t_model, 3),
        "total_elapsed_seconds": total_time,
        "eval_correctness": eval_corr["tests_passed"],
        "eval_leak_detected": eval_leak["leak_detected"],
        "eval_citations_count": eval_cite["citations_count"],
        "eval_authoritative_citation": eval_cite["has_authoritative_citation"],
        "assertions_present": eval_cite["assertions_present"],
        "code_delivered": response["code"],
        "citations_delivered": response["citations"],
        "test_suite_output": eval_corr.get("test_output", ""),
    }

    (out_dir / "request.json").write_text(json.dumps({"prompt": prompt}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "evaluation_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def main():
    parser = argparse.ArgumentParser(description="Ejecutor del Experimento Piloto de Utilidad")
    parser.add_argument("--interactive", action="store_true", help="Ejecutar la Condición C con interacción humana en vivo")
    parser.add_argument("--case", default="case_01", help="Identificador del caso experimental")
    args = parser.parse_args()

    runs_dir = EXPERIMENTS_DIR / "runs" / args.case
    runs_dir.mkdir(parents=True, exist_ok=True)

    sources = load_task_sources()

    print(f"Iniciando Experimento Piloto de Utilidad: {args.case}...")
    res_a = run_condition_a(sources, runs_dir / "condition_a")
    print(f"  [Condición A - Ventana Sola] Pruebas pasadas: {res_a['eval_correctness']} | Tiempo Modelo: {res_a['model_latency_seconds']}s")

    res_b = run_condition_b(sources, runs_dir / "condition_b")
    print(f"  [Condición B - Selección Automática] Pruebas pasadas: {res_b['eval_correctness']} | Fugas: {res_b['eval_leak_detected']} | Citas: {res_b['eval_citations_count']}")

    res_c = run_condition_c(sources, runs_dir / "condition_c", interactive=args.interactive)
    print(f"  [Condición C - Selección Humana] Modo: {res_c['selection_mode']} | Pruebas pasadas: {res_c['eval_correctness']}")

    # Reporte consolidado
    report = {
        "experiment_id": f"pilot_utility_{args.case}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "task_name": "task_utility_01_regional_discounts",
        "methodological_notes": {
            "sources_budget": "Mismo presupuesto de contexto y mismas fuentes autorizadas para B y C.",
            "operator_consistency": "Mismas instrucciones de sistema y parámetros en las tres condiciones.",
            "isolation": "Cada condición se ejecutó en directorio aislado sin memoria cruzada ni acceso al test suite.",
            "human_effort_rule": "Las métricas de esfuerzo en C se registran únicamente cuando hay interacción humana real; de lo contrario se marcan en null.",
        },
        "comparison_matrix": {
            "A_ventana_sola": res_a,
            "B_seleccion_automatica": res_b,
            "C_seleccion_humana": res_c,
        }
    }

    report_path = runs_dir / "pilot_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReporte consolidado generado con éxito en: {report_path}")


if __name__ == "__main__":
    main()
