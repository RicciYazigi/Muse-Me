# Cómo Funciona Muse-Me

Muse-Me conecta la actividad en aplicaciones autorizadas con memoria contextual, modelos de lenguaje y herramientas de acción bajo compuertas de seguridad formales.

---

## 1. El Recorrido Objetivo (Asistencia Residente)

1. **Autorización:** El usuario selecciona qué aplicaciones o carpetas pueden observarse y qué alcance tiene cada una (`may_transfer`, `restricted`, `local-only`). Puede pausar la observación en cualquier momento.
2. **Observación y Episodios:** Un observador local registra cambios permitidos y los agrupa en episodios temporales con caducidad. Se registra la procedencia y la vigencia de cada dato.
3. **Interpretación Preparada:** Ante un hito significativo, el modelo interpreta el episodio y prepara opciones de ayuda concretas con evidencia y efecto previsto.
4. **Invocación:** El usuario invoca Muse-Me mediante un gesto o atajo rápido cuando necesita asistencia.
5. **Revisión y Compuerta 1:** El usuario revisa la propuesta. Si requiere inferencia externa, la compuerta `approve_transfer` verifica que no se incluyan fuentes `restricted`.
6. **Aprobación y Compuerta 2:** El usuario revisa y aprueba el borrador exacto para un destino específico (`approve_insertion`).
7. **Acción y Comprobación:** La aplicación ejecuta la acción en el destino autorizado y realiza una comprobación de lectura inmediata (`readback`). La memoria registra el resultado.

---

## 2. Lo que Hace el Prototipo Actual

En la versión actual (`2f0b3dd`):
- **Memoria y Contexto:** `ProjectMemory` ingesta archivos locales, calcula hashes SHA-256, versiona revisiones y realiza búsquedas léxicas mediante SQLite/FTS5.
- **Capacidades Locales:** Las opciones `Comparar Evidencia` y `Producir Entregable` operan mediante **reglas y plantillas deterministas locales**, no inferencia de modelo de lenguaje.
- **Superficie de Escritorio:** Opera sobre controles `EDIT` de prueba de laboratorio en Windows mediante Win32 API (`SendMessageW` / `WM_SETTEXT` / `WM_GETTEXT`).
- **Operador:** Funciona mediante el operador asistido por archivos (`AntigravityAssistedOperator`): exporta `request.json`, importa la propuesta estructurada, valida hashes y consume atómicamente la misión.
- **Sensor Fuse:** TrajectorySensor integrado experimentalmente. Si el riesgo acumulado alcanza el umbral de `DEGRADE`, permite lecturas pero bloquea escrituras e inserciones.
- **Configuración:** La aplicación lee `MODEL_API_KEY` del entorno del proceso; **no carga automáticamente archivos `.env`**.

---

## 3. Fronteras de Seguridad y Confianza

- **Compuertas Formales:** `approve_transfer` y `approve_insertion` son decisiones del operador humano o la política del sistema; nunca herramientas que se deleguen al modelo.
- **Integridad Criptográfica:** Todos los paquetes y borradores se identifican mediante digests SHA-256. Un hash acredita integridad contra alteraciones; no certifica verdad semántica ni consentimiento humano.
- **Aislamiento de Secretos:** Fuentes marcadas como `restricted` son excluidas rigurosamente de transferencias hacia modelos o herramientas externas.
