# Roadmap Muse Environment
## P0 — Prueba de cadena (ESTE repo, sandbox)
Observer simulado → episodios → Context Builder → Invoke con stub → inserción aprobada →
Fuse A/B → cadena SHA-256. **Puerta:** `scripts/verify_all.sh` verde. ✅ condición de la propuesta.
## P0.0.2 — Correcciones locales
Identidad persistente, permisos completos, transferencia autorizada antes de la API,
aprobación del borrador exacto y destino, HTTP Meta comprobado con mock, cadena de
contenido y STOP conectado. Visor estático y todas las superficies simuladas.
Ver `COMO_FUNCIONA.md` para fronteras y contratos.
## P1 — Windows + acceso Meta disponible
- Adaptadores UIA reales en 3 superficies controladas (docs/ADAPTADORES_WINDOWS.md).
- `MetaMuseProvider` con clave real: verificar imagen + structured output + coste por invocación.
- Medición H5: ventana-sola vs transversal, con tareas-trampa («la memoria NO debe usarse»)
  y auditoría de fugas = 0. Métricas: exactitud ciega, esfuerzo del usuario, omisiones/invenciones.
- **Puerta de muerte:** si UIA no expone las superficies o lo transversal no mejora, se registra
  el negativo; no se maquilla.
## P2 — Adaptación
- Episodios `inferred` confirmables en el visor; memoria episódica persistente entre sesiones.
- Superficie Propose: UNA categoría (automatización candidata) con contrato de verificación.
- Fuse A/B con trazas reales; auto-mejora solo como propuesta → holdout → aprobación humana.
## Líneas rojas
Insertar ≠ enviar · observed ≠ inferred · hash = integridad ≠ verdad · Fuse apagable y nunca
única muralla · nada sale a un destino externo sin paquete visible y aprobación.
