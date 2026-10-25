"""Orchestrator for Automated Win32 Native Flow (Synthetic Fixture Response).

Prueba automatizada integral del ciclo técnico de destino Win32 real:
1. Spawns persistent Win32 EDIT control host.
2. Runs export_mission.py --use-win32-real as a separate process.
3. Generates synthetic response fixture (automated testing of hash validation).
4. Runs complete_mission.py as a separate process against the same living control.
5. Verifies outcome_verified: true, readback: CORRECTO, chain: True.
6. Tests replay rejection on complete_mission.py.
7. Shuts down the persistent host.

Nota: Para la ejecución asistida con respuesta humana/operador manual en vivo,
usar el flujo interactivo: win32_test_host.py -> export_mission.py -> (redacción manual) -> complete_mission.py.
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
    print("=== INICIANDO HOST PERSISTENTE WIN32 ===")
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
        req_file = mission_dir / "request.json"
        req_data = json.loads(req_file.read_text(encoding="utf-8"))

        print(f"\n=== PASO 2: GENERACIÓN DE RESPUESTA POR OPERADOR ANTIGRAVITY ===")
        print(f"Misión: {mission_id}")
        print(f"Request Hash: {req_data['package_hash'][:16]}...")
        print(f"Fuentes autorizadas: {req_data['allowed_sources']}")

        # Respuesta estructurada del Operador Antigravity fuera del script de demo
        res_data = {
            "proposal_id": f"prop-native-live-{mission_id[-6:]}",
            "mission_id": mission_id,
            "request_hash": req_data["package_hash"],  # digest se valida en import
            "request_hash": req_file.parent.joinpath("request.json"),  # placeholder, leer digest real:
        }
        # Cargar digest exacto del request:
        from muse_env.operators.contract import MissionRequest
        req_obj = MissionRequest(**req_data)
        res_data = {
            "proposal_id": f"prop-native-live-{mission_id[-6:]}",
            "mission_id": mission_id,
            "request_hash": req_obj.digest,
            "payload_hash": req_obj.payload_hash,
            "text": "El error 422 (Unprocessable Entity) en FastAPI es originado por fallos de validación en los esquemas Pydantic cuando los tipos o estructuras recibidas no concuerdan con la especificación. Para corregirlo, verifique que los parámetros de entrada respeten estrictamente los tipos definidos.",
            "citations": [
                req_obj.allowed_sources[0],
                req_obj.allowed_sources[1]
            ],
            "operator_identity": "antigravity-ide:agent",
            "actions_requested": []
        }
        res_file = mission_dir / "response.json"
        res_file.write_text(json.dumps(res_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Respuesta generada en: {res_file}")

        # Comprobar que el host sigue exactamente vivo antes de la continuación
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
        print("Salida del reintento:")
        print(replay_proc.stderr if replay_proc.stderr else replay_proc.stdout)
        assert replay_proc.returncode != 0, "El reintento con la misma misión debió ser rechazado"
        assert "ya fue consumida previamente" in (replay_proc.stderr + replay_proc.stdout), "Falta mensaje de misión consumida"
        print("[ÉXITO] El reintento de la misión consumida fue bloqueado inmediatamente.")

        print("\n================================================================================")
        print(f"MISIÓN {mission_id} COMPLETADA CON ÉXITO Y SELLADA (OUTCOME_VERIFIED: TRUE)")
        print("================================================================================")
        return 0
    finally:
        print("\n=== DETENIENDO HOST PERSISTENTE ===")
        host.stop()
        print("[HOST DETENIDO] Recursos liberados limpiamente.")


if __name__ == "__main__":
    sys.exit(main())
