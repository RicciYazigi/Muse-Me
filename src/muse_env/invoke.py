"""Two explicit stages: authorize transfer and prepare, then approve exact insertion.

Approval constructors belong to the trusted UI/operator, not to model tools.
P0 demonstrates these stages in code; it does not implement a live consent dialog.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass
from uuid import uuid4
from .context_builder import provider_payload
from .gate import checkpoint
from .store import digest


@dataclass(frozen=True)
class TransferApproval:
    package_hash: str
    payload_hash: str
    provider_id: str
    actor: str


@dataclass(frozen=True)
class InsertionApproval:
    draft_id: str
    draft_hash: str
    target_id: str
    actor: str


def approve_transfer(package, provider, *, actor):
    if not actor:
        raise ValueError("identificar al operador que autoriza")
    return TransferApproval(digest(package), digest(provider_payload(package)), provider.identity, actor)


def approve_insertion(draft, *, actor):
    if not actor:
        raise ValueError("identificar al operador que aprueba")
    return InsertionApproval(draft["draft_id"], digest(draft), draft["target_id"], actor)


class FakeSurface:
    """Controlled surface. A real adapter must implement stable identity and readback."""
    def __init__(self, name, *, is_external=True, target_id=None):
        self.name, self.is_external = name, is_external
        self.target_id = target_id or f"surface-{uuid4().hex}"
        self.inserted = []

    def insert(self, text):
        self.inserted.append(text)
        return True

    def verify_inserted(self, text):
        return bool(self.inserted and self.inserted[-1] == text)


def _sensor_blocks(sensor, score, t, effect, path):
    if sensor is None or not sensor.enabled:
        return False
    if score is None or t is None:
        raise ValueError("sensor activo requiere score y tiempo explícitos")
    return sensor.observe(score, effect=effect, t=t, path=path)


def prepare_reply(*, store, package, provider, surface, transfer_approval=None,
                  sensor=None, risk_score=None, t=None, session="session"):
    package = deepcopy(package)
    remote = provider.is_external
    ok, reason = checkpoint(package, store=store, transfer_required=remote or surface.is_external)
    if not ok:
        return {"status": "blocked", "reason": reason}
    if package["target_application"] != surface.name or package["target_is_external"] != surface.is_external:
        return {"status": "blocked", "reason": "destino_inconsistente"}
    outbound = provider_payload(package)
    expected = (digest(package), digest(outbound), provider.identity)
    if remote and (not isinstance(transfer_approval, TransferApproval) or not transfer_approval.actor or
        (transfer_approval.package_hash, transfer_approval.payload_hash, transfer_approval.provider_id) != expected):
        return {"status": "transfer_not_approved"}
    try:
        if _sensor_blocks(sensor, risk_score, t, "share" if remote else "read", session):
            store.append_intervention("blocked_sensor", {"phase": "prepare", "session": session})
            return {"status": "blocked", "reason": "trajectory_stop"}
    except (ValueError, TypeError, KeyError):
        return {"status": "blocked", "reason": "señal_inválida"}
    store.append_intervention("proposed", {"package": package, "payload": outbound,
        "provider_id": provider.identity, "target_id": surface.target_id})
    if remote:
        store.append_intervention("transfer_approved", asdict(transfer_approval))
    try:
        response = provider.reply(deepcopy(outbound))
        if not isinstance(response["text"], str) or not response["text"].strip():
            raise ValueError("borrador vacío")
        allowed = {item["source"] for item in [outbound["current_context"], *outbound["additional_context"]]}
        citations = response.get("citations", [])
        if not isinstance(citations, list) or any(citation not in allowed for citation in citations):
            raise ValueError("cita ajena al contexto autorizado")
        draft = {"draft_id": f"draft-{uuid4().hex}", "text": response["text"],
            "citations": citations, "provided_sources": sorted(allowed),
            "provider": provider.identity, "payload_hash": digest(outbound), "package": package,
            "target_id": surface.target_id, "target_application": surface.name,
            "target_is_external": surface.is_external}
        store.save_draft(draft)
    except Exception as error:
        store.append_intervention("provider_failed", {"error_type": type(error).__name__})
        return {"status": "provider_failed", "reason": type(error).__name__}
    return {"status": "draft_ready", "draft": draft}


def insert_reply(*, store, draft, surface, approval=None,
                 sensor=None, risk_score=None, t=None, session="session"):
    draft = deepcopy(draft)
    if not isinstance(approval, InsertionApproval) or not approval.actor:
        return {"status": "not_approved"}
    if (approval.draft_id, approval.draft_hash, approval.target_id) != (draft["draft_id"], digest(draft), surface.target_id):
        return {"status": "blocked", "reason": "aprobación_no_corresponde"}
    if (draft["target_id"], draft["target_application"], draft["target_is_external"]) != (surface.target_id, surface.name, surface.is_external):
        return {"status": "blocked", "reason": "destino_cambió"}
    if hasattr(surface, "is_target_active") and not surface.is_target_active():
        return {"status": "blocked", "reason": "destino_inactivo"}
    ok, reason = checkpoint(draft["package"], store=store, transfer_required=surface.is_external)
    if not ok:
        return {"status": "blocked", "reason": reason}
    try:
        if _sensor_blocks(sensor, risk_score, t, "insert", session):
            store.append_intervention("blocked_sensor", {"phase": "insert", "session": session})
            return {"status": "blocked", "reason": "trajectory_stop"}
    except (ValueError, TypeError, KeyError):
        return {"status": "blocked", "reason": "señal_inválida"}
    if not store.claim_draft(draft):
        return {"status": "blocked", "reason": "borrador_alterado_o_ya_intentado"}
    store.append_intervention("insertion_approved", asdict(approval))
    try:
        done = surface.insert(draft["text"]) and surface.verify_inserted(draft["text"])
    except Exception as error:
        done = False
        store.append_intervention("surface_error", {"error_type": type(error).__name__})
    store.append_intervention("inserted_confirmed" if done else "insert_failed",
        {"draft_id": draft["draft_id"], "draft_hash": digest(draft), "target_id": surface.target_id, "sent": False})
    return {"status": "inserted_not_sent" if done else "insert_failed", "draft": draft, "surface": surface.name}
