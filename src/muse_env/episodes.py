# -*- coding: utf-8 -*-
"""Episodios por reglas aburridas y auditables (MVP): solape temporal + términos compartidos.
Toda relación nace 'inferred'; solo el usuario la promueve a 'user_confirmed'. Nada de ML propio v0."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .events import ObservationEvent

STOP = set("el la de en y un una con por para que los las del se es su al lo como más o a e".split())
def terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-záéíóúñ0-9_]{3,}", text.lower()) if w not in STOP}

@dataclass
class Episode:
    episode_id: str
    events: list[ObservationEvent] = field(default_factory=list)
    relation_status: str = "inferred"
    @property
    def applications(self): return sorted({e.application for e in self.events})
    @property
    def vocabulary(self) -> set[str]:
        v: set[str] = set()
        for e in self.events: v |= terms(e.content)
        return v
    def summary(self):
        return {"episode": self.episode_id, "apps": self.applications,
                "relation_status": self.relation_status, "events": [e.event_id for e in self.events]}

def build_episodes(events: list[ObservationEvent], window_s: float = 900.0, min_shared: int = 2) -> list[Episode]:
    """Agrupa secuencialmente: un evento entra al episodio abierto si comparte >=min_shared
    términos con él o está dentro de la ventana temporal inmediata; si no, abre otro."""
    if window_s < 0 or min_shared < 1:
        raise ValueError("ventana temporal y solape inválidos")
    episodes: list[Episode] = []
    for ev in sorted(events, key=lambda event: (event.ts, event.event_id)):
        if ev.kind == "window_focus" and not ev.content: continue
        placed = False
        if episodes:
            cur = episodes[-1]
            shared = terms(ev.content) & cur.vocabulary
            gap = ev.ts - cur.events[-1].ts
            if gap <= window_s and (len(shared) >= min_shared or gap <= 5.0):
                cur.events.append(ev); placed = True
        if not placed:
            episodes.append(Episode(episode_id=f"ep-{len(episodes)+1:02d}", events=[ev]))
    return episodes
