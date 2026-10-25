"""Orchestrator for Authentic Operator-Assisted Win32 Native Flow.

Mantiene vivo el control nativo Win32 (EDIT) y coordina el flujo asistido real:
1. Inicia el host Win32 independiente.
2. Ejecuta export_mission.py --use-win32-real en un proceso separado.
3. Espera a que el operador (Antigravity) lea request.json y PROMPT_OPERADOR.md
   y redacte genuinamente response.json (sin cadenas sintéticas fijas).
4. Ejecuta complete_mission.py en un proceso separado para validar e insertar en el control vivo.
5. Comprueba el rechazo de repetición (replay prevention) en SQLite ejecutando complete_mission.py nuevamente.
6. Cierra ordenadamente el host Win32.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.surfaces.test_host import Win32TestHost


def main():
    if sys.platform != "win32":
        print("Este flujo requiere Windows.")
        return 1

    status_file = ROOT / "data" / "win32_test_host.json"
    host = Win32TestHost(status_file=status_file, title="MuseWin32PersistentHost")
    print("=== INICIANDO HOST PERSISTENTE WIN32 (OPERADOR ASISTIDO REAL) ===")
    host.start()
    print(f"[HOST ACTIVO] HWND: {host.hwnd} (0x{host.hwnd:08X}) | PID: {host.pid}")
    assert host.is_alive(), "El control del host no está activo"

    try:
        # Paso 1: Ejecutar export_mission.py en un proceso separado
        print("\n=== PASO 1: EXPORTACIÓN DE MISIÓN EN PROCESO SEPARADO ===")
        export_proc = subprocess.run(
            [sys.executable, str(ROOT / "export_mission.py"), "--use-win32-real"],
            capture_output=True,
            text=True,
            check=True
        )
        print(export_proc.stdout)

        # Extraer ID de misión exportada desde la salida
        mission_id = None
        for line in export_proc.stdout.splitlines():
            if "ID de Misión :" in line:
                mission_id = line.split(":")[-1].strip()
                break

        if not mission_id:
            raise RuntimeError("No se pudo obtener el ID de la misión exportada")

        mission_dir = ROOT / "data" / "runs" / mission_id
        pending_file = ROOT / "data" / "pending_operator_mission.json"
        pending_data = {
            "mission_id": mission_id,
            "mission_dir": str(mission_dir),
            "status": "waiting_operator_response",
            "timestamp": time.time(),
        }
        pending_file.write_text(json.dumps(pending_data, indent=2), encoding="utf-8")

        print(f"\n=== PASO 2: ESPERA DE RESPUESTA GENUINA DEL OPERADOR ANTIGRAVITY ===")
        print(f"Misión ID: {mission_id}")
        print(f"Carpeta: {mission_dir}")
        print("Por favor redactar response.json a partir de request.json y PROMPT_OPERADOR.md...")
        print("El host permanece vivo en este proceso mientras se redacta la respuesta.", flush=True)

        res_file = mission_dir / "response.json"
        wait_seconds = 0
        timeout_seconds = 300
        while not res_file.exists():
            time.sleep(1)
            wait_seconds += 1
            if wait_seconds % 10 == 0:
                print(f"Esperando response.json... ({wait_seconds}s transcurridos, Host HWND: {host.hwnd} vivo: {host.is_alive()})", flush=True)
            if wait_seconds > timeout_seconds:
                raise TimeoutError(f"Se excedió el tiempo límite ({timeout_seconds}s) esperando {res_file}")

        print(f"\n[RESPUESTA DETECTADA] Archivo: {res_file}")
        # Pequeña pausa para asegurar flush del archivo en disco
        time.sleep(0.5)

        # Comprobar que el host sigue vivo
        print(f"\n[COMPROBACIÓN] Verificando que el destino vivo persiste:")
        print(f"Host HWND: {host.hwnd} | IsAlive: {host.is_alive()}")
        assert host.is_alive(), "El host desapareció antes de continuar"

        # Paso 3: Ejecutar complete_mission.py en un proceso separado
        print("\n=== PASO 3: CONTINUACIÓN E INSERCIÓN EN PROCESO SEPARADO ===")
        complete_proc = subprocess.run(
            [sys.executable, str(ROOT / "complete_mission.py"), "--mission-id", mission_id],
            capture_output=True,
            text=True
        )
        print(complete_proc.stdout)
        if complete_proc.stderr:
            print("STDERR:", complete_proc.stderr)

        if complete_proc.returncode != 0:
            raise RuntimeError(f"complete_mission.py falló con código {complete_proc.returncode}")

        # Validar el reporte de resultado
        report_file = mission_dir / "resultado_mision.json"
        report = json.loads(report_file.read_text(encoding="utf-8"))
        print("\n=== EVIDENCIA SELLADA ===")
        print(f"- Misión              : {report['mission_id']}")
        print(f"- Modo                : {report['mode']}")
        print(f"- Superficie          : {report['surface']}")
        print(f"- Inserción           : {report['insertion_status']}")
        print(f"- Readback Verificado : {report['readback_verified']}")
        print(f"- Cadena Verificada   : {report['chain_valid']}")
        print(f"- Outcome Verificado  : {report['outcome_verified']}")

        assert report["mode"] == "asistido_win32_real", f"Modo incorrecto: {report['mode']}"
        assert report["surface"] == "windows_win32_control", f"Superficie incorrecta: {report['surface']}"
        assert report["insertion_status"] == "inserted_not_sent", f"Inserción falló: {report['insertion_status']}"
        assert report["readback_verified"] is True, "Readback no fue verificado"
        assert report["chain_valid"] is True, "Integridad de la cadena falló"
        assert report["outcome_verified"] is True, "Outcome verificado es False"

        # Paso 4: Probar rechazo de repetición (Replay Prevention)
        print("\n=== PASO 4: PRUEBA DE RECHAZO DE REPETICIÓN (REPLAY) ===")
        replay_proc = subprocess.run(
            [sys.executable, str(ROOT / "complete_mission.py"), "--mission-id", mission_id],
            capture_output=True,
            text=True
        )
        print("Salida replay:", replay_proc.stdout)
        if replay_proc.returncode == 0:
            raise RuntimeError("ERROR: Se esperaba rechazo de repetición, pero complete_mission.py tuvo código 0")
        assert "ya fue consumida previamente" in replay_proc.stdout or "ya fue consumida previamente" in replay_proc.stderr, "Mensaje de rechazo de replay no encontrado"
        print("Rechazo de repetición comprobado y verificado en SQLite con éxito.")

        if pending_file.exists():
            pending_file.unlink()

        print("\n=== FLUJO ASISTIDO CON OPERADOR ANTIGRAVITY COMPLETADO EXITOSAMENTE ===")
        return 0

    finally:
        print("\n=== CERRANDO HOST PERSISTENTE WIN32 ===")
        host.stop()
        print("[HOST CERRADO ORDENADAMENTE]")


if __name__ == "__main__":
    sys.exit(main())
