> [!NOTE]
> **Documento Histórico de Exploración de Adaptadores (21 de octubre de 2026).**  
> La implementación actual cuenta con controles Win32 `EDIT` de prueba de laboratorio (`src/muse_env/surfaces/`). La integración general mediante UI Automation (UIA) corresponde a fases posteriores. Consultar [docs/STATUS.md](STATUS.md).

# Adaptadores Windows (P1) — contrato de interfaz
El observador de P0 emite `ObservationEvent` desde superficies simuladas. En Windows se
implementa la MISMA interfaz sin tocar Context Builder/Invoke/Gate:

| Canal | Implementación P1 | Eventos |
|---|---|---|
| Foco/ventana | `pywinauto` backend `uia`: ventana activa, título, proceso | `window_focus` |
| Estructural | Árbol UIA de la app permitida (`dump_tree`, valores de controles `Edit/Text`) | `content_observed` (solo apps allowlist) |
| Visual (respaldo) | Screenshot por evento de la ventana (no video continuo) → Muse Spark imagen si hace falta interpretar | `content_observed` status `inferred` hasta verificar |
| Archivos | Polling/`watchdog` solo en carpetas opt-in | `file_changed` |

Reglas: sin keylogging indiscriminado; contraseñas/campos seguros excluidos por tipo de
control UIA; apps fuera de allowlist = invisibles (ni el título se registra);
`restricted` se marca en origen (carpeta/app), nunca a posteriori.
La superficie destino del chat para la demo será propia/controlada (DOM de terceros es frágil).
