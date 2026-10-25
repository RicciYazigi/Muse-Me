import tempfile
import time
from pathlib import Path
import pytest

from muse_env.project_memory import ProjectMemory
from muse_env.gate import TrajectorySensor
from muse_env.capabilities import propose_deliverable, execute_deliverable_action


def test_fuse_live_ab_connection_in_gate2():
    """F07: Verify Fuse A/B switch and trip behavior in Compuerta 2."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "fuse_test.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            doc_dir = Path(td) / "docs"
            doc_dir.mkdir()
            f = doc_dir / "doc.md"
            f.write_text("Contenido seguro para entregable.", encoding="utf-8")
            rev = mem.ingest_text("proj", str(doc_dir), "doc.md", scope="may_transfer")
            mid = mem.checkpoint("proj", "Generar entregable", {"doc.md": rev})
            prop = propose_deliverable(mem, mid, title="Reporte")
            draft_hash = prop["draft_sha256"]

            # Mode A: Fuse disabled (None) -> succeeds normally
            res_a = execute_deliverable_action(
                mem, mid, target_dir=td, filename="out_a.md",
                approved_draft_sha256=draft_hash, user_approved=True, fuse_sensor=None
            )
            assert res_a["readback_verified"] is True

            # Mode B: Fuse enabled with normal risk (0.01) -> succeeds
            mid_b = mem.checkpoint("proj", "Generar entregable 2", {"doc.md": rev})
            prop_b = propose_deliverable(mem, mid_b, title="Reporte 2")
            sensor = TrajectorySensor(threshold=0.04)
            res_b = execute_deliverable_action(
                mem, mid_b, target_dir=td, filename="out_b.md",
                approved_draft_sha256=prop_b["draft_sha256"], user_approved=True,
                fuse_sensor=sensor, risk_score=0.01, fuse_t=1.0
            )
            assert res_b["readback_verified"] is True

            # Mode C: Excessive risk pulses trip the fuse
            mid_c = mem.checkpoint("proj", "Generar entregable 3", {"doc.md": rev})
            prop_c = propose_deliverable(mem, mid_c, title="Reporte 3")
            # Feed progressive risk with strictly monotonic timestamps
            sensor.observe(0.95, effect="insert", t=2.0)
            sensor.observe(0.95, effect="insert", t=3.0)
            sensor.observe(0.95, effect="write", t=4.0)

            with pytest.raises(PermissionError, match="Fusible Temporal"):
                execute_deliverable_action(
                    mem, mid_c, target_dir=td, filename="out_c.md",
                    approved_draft_sha256=prop_c["draft_sha256"], user_approved=True,
                    fuse_sensor=sensor, risk_score=0.99, fuse_path="session", fuse_t=5.0
                )
        finally:
            mem.close()


def test_degrade_state_permits_read_and_blocks_write():
    """A3: In DEGRADE state (0.04 < effective <= 0.08), read is allowed, but write is strictly blocked."""
    with tempfile.TemporaryDirectory() as td:
        db_p = Path(td) / "fuse_degrade_test.sqlite"
        mem = ProjectMemory(str(db_p))
        try:
            doc_dir = Path(td) / "docs"
            doc_dir.mkdir()
            f = doc_dir / "doc.md"
            f.write_text("Evidencia segura para prueba DEGRADE.", encoding="utf-8")
            rev = mem.ingest_text("proj", str(doc_dir), "doc.md", scope="may_transfer")
            mid = mem.checkpoint("proj", "Mision degrade", {"doc.md": rev})
            prop = propose_deliverable(mem, mid, title="Reporte Degrade")

            from muse_env.gate import GatePolicy
            # Sensor configured with multi-tier policy (degrade=0.04, stop=0.08)
            sensor = TrajectorySensor(policy=GatePolicy(degrade_threshold=0.04, stop_threshold=0.08))

            # Pulse with score=0.83 at t=1.0:
            # dev = 0.83 - 0.60 = 0.23 -> dev^2 = 0.0529
            # For effect="read" (weight=0.8): effective = 0.0529 * 0.8 = 0.04232 -> in DEGRADE range (0.04 to 0.08)
            v_read = sensor.evaluate(score=0.83, t=1.0, effect="read")
            assert v_read.action == "DEGRADE", f"Expected DEGRADE, got {v_read.action}"
            assert v_read.allowed is True, "Read must be allowed in DEGRADE"

            # For effect="write" (weight=1.0): effective = 0.0529 * 1.0 = 0.0529 -> in DEGRADE range (0.04 to 0.08)
            # In DEGRADE, write MUST NOT be allowed!
            v_write = sensor.evaluate(score=0.0, t=1.01, effect="write")
            assert v_write.action == "DEGRADE", f"Expected DEGRADE, got {v_write.action}"
            assert v_write.allowed is False, "Write must be BLOCKED in DEGRADE state"

            # Executing deliverable action with sensor in DEGRADE state must raise PermissionError
            with pytest.raises(PermissionError, match="Compuerta 2 bloqueada por Fusible Temporal"):
                execute_deliverable_action(
                    mem, mid, target_dir=td, filename="out_degrade.md",
                    approved_draft_sha256=prop["draft_sha256"], user_approved=True,
                    fuse_sensor=sensor, risk_score=0.0, fuse_t=1.02
                )
        finally:
            mem.close()
