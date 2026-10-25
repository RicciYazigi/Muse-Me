"""Operator contract: explicit data structures for mission request and operator proposals.

Defines the boundary between the host environment and the reasoning operator (Antigravity / Muse).
The operator NEVER grants permissions or approves its own proposals.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import time
from uuid import uuid4

VALID_MODES = ("asistido", "automatico", "simulado")


def canonical_json(value: dict | list) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def sha256_digest(value: dict | list) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MissionRequest:
    mission_id: str
    task: str
    action: str
    package_hash: str
    payload_hash: str
    target_application: str
    target_id: str
    allowed_sources: list[str]
    outbound_payload: dict
    operator_target: str = "antigravity"
    mode: str = "asistido"
    ts: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.mission_id or not self.task or not self.action:
            raise ValueError("identificadores de misión, tarea y acción son obligatorios")
        if self.mode not in VALID_MODES:
            raise ValueError(f"modo inválido: {self.mode}")
        if not math.isfinite(self.ts):
            raise ValueError("timestamp de solicitud debe ser finito")
        if not isinstance(self.allowed_sources, list):
            raise ValueError("allowed_sources debe ser una lista")
        if not isinstance(self.outbound_payload, dict):
            raise ValueError("outbound_payload debe ser un diccionario")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())


@dataclass(frozen=True)
class OperatorProposal:
    proposal_id: str
    mission_id: str
    request_hash: str
    payload_hash: str
    text: str
    citations: list[str]
    operator_identity: str
    mode: str = "asistido"
    actions_requested: list[str] = field(default_factory=list)
    status: str = "proposal_ready"
    ts: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.proposal_id or not self.mission_id:
            raise ValueError("identificadores de propuesta y misión son obligatorios")
        if not self.request_hash or not self.payload_hash:
            raise ValueError("request_hash y payload_hash son obligatorios para vincular la propuesta a la solicitud exacta")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("la propuesta de texto no puede estar vacía")
        if not isinstance(self.citations, list):
            raise ValueError("citations debe ser una lista")
        if self.mode not in VALID_MODES:
            raise ValueError(f"modo inválido: {self.mode}")
        if not math.isfinite(self.ts):
            raise ValueError("timestamp de propuesta debe ser finito")

    def validate_citations(self, allowed_sources: set[str] | list[str]) -> bool:
        allowed = set(allowed_sources)
        return all(citation in allowed for citation in self.citations)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())
