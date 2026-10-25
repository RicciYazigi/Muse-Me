"""Observed events preserve provenance, permission and identity across restarts."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import math
import time
from uuid import uuid4

EPISTEMIC = ("observed", "inferred", "verified", "user_confirmed", "superseded")
SCOPES = ("local-only", "may_transfer", "restricted")


@dataclass(frozen=True)
class ObservationEvent:
    kind: str
    application: str
    content: str = ""
    epistemic_status: str = "observed"
    permission_scope: str = "local-only"
    source_type: str = "simulated"
    ts: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"evt-{uuid4().hex}")

    def __post_init__(self):
        if self.epistemic_status not in EPISTEMIC:
            raise ValueError("estado epistemológico inválido")
        if self.permission_scope not in SCOPES:
            raise ValueError("alcance de permiso inválido")
        if not math.isfinite(float(self.ts)):
            raise ValueError("timestamp debe ser finito")
        if not self.event_id or not self.kind or not self.application:
            raise ValueError("identidad, tipo y aplicación son obligatorios")
        if not isinstance(self.content, str):
            raise ValueError("content debe ser texto")

    def to_dict(self):
        return asdict(self)
