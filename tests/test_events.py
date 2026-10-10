# This file was generated with the assistance of an AI coding tool.
"""Tests voor evaluatie (plankit.events)."""

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.events import evaluate
from plankit.generate import generate


def _two_room() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )


def test_evaluate_has_both_layers():
    sd = generate(_two_room())
    report = evaluate(sd, _two_room())
    assert "conformance" in report
    assert "quality" in report
    assert set(report["quality"]) == {
        "aspect_ratio",
        "facade_length",
        "facade_ratio",
        "circulation_depth",
        "escape_depth",
        "enfilade",
    }
