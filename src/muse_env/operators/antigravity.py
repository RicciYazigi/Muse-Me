"""Antigravity Assisted Operator Adapter.

Provides auditable export of authorized mission requests and validation of operator proposals.
Enforces explicit transfer authorization prior to file export and strict cryptographic binding
between requests, proposals, and single-use mission lifecycles in the EventStore ledger.
"""
from __future__ import annotations
import json
from pathlib import Path
from uuid import uuid4
from ..context_builder import provider_payload
from ..gate import checkpoint
from ..invoke import TransferApproval
from ..store import digest
from .contract import MissionRequest, OperatorProposal, canonical_json, sha256_digest


class AntigravityAssistedOperator:
    name = "antigravity-operator (asistido: intercambio auditable)"
    # Tratado como externo a nivel de frontera de confianza para exigir TransferApproval
    is_external = True
    mode = "asistido"

    def __init__(self, run_dir: Path | str | None = None, operator_identity: str = "antigravity-ide:agent", store=None):
        self.run_dir = Path(run_dir) if run_dir else None
        self.operator_identity = operator_identity
        self.store = store
        self._staged_proposal: OperatorProposal | None = None
        self._staged_request: MissionRequest | None = None

    @property
    def identity(self) -> str:
        return f"{self.name}@{self.operator_identity} [modo={self.mode}]"

    def create_mission_request(self, *, package: dict, surface, task: str = "Responder con contexto autorizado") -> MissionRequest:
        outbound = provider_payload(package)
        allowed = sorted({item["source"] for item in [outbound["current_context"], *outbound["additional_context"]]})
        mission_id = f"msn-{uuid4().hex[:12]}"
        return MissionRequest(
            mission_id=mission_id,
            task=task,
            action=package["action"],
            package_hash=digest(package),
            payload_hash=digest(outbound),
            target_application=surface.name,
            target_id=surface.target_id,
            allowed_sources=allowed,
            outbound_payload=outbound,
            operator_target="antigravity",
            mode=self.mode,
        )

    def export_mission(
        self,
        request: MissionRequest,
        target_dir: Path | str,
        *,
        store=None,
        transfer_approval: TransferApproval | None = None,
        package: dict | None = None,
    ) -> dict[str, Path]:
        active_store = store or self.store
        if active_store is None:
            raise ValueError("export_mission requiere un EventStore activo para revalidación y registro")

        # 1. Revalidación estricta del paquete contra el almacén de eventos
        if package is None:
            raise ValueError("se requiere el paquete original para revalidar permisos contra EventStore")
        from copy import deepcopy
        package = deepcopy(package)
        ok, reason = checkpoint(package, store=active_store, transfer_required=True)
        if not ok:
            raise PermissionError(f"exportación rechazada por política: {reason}")

        # Derivar canónicamente el payload y recalcular hashes reales
        derived_payload = provider_payload(package)
        actual_package_hash = digest(package)
        actual_payload_hash = digest(derived_payload)

        # Verificar correspondencia estricta entre la solicitud y el paquete validado
        if request.package_hash != actual_package_hash:
            raise ValueError(f"package_hash de la solicitud difiere del paquete validado: {request.package_hash} != {actual_package_hash}")
        if request.payload_hash != actual_payload_hash:
            raise ValueError(f"payload_hash de la solicitud difiere del payload derivado: {request.payload_hash} != {actual_payload_hash}")
        if request.outbound_payload != derived_payload:
            raise ValueError("el outbound_payload de la solicitud fue alterado y difiere del derivado del paquete validado")

        # 2. Exigir autorización de transferencia válida y vinculada
        if not isinstance(transfer_approval, TransferApproval) or not transfer_approval.actor:
            raise PermissionError("exportación requiere autorización de transferencia explícita")
        expected = (actual_package_hash, actual_payload_hash, self.identity)
        actual = (transfer_approval.package_hash, transfer_approval.payload_hash, transfer_approval.provider_id)
        if actual != expected:
            raise PermissionError("la autorización de transferencia no corresponde a este paquete, payload u operador")

        # 3. Registrar misión y autorización en el ledger persistente
        active_store.save_mission(request.mission_id, request.digest, request.payload_hash, state="exported")
        active_store.append_intervention("mission_exported", {
            "mission_id": request.mission_id,
            "request_hash": request.digest,
            "payload_hash": request.payload_hash,
            "operator": self.identity,
            "actor": transfer_approval.actor,
        })

        # 4. Escribir archivos auditables utilizando el request canónico verificado
        folder = Path(target_dir) / request.mission_id
        folder.mkdir(parents=True, exist_ok=True)

        req_path = folder / "request.json"
        req_path.write_text(canonical_json(request.to_dict()), encoding="utf-8")

        prompt_path = folder / "PROMPT_OPERADOR.md"
        prompt_content = f"""# Solicitud de Misión para Operador Antigravity

**ID Misión:** `{request.mission_id}`
**Modo:** `{request.mode}`
**Aplicación Destino:** `{request.target_application}` (ID: `{request.target_id}`)
**Hash Solicitud (Digest):** `{request.digest}`
**Hash Paquete:** `{request.package_hash}`
**Hash Payload:** `{request.payload_hash}`

## Tarea
{request.task}

## Fuentes de Contexto Autorizadas (Citas permitidas ÚNICAMENTE de esta lista)
"""
        for src in request.allowed_sources:
            prompt_content += f"- `{src}`\n"

        prompt_content += f"""
## Payload Mínimo Autorizado
```json
{json.dumps(derived_payload, indent=2, ensure_ascii=False)}
```

## Formato Requerido para `response.json`
El operador debe generar `response.json` en esta misma carpeta vinculando la solicitud exacta:
```json
{{
  "proposal_id": "prop-{uuid4().hex[:12]}",
  "mission_id": "{request.mission_id}",
  "request_hash": "{request.digest}",
  "payload_hash": "{request.payload_hash}",
  "text": "Tu propuesta de respuesta utilizando únicamente la evidencia de las fuentes autorizadas.",
  "citations": ["{request.allowed_sources[0] if request.allowed_sources else 'evt-xxx'}"],
  "operator_identity": "{self.operator_identity}",
  "actions_requested": []
}}
```
"""
        prompt_path.write_text(prompt_content, encoding="utf-8")
        return {"request_file": req_path, "prompt_file": prompt_path, "mission_dir": folder}

    def import_proposal(
        self, response_file: Path | str, request: MissionRequest, *, store=None
    ) -> OperatorProposal:
        active_store = store or self.store
        path = Path(response_file)
        if not path.exists():
            raise FileNotFoundError(f"archivo de respuesta no encontrado: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))

        # Validación 1: Correspondencia de ID de misión
        if data.get("mission_id") != request.mission_id:
            raise ValueError(f"misión no coincide: esperada {request.mission_id}, recibida {data.get('mission_id')}")

        # Validación 2: Correspondencia exacta de hashes de solicitud y payload
        if data.get("request_hash") != request.digest:
            raise ValueError(
                f"request_hash no coincide con la solicitud exacta: esperado {request.digest}, recibido {data.get('request_hash')}"
            )
        if data.get("payload_hash") != request.payload_hash:
            raise ValueError(
                f"payload_hash no coincide con el payload exacto: esperado {request.payload_hash}, recibido {data.get('payload_hash')}"
            )

        # Validación 3: Estado y correspondencia de hashes en el almacén persistente
        if active_store:
            m = active_store.get_mission(request.mission_id)
            if not m:
                raise ValueError(f"misión {request.mission_id} no está registrada en el almacén")
            if m["request_hash"] != request.digest or m["payload_hash"] != request.payload_hash:
                raise ValueError(
                    f"los hashes de la solicitud no coinciden con el registro persistente de la misión: "
                    f"({request.digest[:16]}, {request.payload_hash[:16]}) != ({m['request_hash'][:16]}, {m['payload_hash'][:16]})"
                )
            if m["state"] == "consumed":
                raise ValueError(f"la misión {request.mission_id} ya fue consumida previamente")
            active_store.update_mission_state(request.mission_id, "proposal_imported")

        # Validación 4: Citas de fuentes
        citations = data.get("citations", [])
        proposal = OperatorProposal(
            proposal_id=data.get("proposal_id", f"prop-{uuid4().hex[:12]}"),
            mission_id=request.mission_id,
            request_hash=data.get("request_hash", ""),
            payload_hash=data.get("payload_hash", ""),
            text=data.get("text", ""),
            citations=citations,
            operator_identity=data.get("operator_identity", self.operator_identity),
            mode=self.mode,
            actions_requested=data.get("actions_requested", []),
            status="proposal_ready",
        )

        if not proposal.validate_citations(request.allowed_sources):
            invalid = [c for c in citations if c not in request.allowed_sources]
            raise ValueError(f"cita(s) fuera de las fuentes autorizadas: {invalid}")

        self._staged_proposal = proposal
        self._staged_request = request
        return proposal

    def stage_proposal(self, proposal: OperatorProposal, request: MissionRequest | None = None):
        """Permite cargar una propuesta en memoria validada antes de reply()."""
        if proposal.request_hash and request and proposal.request_hash != request.digest:
            raise ValueError("la propuesta no coincide con el hash de la solicitud")
        self._staged_proposal = proposal
        self._staged_request = request

    def reply(self, payload: dict) -> dict:
        """Cumple el contrato de Provider de invoke.py."""
        if self._staged_proposal is None:
            raise RuntimeError(
                "AntigravityAssistedOperator en modo asistido requiere cargar una propuesta mediante import_proposal() o stage_proposal() antes de reply()"
            )
        prop = self._staged_proposal

        # Comprobar que el payload que se pasa a reply() coincide con el de la propuesta
        if digest(payload) != prop.payload_hash:
            raise ValueError("payload entregado a reply() no coincide con el payload autorizado de la propuesta")

        # Consumo atómico idempotente por misión si hay store
        if self.store:
            claimed = self.store.claim_mission(prop.mission_id, prop.request_hash, prop.payload_hash)
            if not claimed:
                raise RuntimeError(f"la misión {prop.mission_id} ya fue consumida; no se puede generar un nuevo borrador de la misma propuesta")

        return {
            "text": prop.text,
            "citations": prop.citations,
            "provider": self.identity,
            "proposal_id": prop.proposal_id,
            "mission_id": prop.mission_id,
            "mode": self.mode,
            "request_hash": prop.request_hash,
            "payload_hash": prop.payload_hash,
        }
