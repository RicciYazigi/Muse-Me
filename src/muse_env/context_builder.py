"""Auditable candidate selection. Runtime revalidates against trusted observations."""
from __future__ import annotations
from .episodes import Episode, terms


def source_record(event):
    return {"source": event.event_id, "app": event.application,
            "status": event.epistemic_status, "content": event.content}


def provider_payload(package):
    """Exact outbound data: excluded metadata and local controls stay local."""
    def selected(record):
        return {key: record[key] for key in ("source", "status", "content")}
    return {"action": package["action"], "current_context": selected(package["current_context"]),
            "additional_context": [selected(item) for item in package["additional_context"]]}


class ContextBuilder:
    def __init__(self, max_additional=4, max_chars=16000):
        if max_additional < 0 or max_chars <= 0:
            raise ValueError("presupuesto de contexto inválido")
        self.max_additional, self.max_chars = max_additional, max_chars

    def build(self, *, action, target_application, current_content,
              episodes: list[Episode], target_is_external=True, current_source=None):
        events = {event.event_id: event for episode in episodes for event in episode.events}
        matches = [event for event in events.values()
                   if event.application == target_application and event.content == current_content
                   and (current_source is None or event.event_id == current_source)]
        if not matches:
            raise ValueError("el contexto actual requiere una observación con procedencia")
        current = max(matches, key=lambda event: event.ts)
        if current.permission_scope == "restricted" or (target_is_external and current.permission_scope != "may_transfer"):
            raise PermissionError("ventana actual no autorizada para este destino")
        if current.epistemic_status == "superseded":
            raise ValueError("el contexto actual está reemplazado")
        if len(current_content) > self.max_chars:
            raise ValueError("el contexto actual excede el presupuesto")
        query = terms(action) | terms(current_content)
        candidates, excluded = [], []
        for event in events.values():
            if event.event_id == current.event_id:
                continue
            reason = None
            if event.permission_scope == "restricted":
                reason = "restricted_no_transfer" if target_is_external else "restricted"
            elif target_is_external and event.permission_scope != "may_transfer":
                reason = "local_only_not_authorized_for_external_target"
            elif event.epistemic_status == "superseded":
                reason = "superseded"
            elif event.ts > current.ts:
                reason = "future_observation"
            shared = terms(event.content) & query
            if reason is None and not shared:
                reason = "not_relevant_to_current_action"
            if reason:
                excluded.append({"source": event.event_id, "app": event.application, "reason": reason})
            else:
                candidates.append((event, shared))
        candidates.sort(key=lambda item: (-len(item[1]), -item[0].ts, item[0].event_id))
        selected, used = [], len(current_content)
        for event, shared in candidates:
            if len(selected) >= self.max_additional or used + len(event.content) > self.max_chars:
                excluded.append({"source": event.event_id, "app": event.application, "reason": "context_budget"})
                continue
            selected.append({**source_record(event), "shared_terms": sorted(shared)})
            used += len(event.content)
        return {"action": action, "target_application": target_application,
                "target_is_external": target_is_external, "current_context": source_record(current),
                "additional_context": selected, "excluded_context": excluded, "requires_user_approval": True}
