# Muse-Me: Guía de Inicio Rápido

Bienvenido a Muse-Me. Este repositorio contiene la base experimental para un asistente contextual residente en Windows.

---

## 1. Documentos Principales

- **[README.md](README.md):** Visión del producto, estado actual, límites y cómo probarlo.
- **[docs/STATUS.md](docs/STATUS.md):** Única fuente pública del estado técnico vigente (commit `2f0b3dd` verificado con 92 pruebas).
- **[docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md):** Guión de demostración de 90-120 segundos.
- **[docs/ROADMAP.md](docs/ROADMAP.md):** Prioridades de desarrollo para la asistencia residente (H0 a H5).
- **[docs/COMO_FUNCIONA.md](docs/COMO_FUNCIONA.md):** Explicación del ciclo objetivo y los mecanismos actuales.

---

## 2. Cómo Probar el Prototipo en Windows

### Requisitos
- Windows 10 o 11 (para controles Win32 nativos).
- Python 3.11, 3.12 o 3.13 (CI cubre estas versiones).

### Instalación
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### Opción A: Panel Local Interactivo
El panel local integra `ProjectMemory`, selección de fuentes, políticas de seguridad y controles de laboratorio Win32:
```powershell
.\.venv\Scripts\python.exe run_panel.py
```
Abre automáticamente el navegador en `http://localhost:8080`.

### Opción B: Demostración Automatizada por Consola
Para un recorrido determinista rápido sin interfaz gráfica:
```powershell
.\.venv\Scripts\python.exe demo_muse_me.py
```
Este script genera datos de prueba sintéticos en una carpeta aislada y comprueba las compuertas de seguridad y la escritura con readback verificado.

---

## 3. Ejecución de Pruebas Automatizadas

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```
El corte verificado reproduce **92 pruebas pasando al 100%**.
