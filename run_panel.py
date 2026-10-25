"""Lanzador del Panel Local de Revisión de Muse Environment.

Permite probar la experiencia completa de uso de forma visual e interactiva:
1. Activar / desactivar captura de Windows (opt-in).
2. Seleccionar controles autorizados en el allowlist con políticas de captura y transferencia.
3. Revisar fuentes capturadas y exclusiones explícitas de ContextBuilder.
4. Autorizar el procesamiento (Compuerta 1).
5. Revisar el borrador y citas del operador Antigravity.
6. Aprobar la inserción exacta (Compuerta 2) y ejecutar en el control EDIT nativo con readback verificado.
7. Comprobar la integridad de la cadena criptográfica y la correspondencia con la tabla de procedencia.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from muse_env.panel.server import ReviewPanelServer
from muse_env.panel.engine import PanelEngine


def main():
    parser = argparse.ArgumentParser(description="Panel Local de Revisión de Muse Environment")
    parser.add_argument("--host", default="127.0.0.1", help="Host de escucha (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Puerto de escucha (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="No abrir automáticamente el navegador")
    args = parser.parse_args()

    port = args.port
    server = None
    for attempt in range(5):
        try:
            engine = PanelEngine()
            server = ReviewPanelServer(host=args.host, port=port + attempt, engine=engine)
            break
        except OSError as e:
            if attempt == 4:
                raise e
            print(f"Puerto {port + attempt} ocupado, intentando con {port + attempt + 1}...")

    actual_port = server.port
    url = f"http://{args.host}:{actual_port}"

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    server.run_forever()


if __name__ == "__main__":
    main()
