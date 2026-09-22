# This file was generated with the assistance of an AI coding tool.
"""Tests voor serialisatie en event-log (plankit.events)."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.derive import door_pairs
from plankit.events import evaluate, read_events, record
from plankit.generate import generate
from plankit.planar import PlanarSubdivision


def _two_room() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )


def test_serialization_roundtrip():
    sd = generate(_two_room())
    sd2 = PlanarSubdivision.from_dict(sd.to_dict())
    assert len(sd2.bounded_faces()) == len(sd.bounded_faces())
    assert sorted(sd2.face_area(f) for f in sd2.bounded_faces()) == pytest.approx(
        sorted(sd.face_area(f) for f in sd.bounded_faces())
    )
    assert door_pairs(sd2) == door_pairs(sd)


def test_event_log_roundtrip(tmp_path):
    prog = _two_room()
    sd = generate(prog)
    log = str(tmp_path / "gen.jsonl")
    record(log, 0, "generate", sd, prog)
    record(log, 1, "revise", sd, prog)
    events = read_events(log)
    assert [e.step for e in events] == [0, 1]
    assert [e.op for e in events] == ["generate", "revise"]
    sd2 = PlanarSubdivision.from_dict(events[0].state)
    assert len(sd2.bounded_faces()) == 2


def test_evaluate_has_both_layers():
    sd = generate(_two_room())
    report = evaluate(sd, _two_room())
    assert "conformance" in report
    assert "quality" in report
    assert set(report["quality"]) == {"aspect_ratio", "facade_length", "circulation_depth", "enfilade"}
