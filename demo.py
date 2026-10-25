"""Controlled P0: explicit stages, persistent events, optional STOP before insertion."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from muse_env.observer import SimulatedObserver, DEMO_SCRIPT
from muse_env.store import EventStore
from muse_env.episodes import build_episodes
from muse_env.context_builder import ContextBuilder, provider_payload
from muse_env.providers import LocalStubProvider
from muse_env.invoke import prepare_reply, insert_reply, approve_insertion, FakeSurface
from muse_env.gate import TrajectorySensor, policy_per_turn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = args.output_dir / "data"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "demo.sqlite"
    store = EventStore(db_path)
    before = len(store.all())
    events = list(SimulatedObserver(DEMO_SCRIPT).stream())
    for event in events:
        store.add(event)
    episodes = build_episodes(events)
    package = ContextBuilder().build(action="reply_with_muse", target_application="Chat externo",
        current_content=events[-1].content, current_source=events[-1].event_id,
        episodes=episodes, target_is_external=True)
    surface = FakeSurface("Chat externo")
    prepared = prepare_reply(store=store, package=package, provider=LocalStubProvider(), surface=surface)
    if prepared["status"] != "draft_ready":
        raise RuntimeError(prepared)
    # Demonstrated in script, not a claim that a person clicked an actual dialog.
    approval = approve_insertion(prepared["draft"], actor="demo-script (aprobación simulada)")
    result = insert_reply(store=store, draft=prepared["draft"], surface=surface, approval=approval)

    # Separate attempted action, now actually routed through the optional sensor.
    stop_surface = FakeSurface("Chat externo")
    stop_prepared = prepare_reply(store=store, package=package, provider=LocalStubProvider(), surface=stop_surface)
    sensor = TrajectorySensor()
    stop_index = None
    scores = [0.68, 0.72, 0.78, 0.66]
    for index, score in enumerate(scores):
        if sensor.observe(score, effect="read", t=float(index)):
            stop_index = index
            break
    stopped = insert_reply(store=store, draft=stop_prepared["draft"], surface=stop_surface,
        approval=approve_insertion(stop_prepared["draft"], actor="demo-script"),
        sensor=sensor, risk_score=0.0, t=4.0)
    chain_valid = store.verify_chain()
    chain = store.chain()
    store.close()
    reopened = EventStore(db_path)
    after = len(reopened.all())
    persisted = after == before + len(events) and reopened.verify_chain()
    reopened.close()
    output = {"format_version": 2, "mode": "simulated", "meta_calls": 0,
        "episodes": [episode.summary() for episode in episodes],
        "activity": [event.to_dict() for event in events],
        "package": package, "outbound_payload": provider_payload(package),
        "invoke": result, "inserted": surface.inserted,
        "ab": {"fixture_only": True, "per_turn_stop": next((i for i, score in enumerate(scores) if policy_per_turn(score)), None),
               "fuse_stop": stop_index, "attempt_status": stopped["status"], "blocked_insertions": len(stop_surface.inserted)},
        "persistence": {"before": before, "after": after, "reopened_ok": persisted},
        "chain_valid": chain_valid, "chain": chain}
    (args.output_dir / "resultado_demo.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = (result["status"] == "inserted_not_sent" and stopped["status"] == "blocked"
          and not stop_surface.inserted and persisted and chain_valid)
    print("P0 SIMULADO · proveedor local · llamadas Meta: 0")
    print("inserción:", result["status"], "| STOP:", stopped["status"])
    print("persistencia tras reabrir:", persisted, "| cadena:", chain_valid)
    print("OK" if ok else "FALLO")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
