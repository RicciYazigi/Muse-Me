# Estado Operativo de Muse-Me (MUSE Environment)

Documento vivo de control técnico, evidencia y avance por fases.

## 1. Visión y Resumen del Sistema

MUSE (nombre público de producto: **Muse-Me**) es un entorno de asistencia contextual que conecta la actividad y las fuentes autorizadas del usuario con memoria, modelos y herramientas para comprender, decidir, crear y actuar según sus objetivos y permisos.

### Principios Fundamentales
1. **Autoridad y Permisos:** El operador (humano o modelo) propone; la aplicación conserva y valida permisos y ejecuta las acciones. El texto de una fuente no amplía permisos ni activa herramientas.
2. **Separación de Ciclos:** Captura, conservación, transferencia y escritura son fases desacopladas con compuertas explícitas (`approve_transfer`, `approve_insertion`).
3. **Integridad y Trazabilidad:** Todo paquete transferido y toda propuesta de inserción está respaldada por hashes SHA-256 y registrada en el ledger inmutable.
4. **Transparencia Epistémica:** Distinción rigurosa entre simulaciones/fixtures y ejecuciones empíricas. Métricas no observadas se declaran como `null`.

---

## 2. Matriz de Estado por Fases

| Fase | Título | Estado | Evidencia Acreditada | Siguiente Acción |
| :--- | :--- | :--- | :--- | :--- |
| **Fase 0** | Fijar base y recuperar lo necesario | **Completada** | 73 tests pasando al 100% en Windows/Python 3.13; arnés `experiments/utility_pilot` incorporado sin `runs/`; manifiesto inicial en `.local/backup_phase0`. | Iniciar Fase 1 (limpieza y publicación git inicial). |
| **Fase 1** | Publicar base limpia y reproducible | **En Progreso** | `.gitignore` ampliado, CI GitHub Actions (`ci.yml`), README estructurado en inglés. | Inicializar Git, configurar remoto autorizado y realizar primer push verificado. |
| **Fase 2** | Contexto, capacidades y persistencia | **Pendiente** | `ProjectMemory` operativo por CLI (FTS5, revisiones, checkpoints). | Integrar contratos formales de dos capacidades: "Comparar evidencia" y "Producir entregable" con persistencia y no duplicación. |
| **Fase 3** | Experiencia de producto clara | **Pendiente** | Panel web local heredado con controles Win32 y tokens de sesión. | Unificar panel con `ProjectMemory`, selección de capacidades y visualización de artefactos en un solo lanzador. |
| **Fase 4** | Operador e integración Meta honesta | **Pendiente** | Adaptador Meta y contrato `AntigravityAssistedOperator`. | Validación de credenciales locales en `.env`, llamadas acotadas o etiquetado transparente de "Meta pendiente". |
| **Fase 5** | Verificación y demostración de valor | **Pendiente** | Smoke tests de tubería y tests unitarios. | Guion de demo (90–120s), dos escenarios sintéticos y evidencia de lectura de entregables. |
| **Fase 6** | Entrega profesional y paquete final | **Pendiente** | - | Tag release, verificación de checkout limpio y paquete ZIP con SHA-256. |

---

## 3. Evidencia Técnica Reciente
- **Suite de Pruebas:** 73 passed en Windows 11 con Python 3.13.4 (`tests/test_muse_env.py`, `tests/test_operators.py`, `tests/test_panel.py`, `tests/test_project_memory.py`, `tests/test_windows_observer.py`).
- **Arnés Experimental:** `smoke_test_fixture.py` ejecutado y validado en sandbox local.
- **Inventario Inicial:** Registrado con hashes SHA-256 en `.local/backup_phase0/initial_manifest.csv`.
