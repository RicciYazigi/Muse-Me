"""Muse-Me Governed Context MCP Server.
Exposes Muse-Me's authorized zero-trust context and evidence kernel to any MCP host
(Muse Code, Claude Code, Cursor, Codex) via standard JSON-RPC 2.0 stdio protocol.

MOAT: Unlike commodity desktop scrapers, Muse-Me enforces human-in-the-loop double gates,
identity allowlists, cryptographic readback, and tamper-evident audit trails.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Dict, List, Optional

from .project_memory import ProjectMemory
from .capabilities import (
    propose_deliverable,
    execute_deliverable_action,
    compare_evidence,
    CAPABILITY_DELIVERABLE_PRODUCTION,
    CAPABILITY_EVIDENCE_COMPARISON
)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "muse-me"
SERVER_VERSION = "0.2.0"

TOOLS_SPEC = [
    {
        "name": "get_context_package",
        "description": (
            "Recupera un paquete de contexto autorizado y verificado para un objetivo específico. "
            "Filtra estrictamente fuentes confidenciales (restricted/local-only), calcula citas "
            "criptográficas verificadas y declara las exclusiones motivadas."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Nombre del proyecto registrado en la memoria de Muse-Me (ej: 'demo-latam', 'default').",
                    "default": "demo-latam"
                },
                "goal": {
                    "type": "string",
                    "description": "Objetivo operativo o consulta sobre el cual compilar la evidencia."
                },
                "token_budget": {
                    "type": "integer",
                    "description": "Presupuesto máximo aproximado de tokens para el paquete (default: 1500).",
                    "default": 1500
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "propose_insertion",
        "description": (
            "Propone formalmente una acción o artefacto para una misión existente bajo Compuerta 2. "
            "Genera el hash criptográfico del borrador y lo deja listo para la aprobación humana."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mission_id": {
                    "type": "string",
                    "description": "Identificador de la misión retornado por get_context_package."
                },
                "title": {
                    "type": "string",
                    "description": "Título descriptivo del entregable o acción propuesta."
                },
                "custom_draft": {
                    "type": "string",
                    "description": "Borrador de texto o código propuesto para revisión."
                }
            },
            "required": ["mission_id"]
        }
    },
    {
        "name": "verify_state",
        "description": (
            "Inspecciona el estado de integridad de la memoria, misiones activas y detección de "
            "modificaciones en disco. Permite al host comprobar si la evidencia sigue vigente."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mission_id": {
                    "type": "string",
                    "description": "ID opcional de una misión para verificar si sus fuentes cambiaron."
                },
                "project": {
                    "type": "string",
                    "description": "Proyecto para listar fuentes, revisiones y estado del ledger."
                }
            }
        }
    }
]


class MuseMeMCPServer:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_path = os.environ.get("MUSE_MEMORY_DB", "data/demo_walkthrough/project_memory.sqlite")
        p = Path(db_path)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        self.memory = ProjectMemory(str(p))

    def get_context_package(self, goal: str, project: str = "demo-latam", token_budget: int = 1500, external: bool = True) -> Dict[str, Any]:
        """Tool 1: Compile governed context package with token budget, vigencia filter, and reasoned exclusions."""
        # R5 / Runtime validation: validate positive budget
        if not isinstance(token_budget, int) or token_budget <= 0:
            raise ValueError("token_budget debe ser un entero positivo.")
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal debe ser una cadena no vacía.")

        # Re-check on-disk sources for project to avoid delivering stale context before resume
        sources = self.memory.db.execute("SELECT source, root_path, relative_path, file_hash FROM source_files WHERE project=?", (project,)).fetchall()
        for sf in sources:
            if sf["root_path"] and sf["relative_path"]:
                dp = Path(sf["root_path"]) / sf["relative_path"]
                if dp.exists():
                    try:
                        cur_text = dp.read_text(encoding="utf-8")
                        import hashlib
                        cur_h = hashlib.sha256(cur_text.encode("utf-8")).hexdigest()
                        if cur_h != sf["file_hash"]:
                            # Auto-reingest or refresh source file hash so search reflects current reality
                            s_row = self.memory.db.execute("SELECT scope FROM sources WHERE project=? AND source=?", (project, sf["source"])).fetchone()
                            orig_scope = s_row["scope"] if s_row else "local-only"
                            self.memory.ingest_text(project, sf["root_path"], sf["relative_path"], scope=orig_scope)
                    except Exception:
                        pass

        char_budget = token_budget * 4
        search_res = self.memory.search_with_exclusions(project, goal, external=external, budget=char_budget)
        budgeted_evidence = search_res["selected"]
        excluded = search_res["excluded"]
        current_chars = sum(len(ev.get("content", "")) for ev in budgeted_evidence)

        if not budgeted_evidence:
            return {
                "status": "insufficient_evidence",
                "project": project,
                "goal": goal,
                "message": f"Evidencia insuficiente: no se encontraron fuentes vigentes y transferibles coincidentes en '{project}'.",
                "authorized_evidence": [],
                "excluded_sources": excluded
            }

        refs = {ev["source"]: ev["revision"] for ev in budgeted_evidence}
        mission_id = self.memory.checkpoint(project, goal, refs, capability=CAPABILITY_DELIVERABLE_PRODUCTION.id)

        return {
            "status": "authorized_package_ready",
            "mission_id": mission_id,
            "project": project,
            "goal": goal,
            "token_budget": token_budget,
            "estimated_tokens_used": int(current_chars / 4),
            "evidence_count": len(budgeted_evidence),
            "authorized_evidence": budgeted_evidence,
            "excluded_sources": excluded,
            "governance_note": "Evidencia autorizada bajo Compuerta 1. Requiere aprobación de Compuerta 2 antes de cualquier inserción."
        }

    def propose_insertion(self, mission_id: str, title: str = "Propuesta Contextual", custom_draft: Optional[str] = None) -> Dict[str, Any]:
        """Tool 2: Register action draft and proposal hash for Gate 2 approval."""
        res = propose_deliverable(self.memory, mission_id, title=title, custom_draft=custom_draft)
        return {
            "status": "proposal_registered",
            "mission_id": mission_id,
            "approved_draft_sha256": res["draft_sha256"],
            "requires_gate2_human_approval": True,
            "summary": f"Borrador registrado bajo hash {res['draft_sha256'][:16]}... Esperando confirmación de Compuerta 2.",
            "draft_preview": res.get("draft_markdown", "")[:400] + "..."
        }

    def verify_state(self, mission_id: Optional[str] = None, project: Optional[str] = None) -> Dict[str, Any]:
        """Tool 3: Audit evidence freshness and system ledger."""
        result: Dict[str, Any] = {"status": "ok"}
        if mission_id:
            try:
                state = self.memory.resume(mission_id)
                result["mission_status"] = {
                    "mission_id": mission_id,
                    "state": state.get("state"),
                    "needs_review": state.get("needs_review", False),
                    "changed_sources": state.get("changed_sources", []),
                    "artifact_path": state.get("artifact_path"),
                    "artifact_hash": state.get("artifact_hash")
                }
            except KeyError:
                result["mission_status"] = {"error": f"Misión '{mission_id}' no encontrada"}

        if project:
            sources = self.memory.db.execute("SELECT source, revision, scope FROM sources WHERE project=?", (project,)).fetchall()
            result["project_summary"] = {
                "project": project,
                "sources": [dict(s) for s in sources]
            }

        return result

    def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "get_context_package":
            goal = arguments.get("goal", "")
            proj = arguments.get("project", "demo-latam")
            budget = arguments.get("token_budget", 1500)
            # B1 Governance Invariant: The MCP consumer cannot lower the external security boundary.
            # External is unconditionally enforced to True regardless of caller input.
            return self.get_context_package(goal=goal, project=proj, token_budget=budget, external=True)
        elif name == "propose_insertion":
            mid = arguments.get("mission_id", "")
            title = arguments.get("title", "Propuesta Contextual")
            draft = arguments.get("custom_draft")
            return self.propose_insertion(mission_id=mid, title=title, custom_draft=draft)
        elif name == "verify_state":
            mid = arguments.get("mission_id")
            proj = arguments.get("project")
            return self.verify_state(mission_id=mid, project=proj)
        else:
            raise ValueError(f"Herramienta desconocida: {name}")

    def run_stdio(self):
        """Standard JSON-RPC 2.0 loop over stdin/stdout."""
        # Force utf-8 stdio
        if sys.platform == "win32":
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

        stdin_stream = sys.stdin.buffer
        stdout_stream = sys.stdout.buffer

        while True:
            line = stdin_stream.readline()
            if not line:
                break
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                msg = json.loads(line_str)
            except Exception:
                continue

            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
                    }
                }
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS_SPEC}
                }
            elif method == "tools/call":
                t_name = params.get("name")
                t_args = params.get("arguments", {})
                try:
                    tool_output = self.handle_call_tool(t_name, t_args)
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(tool_output, indent=2, ensure_ascii=False)
                                }
                            ]
                        }
                    }
                except Exception as e:
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32000,
                            "message": str(e),
                            "data": traceback.format_exc()
                        }
                    }
            elif method == "ping":
                res = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            out_bytes = (json.dumps(res, ensure_ascii=False) + "\n").encode("utf-8")
            stdout_stream.write(out_bytes)
            stdout_stream.flush()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Muse-Me MCP Server")
    parser.add_argument("--db-path", help="Ruta a la base de datos project_memory.sqlite", default=None)
    args = parser.parse_args()

    server = MuseMeMCPServer(db_path=args.db_path)
    server.run_stdio()


if __name__ == "__main__":
    main()