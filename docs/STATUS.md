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
## Fase 7: Blindaje de Invariantes y Remediación de Auditorías (24-oct-2026)
- **Estado:** COMPLETADO.
- **Suite de Pruebas:** 81 passed en Windows (68 passed, 13 skipped en Linux).
- **Hallazgos Corregidos (F01 - F10):**
  - **F01 (P0):** `PanelEngine.__init__` ahora inicializa y cierra determinísticamente `self.project_memory`.
  - **F02 (P0):** `execute_deliverable_action` requiere aprobación explícita `user_approved=True` (no admite `True` por defecto).
  - **F03 (P1):** La ejecución idempotente de misiones completadas revalida el hash en disco; si el archivo fue alterado externamente, reporta `artifact_modified_on_disk` con `readback_verified=False`.
  - **F04 (P1):** Misiones completadas quedan selladas y rechazan re-propuestas (`ValueError`).
  - **F05 (P0 Privacidad):** `reingest_source` preserva el scope original (`restricted` o `local-only`); nunca eleva permisos a `may_transfer`.
  - **F06 (P1):** Búsqueda léxica sin coincidencias reporta honestamente `Evidencia insuficiente` sin error SQL ni volcado masivo.
  - **F06 (Ledger):** Implementada exportación de anclas criptográficas externas (`export_anchor` / `verify_against_anchor`) y modo SQLite WAL.
  - **F08 (P0 XSS):** Añadido `escapeHtml` en `panel.html` para todas las plantillas dinámicas de fuentes.
  - **F09 (P1 Path Traversal):** Rutas de `/api/open_artifact` y directorios de entregables restringidos estrictamente al espacio de trabajo.
  - **F10 (Configuración):** `pyproject.toml` aísla los fixtures del piloto de utilidad con `testpaths = ["tests"]` y `.env.example` sincronizado con `api.meta.ai/v1`.
