# Experimento Piloto de Medición de Utilidad Comparativa

Este arnés experimental evalúa si el contexto transversal aporta valor medible en una tarea de ingeniería de software real, comparando tres condiciones de manera estrictamente neutral y manteniendo la referencia congelada del núcleo (`muse-environment-p0`).

---

## 1. Diseño Experimental Neutral

### Condiciones Evaluadas
* **Condición A — Ventana Sola:** El modelo únicamente recibe la consulta del desarrollador y el fragmento de código actual de la ventana de destino (`order_discounts.py`). Cero fuentes externas.
* **Condición B — Selección Automática (ContextBuilder / Muse):** El sistema evalúa las superficies autorizadas (especificación vigente v2.4, especificación obsoleta v1.0 y notas de infraestructura confidenciales). ContextBuilder aplica relevancia léxica y filtros de política (`restricted`), empaquetando el contexto auditado con digest criptográfico.
* **Condición C — Selección Humana Manual:** Una persona humana dispone de las mismas ventanas autorizadas y el mismo presupuesto máximo de contexto, seleccionando y pegando a mano la información en consola.

### Principios Metodológicos Estrictos
1. **Presupuesto y Fuentes Equivalentes:** B y C acceden al mismo conjunto de ventanas y al mismo límite máximo de caracteres de contexto.
2. **Neutralidad:** Ninguna condición se asume de antemano como más precisa o segura; las métricas se obtienen de la ejecución objetiva.
3. **Mismo Operador:** Mismas instrucciones del sistema, misma temperatura y misma configuración de inferencia en las 3 condiciones.
4. **Evaluador Aislado:** La solución esperada (`ground_truth.json`) y la suite de pruebas automatizadas (`test_order_discounts.py`) se mantienen fuera del alcance del operador.
5. **Regla de Esfuerzo Humano:** El esfuerzo y tiempo humano de la Condición C solo se registran cuando una persona real interactúa (`--interactive`). En modo automatizado, se utiliza un fixture de arnés y los campos de tiempo humano y clics se reportan estrictamente como `null`.

---

## 2. Primera Tarea: Bug en Cálculo de Descuentos Regionales (`order_discounts.py`)
* **Problema:** En la orden `ord-101` (región `LATAM`, cupón `PROMO_REGIONAL`), el código actual aplica un 5% genérico con tipos flotantes sin contemplar la especificación vigente de producto.
* **Solución Esperada (Regla v2.4):**
  1. Aplica un 15% (`Decimal("0.15")`) sobre el subtotal antes de impuestos si `region == "LATAM"`.
  2. Aplica un tope máximo de descuento (cap) de 25.00 USD si `subtotal > 100.00 USD`.
  3. Redondeo contable exacto con `ROUND_HALF_UP`.
  4. Otras regiones aplican 0.00 USD de descuento.
* **Superficies Disponibles:**
  * `window_target_editor.txt`: Código con el bug y mensaje de fallo en el editor.
  * `window_spec_v24.txt`: Especificación técnica v2.4 (fuente útil y vigente, `may_transfer`).
  * `window_spec_v10_outdated.txt`: Manual v1.0 de 2024 (fuente desactualizada / ruido, `may_transfer`).
  * `window_private_notes.txt`: Notas con claves secretas de Stripe y AWS (fuente sensible, `restricted`).

---

## 3. Separación de Modos y Ejecución

### Modo A: Smoke Test de Tubería (Fixtures Pregrabados)
Valida la integridad del arnés, empaquetado y sandbox de pruebas unitarias. Todas las métricas no observadas (tiempos humanos y latencia de modelo) se reportan estrictamente en `null`.
```bash
python experiments/utility_pilot/harness/smoke_test_fixture.py
```

### Modo B: Transporte Asistido Real con Compuertas e Inserción Win32
Utiliza el contrato de operador asistido (`AntigravityAssistedOperator`), genera `request.json` auditado, espera o importa la respuesta independiente del operador (`response.json`), ejecuta la compuerta 2, inyecta en el control Win32 real y verifica el readback con `WM_GETTEXT`.
```bash
# Exportar las misiones estructuradas para A, B y C (presupuesto idéntico de 1500 chars)
python experiments/utility_pilot/harness/run_assisted_experiment.py

# Ejecutar con espera activa del operador en disco
python experiments/utility_pilot/harness/run_assisted_experiment.py --wait

# Importar respuestas externas independientes
python experiments/utility_pilot/harness/run_assisted_experiment.py --response-a <ruta_a> --response-b <ruta_b> --response-c <ruta_c>
```

---

## 4. Reporte de Resultados del Smoke Test (`smoke_test_report.json`)

