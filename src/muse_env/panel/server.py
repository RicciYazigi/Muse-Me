"""Servidor HTTP Local Seguro para el Panel de Revisión de Muse Environment.

Garantías de seguridad y robustez:
1. Sin CORS abierto: solo se permite tráfico de origen idéntico (same-origin).
2. Validación estricta de Host y Origin/Referer para rechazar orígenes ajenos (DNS rebinding / CSRF).
3. Token de sesión local criptográfico (X-Session-Token): generado por ejecución e inyectado en el cliente;
   todas las mutaciones y compuertas exigen validación de este token.
4. Soporte separado para importación de propuesta real en response.json y generador explícito de fixture.
"""
from __future__ import annotations

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets
import sys
import threading
from typing import Any
from urllib.parse import urlparse

from .engine import PanelEngine

STATIC_DIR = Path(__file__).resolve().parent / "static"


class PanelHTTPRequestHandler(BaseHTTPRequestHandler):
    engine: PanelEngine  # Inyectado por el servidor
    session_token: str   # Inyectado por el servidor
    expected_host: str   # Inyectado por el servidor
    port: int            # Inyectado por el servidor

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Connection", "close")
        # CORS abierto retirado estrictamente por seguridad local
        self.end_headers()

    def log_message(self, format, *args):
        pass

    def _validate_origin_and_host(self) -> bool:
        """Verifica que las peticiones provengan exclusivamente del host local y puerto exacto asignado."""
        host_header = self.headers.get("Host", "").strip()
        expected_hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        if self.port == 80:
            expected_hosts.update({"127.0.0.1", "localhost"})
        if host_header not in expected_hosts:
            return False

        origin = self.headers.get("Origin")
        if origin:
            valid_origins = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
            if self.port == 80:
                valid_origins.update({"http://127.0.0.1", "http://localhost"})
            if origin.strip() not in valid_origins:
                return False

        referer = self.headers.get("Referer")
        if referer:
            valid_ref_prefixes = (
                f"http://127.0.0.1:{self.port}/",
                f"http://localhost:{self.port}/",
            )
            if not any(referer.strip().startswith(prefix) for prefix in valid_ref_prefixes):
                return False

        return True

    def _validate_session_token(self) -> bool:
        """Comprueba que la petición contenga el token de sesión local generado."""
        token = self.headers.get("X-Session-Token", "")
        if not token or not secrets.compare_digest(token, self.session_token):
            return False
        return True

    def do_GET(self):
        if not self._validate_origin_and_host():
            self._set_headers(403, "application/json")
            self.wfile.write(json.dumps({"error": "Host u origen no autorizado"}).encode("utf-8"))
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html", "/panel.html"):
            html_file = STATIC_DIR / "panel.html"
            if html_file.exists():
                content = html_file.read_text(encoding="utf-8")
                # Inyectar el token de sesión local en la página HTML
                content = content.replace("__SESSION_TOKEN__", self.session_token)
                self._set_headers(200, "text/html")
                self.wfile.write(content.encode("utf-8"))
            else:
                self._set_headers(404, "text/plain")
                self.wfile.write(b"panel.html no encontrado")
            return

        if path == "/api/state":
            try:
                state = self.engine.get_state()
                self._set_headers(200)
                self.wfile.write(json.dumps(state).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404, "text/plain")
        self.wfile.write(b"Ruta no encontrada")

    def do_POST(self):
        # 1. Validación de Host y Origen (CSRF / Origin Check)
        if not self._validate_origin_and_host():
            self._set_headers(403, "application/json")
            self.wfile.write(json.dumps({"error": "Host u origen no autorizado"}).encode("utf-8"))
            return

        # 2. Validación de Token de Sesión Local para mutaciones de estado y compuertas
        if not self._validate_session_token():
            self._set_headers(403, "application/json")
            self.wfile.write(json.dumps({"error": "Sesión local no autorizada o token inválido (X-Session-Token requerido)"}).encode("utf-8"))
            return

        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except Exception:
                body = {}

        try:
            if path == "/api/opt_in":
                res = self.engine.set_opt_in(body.get("enabled", False))
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/surfaces/configure":
                res = self.engine.configure_surface(
                    hwnd=body["hwnd"],
                    authorized=body.get("authorized"),
                    capture_allowed=body.get("capture_allowed"),
                    permission_scope=body.get("permission_scope"),
                    application=body.get("application"),
                    window_title=body.get("window_title"),
                )
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/surfaces/set_text":
                res = self.engine.set_surface_text(
                    surface_id=body["surface_id"],
                    text=body.get("text", ""),
                )
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/observe":
                res = self.engine.observe()
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/build_context":
                res = self.engine.build_context(query=body.get("query"))
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/authorize_transfer":
                actor = body.get("actor", "operador-humano (panel local)")
                res = self.engine.authorize_transfer(actor=actor)
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            # Importar propuesta existente de disco sin sobrescribirla
            if path in ("/api/import_proposal", "/api/stage_proposal"):
                res = self.engine.import_proposal()
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            # Generar fixture de prueba sintético explícitamente etiquetado
            if path == "/api/generate_fixture_proposal":
                text = body.get("text")
                citations = body.get("citations")
                res = self.engine.generate_fixture_proposal(text=text, citations=citations)
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/approve_insertion":
                actor = body.get("actor", "operador-humano (panel local)")
                res = self.engine.approve_insertion(actor=actor)
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/execute_insertion":
                res = self.engine.execute_insertion()
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/check_readback":
                res = self.engine.check_target_readback()
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            if path == "/api/tamper_provenance":
                tamper_type = body.get("type", "pid")
                res = self.engine.tamper_provenance_test(tamper_type)
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
                return

            self._set_headers(404, "application/json")
            self.wfile.write(json.dumps({"error": f"Endpoint no encontrado: {path}"}).encode("utf-8"))

        except PermissionError as pe:
            self._set_headers(403, "application/json")
            self.wfile.write(json.dumps({"error": str(pe)}).encode("utf-8"))
        except Exception as exc:
            self._set_headers(500, "application/json")
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))


class ReviewPanelServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, engine: PanelEngine | None = None, session_token: str | None = None):
        self.host = host
        self.port = port
        self.engine = engine or PanelEngine()
        self.session_token = session_token or secrets.token_hex(24)

        class Handler(PanelHTTPRequestHandler):
            pass

        Handler.engine = self.engine
        Handler.session_token = self.session_token
        Handler.expected_host = self.host
        Handler.port = self.port

        self.server = HTTPServer((self.host, self.port), Handler)
        self.thread: threading.Thread | None = None

    def start_background(self) -> None:
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def run_forever(self) -> None:
        try:
            print(f"=== PANEL LOCAL DE REVISIÓN INICIADO ===")
            print(f"URL: http://{self.host}:{self.port}")
            print(f"Token de Sesión Local: {self.session_token[:8]}…")
            print("Presione Ctrl+C para detener el panel.")
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nDeteniendo panel...")
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        self.engine.close()
