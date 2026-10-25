# Guión Reproducible de Demostración — Muse-Me (90-120 segundos)

Este guión describe el recorrido demostrable del prototipo de Muse-Me para evaluadores técnicos, jurados y desarrolladores.

---

## 1. Preparación Rápida
Abra una terminal en la raíz del repositorio y ejecute:
```powershell
# Opción 1: Interfaz gráfica interactiva
python run_panel.py

# Opción 2: Demostración automatizada por consola
python demo_muse_me.py
```

---

## 2. Recorrido Demostrable (Paso a Paso)

### Minuto 0:00 - 0:25 | Paso 1: Fuentes Autorizadas y Aislamiento de Secretos
1. **Escenario sintético:** Un desarrollador necesita resolver un problema de facturación en la región LATAM sin exponer claves de infraestructura ni basarse en manuales obsoletos.
2. **Fuentes incorporadas en la demostración:**
   - `especificacion_v24.md` (Vigente: 15% descuento, tope 25 USD, scope: `may_transfer`).
   - `manual_v10_obsoleto.md` (Obsoleto: 5% genérico sin tope, scope: `may_transfer`).
   - `claves_privadas.txt` (Claves de API de prueba de Stripe y AWS, scope: `restricted`).
3. **Comprobación:** El sistema excluye estrictamente el contenido de `claves_privadas.txt` del paquete autorizado, demostrando el bloqueo de la fuente restringida en este caso de prueba.

### Minuto 0:25 - 0:50 | Paso 2: Capacidad A — Comparar Evidencia
1. **Consulta:** *"Determinar el porcentaje y tope de descuento aplicable en región LATAM"*.
2. **Selección:** Capacidad `Comparar Evidencia` (`evidence_comparison`).
3. **Resultado:**
   - La capacidad local extrae afirmaciones de ambas especificaciones.
   - Resalta la discrepancia cuantitativa (`15%` con tope de `25.00 USD` vs `5%` sin tope).
   - Señala la contradicción sin suponer arbitrariamente cuál fuente prevalece sin directiva del usuario.

### Minuto 0:50 - 1:15 | Paso 3: Capacidad B — Producir Entregable
1. **Intención:** *"Generar informe formal de cálculo de descuentos para el equipo contable"*.
2. **Selección:** Capacidad `Producir Entregable` (`deliverable_production`).
3. **Resultado:**
   - Genera un borrador estructurado en Markdown citando las revisiones autorizadas.
   - Calcula el hash determinista del borrador (SHA-256).

### Minuto 1:15 - 1:35 | Paso 4: Compuerta 2 y Escritura Verificada
1. **Acción:** Inspeccionar la vista previa y autorizar: **"Aprobar Inserción y Escribir en Disco"**.
2. **Ejecución y Verificación:**
   - Se crea el archivo en `artifacts/informe_descuentos_latam_demo.md`.
   - Muse-Me lee inmediatamente el archivo desde el disco y recalcula su SHA-256.
   - Confirma `readback_verified: true` y marca la misión como consumida.
3. **Idempotencia:** Repetir la acción sobre la misma misión detecta el estado consumido y no duplica el archivo.

### Minuto 1:35 - 2:00 | Paso 5: Detección de Cambios en Fuentes
1. **Acción:** Modificación externa de la especificación en disco.
2. **Detección:** El sistema detecta la alteración:
   - Marca `needs_review = true`.
   - Bloquea transferencias adicionales hasta que el usuario reingeste y apruebe un nuevo checkpoint.

---

## 3. Estado de la Integración con Meta
- **Modo Asistido Local:** Por defecto, el sistema opera con el operador asistido local (`AntigravityAssistedOperator`), garantizando total auditabilidad e independencia de red.
- **Conector a Meta:** El adaptador HTTP existe en `src/muse_env/providers.py` y lee `MODEL_API_KEY` del entorno del proceso. No hay carga automática de `.env` ni activación automática del panel a Meta; la conexión en vivo con un modelo de Meta requiere verificación con una cuenta del hackathon.