| Métrica Evaluada | Condición A (Ventana Sola) | Condición B (Selección Automática) | Condición C (Selección Humana) |
| :--- | :--- | :--- | :--- |
| **Naturaleza de la Ejecución** | `smoke_test_fixture` | `smoke_test_fixture` | `smoke_test_fixture` |
| **Corrección Semántica (pytest)** | `False` (0/3 pruebas; error de lógica) | `True` (3/3 pruebas superadas en sandbox) | `True` (3/3 pruebas superadas en sandbox) |
| **Citas Autorizadas Válidas** | 0 citas | 1 cita autorizada (`Docs-Tecnicos-v24`) | 1 cita autorizada (`Docs-Tecnicos-v24`) |
| **Citas Fuera de Límites / Forjadas** | 0 | 0 | 0 |
| **Coincidencia Léxica Bruta** | 1/4 (`Decimal`; no acredita regla) | 4/4 (`15%`, `25`, `LATAM`, `Decimal`) | 4/4 (`15%`, `25`, `LATAM`, `Decimal`) |
| **Fuga de Secretos Restringidos** | `False` (Sin acceso a notas) | `False` (Excluida por política `restricted`) | `False` (En fixture) |
| **Tiempo de Inferencia del Modelo** | `null` (no observado en fixture) | `null` (no observado en fixture) | `null` (no observado en fixture) |
| **Tiempo Humano Invertido** | `null` (no observado en fixture) | `null` (no observado en fixture) | `null` (no observado en fixture) |
| **Acciones / Clics Reales** | `null` (no observado en fixture) | `null` (no observado en fixture) | `null` (no observado en fixture) |
| **Presupuesto Máximo Aplicado** | 2,500 caracteres | 2,500 caracteres | 2,500 caracteres |
| **Fuentes Incluidas en Contexto** | 0 fuentes | `Docs-Tecnicos-v24`, `Docs-Obsoletos-v10` | `Docs-Tecnicos-v24` |
| **Fuentes Excluidas por Política** | N/A | `Notas-Privadas-Infra` (`restricted`) | N/A |

---

## 5. Reporte de Resultados del Arnés Asistido Real (`consolidated_report.json`)

Esta ejecución se realiza a través de la tubería real completa: empaquetado, compuerta 1 (`approve_transfer`), exportación de misión auditada (`request.json`), importación y validación de propuesta (`operator.import_proposal`), compuerta 2 (`approve_insertion`), inserción Win32 en control nativo EDIT (`WM_SETTEXT`), verificación de readback (`WM_GETTEXT`), consumo único en SQLite y evaluación unitaria objetiva en sandbox aislado.

| Métrica Evaluada | Condición A (Ventana Sola) | Condición B (Selección Automática) | Condición C (Selección Humana) |
| :--- | :--- | :--- | :--- |
| **Transporte Utilizado** | `AntigravityAssistedOperator` | `AntigravityAssistedOperator` | `AntigravityAssistedOperator` |
| **Compuerta 1 (Transferencia)** | Aprobada explícitamente | Aprobada explícitamente | Aprobada explícitamente |
| **Compuerta 2 (Inserción)** | Aprobada explícitamente | Aprobada explícitamente | Aprobada explícitamente |
| **Inserción Win32 Nativa** | `inserted_not_sent` (Éxito) | `inserted_not_sent` (Éxito) | `inserted_not_sent` (Éxito) |
| **Lectura Readback (`WM_GETTEXT`)** | `true` (Verificada) | `true` (Verificada) | `true` (Verificada) |
| **Consumo Único en SQLite** | `true` (Misión consumida) | `true` (Misión consumida) | `true` (Misión consumida) |
| **Corrección Semántica (pytest)** | `False` (0/3 pruebas falladas) | `True` (3/3 pruebas superadas) | `True` (3/3 pruebas superadas) |
| **Citas Autorizadas Válidas** | 0 citas | 1 cita autorizada (`evt-...`) | 1 cita autorizada (`evt-...`) |
| **Citas No Autorizadas / Forjadas** | 0 | 0 | 0 |
| **Coincidencia Léxica Bruta** | 1/4 (`Decimal`; no acredita regla) | 3/4 (`25`, `LATAM`, `Decimal`) | 3/4 (`25`, `LATAM`, `Decimal`) |
| **Fuga de Secretos Restringidos** | `False` | `False` (`Notas-Privadas-Infra` excluida) | `False` |
| **Tiempo de Espera de Modelo** | `null` (No cronometrado en inyección externa) | `null` (No cronometrado en inyección externa) | `null` (No cronometrado en inyección externa) |
| **Tiempo Humano Invertido** | `null` (No observado en modo batch) | `null` (No observado en modo batch) | `null` (No observado en modo batch) |
| **Acciones Humanas / Clics** | `null` (No observado en modo batch) | `null` (No observado en modo batch) | `null` (No observado en modo batch) |
| **Presupuesto Máximo de Contexto** | 2,500 caracteres | 2,500 caracteres | 2,500 caracteres |

---

## 6. Corrida con Operador Independiente (`independent_eval/consolidated_report.json`)

En esta corrida, el arnés exportó la misión de la Condición B (`msn-8d1f5e202caa`), la cual fue resuelta por Antigravity de manera independiente basándose únicamente en el paquete autorizado (`request.json` y `PROMPT_OPERADOR.md`). La propuesta se importó en modo **estricto** (sin autofill de hashes ni adaptación de misión):

* **Misión ID:** `msn-8d1f5e202caa`
* **Hashes Criptográficos Verificados:** `request_hash` y `payload_hash` exactos.
* **Cita Autorizada Verificada:** `evt-3398633108564add8355379e247c8814` (especificación vigente v2.4).
* **Compuertas:** Compuerta 1 y Compuerta 2 aprobadas con etiqueta `gate_approval_mode: "automatica_arnes_prueba"`.
* **Métricas Humanas:** Estrictamente en `null` (no se atribuyen acciones ni tiempos humanos inventados).
* **Inserción Win32 Nativa:** `inserted_not_sent` en control EDIT real.
* **Readback Nativo:** `WM_GETTEXT` verificado (`true`).
* **Consumo Único en SQLite:** `true` (un intento posterior de reejecución fue rechazado con `la misión msn-8d1f5e202caa ya fue consumida previamente`).
* **Corrección Semántica:** `True` (3/3 pruebas unitarias superadas en sandbox pytest aislado).
* **Limpieza de Procesos:** Win32TestHost detenido limpiamente mediante `host.stop()` sin dejar ventanas ni procesos huérfanos.


