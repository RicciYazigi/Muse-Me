"""Authorization is mandatory; an optional temporal sensor can only restrict."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .context_builder import source_record
from ._fusible_vendor import Fuse

EFFECT_W = {"observe": 0.0, "read": 0.8, "write": 1.0, "insert": 1.2, "share": 1.5}
RANK = {"GO": 0, "DEGRADE": 1, "STOP": 2}


@dataclass(frozen=True)
class GatePolicy:
    """Multi-tier containment policy (adapted from FuseGate)."""
    degrade_threshold: float = 0.04
    stop_threshold: float = 0.08
    theta: float = 0.60
    tau: float = 50.0


@dataclass(frozen=True)
class Verdict:
    action: str  # "GO" | "DEGRADE" | "STOP"
    allowed: bool
    state: float
    effective_state: float
    session: str


def checkpoint(package, *, store, transfer_required):
    if not store.verify_chain():
        return False, "registro_alterado"
    try:
        if package["action"] != "reply_with_muse":
            return False, "acción_no_admitida"
        records = [package["current_context"], *package["additional_context"]]
        seen = set()
        for record in records:
            source = store.get(record["source"])
            if source is None or source.event_id in seen:
                return False, "fuente_ausente_o_duplicada"
            seen.add(source.event_id)
            if any(record.get(key) != value for key, value in source_record(source).items()):
                return False, "contenido_o_procedencia_alterados"
            if source.permission_scope == "restricted" or source.epistemic_status == "superseded":
                return False, "fuente_restringida_o_reemplazada"
            if transfer_required and source.permission_scope != "may_transfer":
                return False, "transferencia_no_autorizada"
        if package["current_context"]["app"] != package["target_application"]:
            return False, "ventana_actual_inconsistente"
    except (KeyError, TypeError, ValueError):
        return False, "paquete_malformado"
    return True, "ok"


class TrajectorySensor:
    """Experimental risk signals are supplied by the caller, never invented here.
    Preserves exact original stop behavior while adding rich multi-tier Verdict evaluation.
    """
    def __init__(self, threshold=0.04):
        self.fuse = Fuse(statistic="i2t", threshold=threshold, theta=0.60, tau=50.0, reset_on_trip=False)
        self.threshold = threshold
        self.enabled = True
        self._stopped = set()

    def observe(self, score, effect, t, path="session"):
        if not self.enabled:
            return False
        if path in self._stopped:
            return True
        trip = self.fuse.observe(score, t=t, path=path, weight=EFFECT_W[effect])
        if trip is not None:
            self._stopped.add(path)
        return trip is not None

    def evaluate(self, *, score: float, t: float, effect: str, session: str = "session") -> Verdict:
        """Evaluate structured Verdict (GO / DEGRADE / STOP) based on accumulated thermal state."""
        if not self.enabled:
            return Verdict("GO", True, 0.0, 0.0, session)
        stopped = self.observe(score, effect, t, path=session)
        state = self.fuse.value(session)
        effective = state * EFFECT_W[effect]
        action = "STOP" if stopped else ("DEGRADE" if effective > self.threshold else "GO")
        allowed = not stopped
        return Verdict(action, allowed, state, effective, session)

    def reset(self, path="session"):
        self._stopped.discard(path)
        self.fuse.reset(path)


def policy_per_turn(score):
    return score > 0.85
