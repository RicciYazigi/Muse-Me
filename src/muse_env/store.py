"""Local SQLite ledger. Hashes bind recorded content; they do not prove truth."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from .events import ObservationEvent


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class EventStore:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS observations(
            event_id TEXT PRIMARY KEY, ts REAL, kind TEXT, application TEXT,
            content TEXT, epistemic_status TEXT, permission_scope TEXT, source_type TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS interventions(
            seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payload TEXT,
            prev_hash TEXT, hash TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS drafts(
            draft_id TEXT PRIMARY KEY, bundle TEXT NOT NULL, state TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS missions(
            mission_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
            payload_hash TEXT NOT NULL, state TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS observation_provenance(
            event_id TEXT PRIMARY KEY, hwnd INTEGER, pid INTEGER, process_name TEXT,
            window_title TEXT, class_name TEXT, control_id TEXT, window_id TEXT,
            target_id TEXT, capture_allowed INTEGER, read_method TEXT, captured_at REAL)""")
        self.db.commit()

    def close(self):
        self.db.close()


    def _append(self, kind, payload):
        prev = self.db.execute("SELECT hash FROM interventions ORDER BY seq DESC LIMIT 1").fetchone()
        previous = prev[0] if prev else "GENESIS"
        hashed = digest({"kind": kind, "payload": payload, "prev": previous})
        self.db.execute("INSERT INTO interventions(kind,payload,prev_hash,hash) VALUES (?,?,?,?)",
                        (kind, canonical(payload), previous, hashed))
        return hashed

    def append_intervention(self, kind, payload):
        with self.db:
            return self._append(kind, payload)

    def add(self, event):
        with self.db:
            self.db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)", (
                event.event_id, event.ts, event.kind, event.application, event.content,
                event.epistemic_status, event.permission_scope, event.source_type))
            self._append("observation_recorded", {"observation": event.to_dict()})
        return event

    @staticmethod
    def _event(row):
        return ObservationEvent(event_id=row[0], ts=row[1], kind=row[2], application=row[3],
            content=row[4], epistemic_status=row[5], permission_scope=row[6], source_type=row[7])

    def get(self, event_id):
        row = self.db.execute("SELECT * FROM observations WHERE event_id=?", (event_id,)).fetchone()
        return self._event(row) if row else None

    def all(self):
        return [self._event(row) for row in self.db.execute("SELECT * FROM observations ORDER BY ts,event_id")]

    def save_provenance(self, provenance):
        with self.db:
            p = provenance if isinstance(provenance, dict) else provenance.to_dict()
            self.db.execute(
                "INSERT OR REPLACE INTO observation_provenance VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["event_id"], p["hwnd"], p["pid"], p["process_name"], p["window_title"],
                 p["class_name"], p["control_id"], p["window_id"], p["target_id"],
                 1 if p.get("capture_allowed", True) else 0, p["read_method"], p["captured_at"])
            )
            self._append("provenance_recorded", {"provenance": p})

    def get_provenance(self, event_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM observation_provenance WHERE event_id=?", (event_id,)).fetchone()
        if not row:
            return None
        return {
            "event_id": row[0], "hwnd": row[1], "pid": row[2], "process_name": row[3],
            "window_title": row[4], "class_name": row[5], "control_id": row[6], "window_id": row[7],
            "target_id": row[8], "capture_allowed": bool(row[9]), "read_method": row[10], "captured_at": row[11],
        }

    def save_draft(self, draft):

        with self.db:
            self.db.execute("INSERT INTO drafts VALUES (?,?,'ready')", (draft["draft_id"], canonical(draft)))
            self._append("draft_ready", {"draft": draft})

    def claim_draft(self, draft):
        """Single-use claim; failed attempts require a fresh draft and approval."""
        with self.db:
            result = self.db.execute("UPDATE drafts SET state='attempted' WHERE draft_id=? AND bundle=? AND state='ready'",
                                     (draft["draft_id"], canonical(draft)))
        return result.rowcount == 1

    def save_mission(self, mission_id, request_hash, payload_hash, state="exported"):
        with self.db:
            self.db.execute("INSERT INTO missions VALUES (?,?,?,?)",
                            (mission_id, request_hash, payload_hash, state))
            self._append("mission_registered", {"mission_id": mission_id, "request_hash": request_hash, "payload_hash": payload_hash, "state": state})

    def get_mission(self, mission_id):
        row = self.db.execute("SELECT mission_id, request_hash, payload_hash, state FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if not row:
            return None
        return {"mission_id": row[0], "request_hash": row[1], "payload_hash": row[2], "state": row[3]}

    def update_mission_state(self, mission_id, state):
        with self.db:
            self.db.execute("UPDATE missions SET state=? WHERE mission_id=?", (state, mission_id))
            self._append("mission_state_updated", {"mission_id": mission_id, "state": state})

    def claim_mission(self, mission_id, request_hash, payload_hash):
        """Single-use claim per mission execution. Prevents proposal replay across restarts."""
        with self.db:
            result = self.db.execute(
                "UPDATE missions SET state='consumed' WHERE mission_id=? AND request_hash=? AND payload_hash=? AND state IN ('exported', 'proposal_imported')",
                (mission_id, request_hash, payload_hash)
            )
            if result.rowcount == 1:
                self._append("mission_consumed", {"mission_id": mission_id, "request_hash": request_hash})
                return True
        return False

    def chain(self):
        return [{"seq": row[0], "kind": row[1], "payload": json.loads(row[2]),
                 "prev_hash": row[3], "hash": row[4]}
                for row in self.db.execute("SELECT * FROM interventions ORDER BY seq")]

    def verify_chain(self):
        previous = "GENESIS"
        try:
            chain = self.chain()
            for link in chain:
                if link["prev_hash"] != previous or digest({"kind": link["kind"], "payload": link["payload"], "prev": previous}) != link["hash"]:
                    return False
                previous = link["hash"]

            recorded = {link["payload"]["observation"]["event_id"]: link["payload"]["observation"]
                        for link in chain if link["kind"] == "observation_recorded"}
            if {event.event_id: event.to_dict() for event in self.all()} != recorded:
                return False

            # Verificación de correspondencia de procedencia contra el ledger:
            recorded_prov = {link["payload"]["provenance"]["event_id"]: link["payload"]["provenance"]
                             for link in chain if link["kind"] == "provenance_recorded"}

            table_rows = self.db.execute("SELECT * FROM observation_provenance ORDER BY captured_at, event_id").fetchall()
            table_prov = {}
            for row in table_rows:
                p = {
                    "event_id": row[0], "hwnd": row[1], "pid": row[2], "process_name": row[3],
                    "window_title": row[4], "class_name": row[5], "control_id": row[6], "window_id": row[7],
                    "target_id": row[8], "capture_allowed": bool(row[9]), "read_method": row[10], "captured_at": row[11],
                }
                table_prov[p["event_id"]] = p

            # 1. Cada registro en observation_provenance debe coincidir exactamente con el ledger criptográfico
            if table_prov != recorded_prov:
                return False

            # 2. Cada procedencia debe corresponder a un evento de observación registrado
            valid_event_ids = {event.event_id for event in self.all()}
            for event_id in table_prov:
                if event_id not in valid_event_ids:
                    return False

            return True
        except (ValueError, KeyError, TypeError):
            return False

