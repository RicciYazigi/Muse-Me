# Estado Operativo de Muse-Me (MUSE Environment)

**Fecha de corte:** 25 de octubre de 2026  
**Commit de código verificado:** `2f0b3dd3ab0302e6787d410430ddff1f46372864`  
**CI verificado:** Ejecución [#40162257110](https://github.com/RicciYazigi/Muse-Me/actions/runs/40162257110) en Windows y Ubuntu (Python 3.11, 3.12, 3.13) en éxito.  
**Suite de pruebas local:** 92 passed en 51.86 s en Windows 11 / Python 3.13 (sin fallos ni omisiones).  

Este documento es la **única fuente pública del estado técnico vigente** de Muse-Me. Los cambios posteriores a `2f0b3dd` corresponden exclusivamente a alineación documental, saneamiento de configuración y preservación de contexto privado; no modifican el código en `src/` ni `tests/`.

---

## 1. Identidad y Enfoque Real del Producto

Muse-Me busca ser un asistente contextual residente: acompaña la actividad en aplicaciones autorizadas por el usuario, mantiene una memoria temporal de trabajo y prepara ayuda concreta antes de que el usuario deba reconstruir su contexto en un chat de IA.

### Ciclo Objetivo
`actividad autorizada → episodio/contexto temporal → interpretación por modelo → ayuda preparada → invocación por usuario → propuesta concreta → acción autorizada → comprobación de resultado`

---

## 2. Lo que Funciona Hoy (Estado Verificado del Corte 2f0b3dd)

1. **Panel Local de Revisión (`run_panel.py`):**
   - Interfaz web local (`localhost:8080`) con `ProjectMemory` inicializada y cerrada determinísticamente.
   - Selección explícita de fuentes y permisos (`may_transfer`, `restricted`, `local-only`).
   - Visor de propuestas y vista previa Markdown de entregables.
   - Aprobación explícita de inserción (`user_approved=True`) y comprobación de readback.
2. **Memoria de Proyecto y Recuperación SQLite/FTS5 (`src/muse_env/project_memory.py`):**
   - Ingestión versionada con hashes SHA-256 por revisión.
   - Búsqueda léxica determinista; reporte honesto de «Evidencia insuficiente» si no hay coincidencias.
   - Reingestión preserva el ámbito de seguridad sin elevar permisos a `may_transfer`.
   - Revalidación ante cambios en disco (`needs_review=True` si un archivo cambia externamente).
3. **Observación y Control Nativo Win32 de Laboratorio (`src/muse_env/surfaces/`):**
   - Host desacoplado (`Win32TestHost`) con despacho de mensajes Windows.
   - Inserción `WM_SETTEXT` y lectura `WM_GETTEXT` sobre controles de prueba `EDIT`.
4. **Operador Asistido por Archivos (`src/muse_env/operators/antigravity.py`):**
   - Exportación de misiones (`request.json`) con digest de paquete.
   - Importación estricta de propuestas vinculando `mission_id`, `request_hash` y `payload_hash`.
   - Consumo atómico único en base de datos (`claim_mission`), previniendo repetición.
5. **Capacidades Locales Deterministas (`src/muse_env/capabilities.py`):**
   - `evidence_comparison` y `deliverable_production` implementadas mediante reglas y plantillas deterministas, no inferencia de modelo de lenguaje.
6. **Interfaz MCP stdio (`src/muse_env/mcp_server.py`):**
   - Exporta paquetes de contexto con `external=True` por defecto, excluyendo fuentes `local-only` y `restricted`.
7. **Integración Experimental Fuse (`src/muse_env/gate.py`, `src/muse_env/_fusible_vendor/`):**
   - Núcleo vendored de Fuse conectado a rutas de inserción y panel.
   - En estado `DEGRADE`, autoriza lecturas pero bloquea escrituras, transferencias e inserciones.
   - Umbrales configurados: 0.02 / 0.04 en sensor por defecto del panel; 0.04 / 0.08 en `GatePolicy` explícita.

---

## 3. Problemas Abiertos y Pendientes Conocidos del Corte

1. **Escape de ruta en entregables:** La validación de rutas absolutas fue incorporada, pero la rama de rutas relativas no comprueba pertenencia tras `resolve()` contra el directorio de artefactos permitido. Un destino relativo con `..` puede escapar de la carpeta de salida.
2. **Fuentes borradas en MCP:** Si un archivo importado es borrado en disco, MCP conserva la evidencia en caché y retorna `authorized_package_ready` en lugar de excluirlo o bloquear la operación.
3. **Aprobación persistente exacta:** Falta formalizar el registro persistente de aprobación ligado a actor, operación, contenido, destino exacto, caducidad y consumo atómico.
4. **Etiqueta visual de Meta en UI:** El panel web muestra estado «Conectado» basándose en disponibilidad (`available`), incluso cuando la clave esté en estado `configured_untested`.
5. **Inferencia Meta real:** `src/muse_env/providers.py` contiene el adaptador HTTP, pero no ha sido verificado con credenciales y endpoints en vivo. El repositorio no carga automáticamente archivos `.env`.
6. **Utilidad humana no acreditada empíricamente:** La condición B del piloto experimental demostró transporte estricto y readback; la generación independiente de la propuesta no quedó acreditada. No se ha demostrado productividad humana comparativa.
7. **Compatibilidad con aplicaciones arbitrarias de escritorio (UIA):** Solo existen controles Win32 `EDIT` de prueba de laboratorio; la compatibilidad general mediante UI Automation sigue pendiente.

---

## 4. Registro Histórico de Fases Anteriores

- **Fase 0 a Fase 5 (20–23 de octubre):** Construcción del núcleo P0, formalización de compuertas, panel local web y suite de 76 pruebas iniciales.
- **Fase 7 / Remediación 5ta Auditoría (24 de octubre):** Cierre de regresiones de invariants (F01–F10, A1–A7, corte `2f0b3dd`), alcanzando las 92 pruebas pasando al 100%.
- **Saneamiento Documental (25 de octubre):** Retiro de historiales extensos públicos, creación de memoria privada hermana (`muse-private-context`), normalización de procedencia y alineación documental con la realidad del código.
