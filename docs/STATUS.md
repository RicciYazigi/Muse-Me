# Estado Operativo de Muse-Me (MUSE Environment)

Documento vivo de control técnico, evidencia y avance por fases.

## 1. Visión y Resumen del Sistema

MUSE (nombre público de producto: **Muse-Me**) es un entorno de asistencia contextual que conecta la actividad y las fuentes autorizadas del usuario con memoria, modelos y herramientas para comprender, decidir, crear y actuar según sus objetivos y permisos.

### Principios Fundamentales
1. **Autoridad y Permisos:** El operador (humano o modelo) propone; la aplicación conserva y valida permisos y ejecuta las acciones. El texto de una fuente no amplía permisos ni activa herramientas.
2. **Separación de Ciclos:** Captura, conservación, transferencia y escritura son fases desacopladas con compuertas explícitas (`approve_transfer`, `approve_insertion`).
3. **Integridad y Trazabilidad:** Todo paquete transferido y toda propuesta de inserción está respaldada por hashes SHA-256 y registrada en el ledger inmutable.
4. **Transparencia Epistémica:** Distinción rigurosa entre simulaciones/fixtures y ejecuciones empíricas. Métricas no observadas se declaran estrictamente como `null`.

---

## 2. Matriz de Estado por Fases

| Fase | Título | Estado | Evidencia Acreditada | Siguiente Acción |
| :--- | :--- | :--- | :--- | :--- |
| **Fase 0** | Fijar base y recuperar lo necesario | **Completada** | 73 tests pasando al 100% en Windows/Python 3.13; arnés `experiments/utility_pilot` incorporado sin `runs/`; manifiesto inicial en `.local/backup_phase0`. | Completada. |
| **Fase 1** | Publicar base limpia y reproducible | **Completada** | Repositorio `https://github.com/RicciYazigi/Muse-Me.git` inicializado con rama `main`, README completo en inglés, `.env.example`, `.gitignore` y CI en GitHub Actions. Primer commit subido (`3b0ea21`). | Completada. |
| **Fase 2** | Contexto, capacidades y persistencia | **Completada** | Contratos formales de dos capacidades (`evidence_comparison` y `deliverable_production`); revalidación en disco, detección reactiva de cambios y no duplicación (idempotencia). 76 tests pasando al 100%. | Completada. |
| **Fase 3** | Experiencia de producto clara | **Completada** | Panel local web unificado (`run_panel.py`), selección visual de fuentes y políticas, selector de capacidades, vista previa de Markdown, aprobación Compuerta 2 y comprobación de readback. | Completada. |
| **Fase 4** | Operador e integración Meta honesta | **Completada (Parcial Declarado)** | Adaptador Meta implementado con control de cabeceras, límites y timeouts. Sin `MODEL_API_KEY` en entorno, reporta honestamente «Meta pendiente de conexión» y opera en modo asistido local. | Bloqueo externo documentado: requiere clave de Meta en `.env`. |
| **Fase 5** | Verificación y demostración de valor | **Completada** | Script de recorrido canónico `demo_muse_me.py` (90–120s) ejecutado con éxito; 76 tests unitarios pasando al 100%; guión detallado en `docs/DEMO_GUIDE.md`. | Completada. |
| **Fase 6** | Entrega profesional y paquete final | **En Progreso** | Creación de commit final, tag v0.1.0, verificación de checkout limpio y generación de paquete ZIP con hash SHA-256. | Ejecutar Fase 6. |

---

## 3. Evidencia Técnica Reciente
- **Suite Automatizada:** 76 passed en 20.75 s en Windows 11 con Python 3.13.4 (`tests/test_capabilities.py`, `tests/test_muse_env.py`, `tests/test_operators.py`, `tests/test_panel.py`, `tests/test_project_memory.py`, `tests/test_windows_observer.py`).
- **Recorrido Demostrable:** `demo_muse_me.py` ejecutado al 100% con registro en `data/demo_walkthrough/walkthrough_evidence.json`.
- **Integridad de Entrega:** Artefacto `informe_descuentos_latam_demo.md` generado en `artifacts/` con readback SHA-256 verificado.