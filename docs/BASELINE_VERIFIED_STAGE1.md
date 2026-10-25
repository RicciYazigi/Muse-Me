# Referencia de Línea Base Verificada — Etapa 1 (Flujo Asistido Win32 Nativo)

**Fecha:** 2026-10-21  
**Estado:** Cerrado y verificado (47/47 pruebas unitarias y de integración pasando).

---

## 1. Alcance Demostrado y Cerrado

1. **Host Persistente y Continuidad Entre Procesos:**
   - Host nativo de Windows (`scripts/win32_test_host.py` y `Win32TestHost`) manteniendo una ventana de control `EDIT` real con bucle de mensajes continuo de Windows (`GetMessageW` / `TranslateMessage` / `DispatchMessageW`).
   - Sobrevivencia y vinculación estricta entre procesos separados de exportación e importación/inserción.

2. **Intercambio Auditable y Criptográfico:**
   - Contrato formal: `MissionRequest` (`request.json`) $\to$ `MissionProposal` (`response.json`).
   - Validación bidireccional de hashes criptográficos (`request_hash`, `payload_hash`, `package_hash`) contrastados en memoria persistente SQLite (`assisted_memory.sqlite`).
   - Detección y bloqueo inmediato de manipulación de payloads o sustitución de identificadores de misión.

3. **Intervención Genuina del Operador Antigravity:**
   - Misión completada: `msn-000801c16ca1`.
   - Propuesta: `prop-antigravity-000801c16ca1`.
   - El operador inspeccionó `request.json` y `PROMPT_OPERADOR.md`, redactó una propuesta analítica basada exclusivamente en las fuentes autorizadas (`evt-07c0f87877e549b3a8512b92e692b4b6` y `evt-b4051bf1b8a8409ca86eac108faebb2f`) y la vinculó al digest exacto.

4. **Inserción y Lectura en Control Win32 Real:**
   - Inserción en control nativo vía `WM_SETTEXT`.
   - Verificación de readback idéntico vía `WM_GETTEXT`.
   - Estado de inserción: `inserted_not_sent`.
   - `readback_verified: true`, `chain_valid: true`, `outcome_verified: true`.

5. **Prevención de Repetición (Replay Prevention):**
   - Transición de estado en SQLite de `proposal_imported` a `consumed`.
   - Cualquier intento de reutilizar o reinsertar la misión genera rechazo inmediato (`la misión ya fue consumida previamente`).

---

## 2. Expedientes y Archivos de Evidencia Preservados

| Carpeta / Archivo | Rol en la Evidencia | Resultado |
|---|---|---|
| `data/runs/msn-028ef639dd04` | Intento inicial con control destruido prematuramente | `outcome_verified: false`, `insertion_status: blocked` (preservado como constancia) |
| `data/runs/msn-b721f99648fa` | Ejecución automatizada con fixture sintético de respuesta | `outcome_verified: true`, readback verificado |
| `data/runs/msn-000801c16ca1` | **Ejecución asistida interactiva real con Operador Antigravity** | `outcome_verified: true`, readback verificado, consumida en SQLite |

---

## 3. Lanzadores Preservados

- `run_assisted_native_flow.py` / `Start-AssistedNativeFlow.ps1`: Prueba técnica automatizada con respuesta sintética fija (fixture).
- `run_operator_assisted_flow.py` / `Start-OperatorAssistedFlow.ps1`: Flujo asistido con operador humano / Antigravity en vivo.

---

## 4. Transición a Etapa 2

El siguiente incremento incorpora:
- Observación Windows de solo lectura con activación explícita (opt-in).
- Captura de procedencia real (HWND, PID, títulos, clases de control) sobre 2 superficies autorizadas.
- Circuito completo con fuente pertinente, irrelevante y restringida, demostrando selección y exclusión estricta.
- Separación epistemológica explícita: observaciones reales (`observed`), inferencias (`inferred`) y datos sintéticos (`simulated`).
