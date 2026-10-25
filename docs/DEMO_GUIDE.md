# Guión Reproducible de Demostración — Muse-Me (90–120 segundos)

Este guión describe el recorrido demostrable de Muse-Me para evaluadores técnicos, jurados del hackathon y usuarios.

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

## 2. Recorrido Paso a Paso (90–120 Segundos)

### Minuto 0:00 – 0:25 | Paso 1: Fuentes Autorizadas y Cero Fugas
1. **Problema:** Un desarrollador o auditor necesita resolver un incidente de facturación en la región LATAM sin exponer secretos de infraestructura ni basarse en documentación obsoleta.
2. **Fuentes incorporadas:**
   - `especificacion_v24.md` (Vigente: 15% de descuento, tope de 25 USD, scope: `may_transfer`).
   - `manual_v10_obsoleto.md` (Obsoleto: 5% genérico sin tope, scope: `may_transfer`).
   - `claves_privadas.txt` (Claves de API de Stripe y AWS, scope: `restricted`).
3. **Evidencia:** El sistema suprime de inmediato el contenido de `claves_privadas.txt`, garantizando cero fugas hacia operadores o modelos.

### Minuto 0:25 – 0:50 | Paso 2: Capacidad A — Comparar Evidencia
1. **Acción:** El usuario formula la pregunta: *"Determinar el porcentaje y tope de descuento aplicable en región LATAM"*.
2. **Selección:** Capacidad `Comparar Evidencia` (`evidence_comparison`).
3. **Resultado:**
   - Extrae afirmaciones formales de ambas fuentes.
   - Detecta y resalta la **discrepancia cuantitativa** (`15%` y `tope 25.00 USD` vs `5%` sin tope).
   - **Garantía epistemológica:** Señala la contradicción sin asumir arbitrariamente que el archivo más reciente es el correcto.

### Minuto 0:50 – 1:15 | Paso 3: Capacidad B — Producir Entregable
1. **Acción:** El usuario cambia de intención a: *"Generar informe formal de cálculo de descuentos para el equipo contable"*.
2. **Selección:** Capacidad `Producir Entregable` (`deliverable_production`).
3. **Resultado:**
   - El sistema genera un borrador estructurado en Markdown citando las revisiones autorizadas.
   - Calcula el hash determinista del borrador (SHA-256).

### Minuto 1:15 – 1:35 | Paso 4: Compuerta 2 y Escritura Verificada
1. **Acción:** El usuario inspecciona la vista previa y hace clic en **"Aprobar Inserción y Escribir en Disco"**.
2. **Ejecución y Verificación:**
   - Se crea el archivo `artifacts/informe_descuentos_latam_demo.md`.
   - Muse-Me realiza una comprobación readback inmediata leyendo el archivo desde el disco y recalculando el SHA-256.
   - Confirma `readback_verified: true` y marca la misión como consumida.
3. **Idempotencia:** Si se repite la acción para la misma misión, el sistema detecta el estado previo y no duplica el archivo.

### Minuto 1:35 – 2:00 | Paso 5: Oportunidad de Ayuda y Detección de Cambios
1. **Acción:** Un proceso externo modifica la especificación en disco.
2. **Detección:** En la siguiente consulta o reanudación (`resume`), el sistema detecta el cambio en disco:
   - Estado: `needs_review = true`.
   - Bloquea cualquier transferencia adicional (`payload`) hasta que el usuario reingeste y apruebe un nuevo checkpoint.
   - Muestra el banner reactivo: *"Cambió una fuente utilizada en este resultado; revisar o descartar"*.

---

## 3. Estado de Meta y Conexiones Externas
- **Modo Asistido:** Por defecto, el sistema opera con el operador asistido local (`AntigravityAssistedOperator`), garantizando total auditabilidad e independencia de red.
- **Inferencia Meta Real:** Si el usuario configura `MODEL_API_KEY` en su archivo local `.env`, el panel activa automáticamente el conector hacia Llama API manteniendo las mismas compuertas y aislamiento estricto.