# This file was generated with the assistance of an AI coding tool.
"""Tests voor conformance (plankit.conform)."""

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.conform import check_program, conform, validate_circulation
from plankit.generate import generate
from plankit.planar import PlanarSubdivision


def _two_room() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8, area_max=15),
            "w": ProgramSpace(name="1.02", area_min=20),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[
            ProgramEdge("k", "buiten", kind="facade"),
            ProgramEdge("k", "w", kind="door"),
        ],
    )


def test_conform_satisfied():
    sd = generate(_two_room())
    r = conform(sd, _two_room())
    assert r.ok
    assert not r.violated
    assert not r.missing
    assert "space:k" in r.satisfied
    assert "space:w" in r.satisfied
    assert "edge:k-w:door" in r.satisfied
    assert "edge:k-buiten:facade" in r.satisfied


def test_conform_missing():
    sd = PlanarSubdivision.from_faces([[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]])
    sd.faces[0].label = "k"
    r = conform(sd, _two_room())
    assert "space:w" in r.missing
    assert not r.ok


def test_conform_area_violation():
    prog = RoomProgram(nodes={"k": ProgramSpace(name="1.01", area_min=100)}, edges=[])
    sd = PlanarSubdivision.from_faces([[(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)]])
    sd.faces[0].label = "k"
    r = conform(sd, prog)
    assert any("area<100" in v for v in r.violated)
    assert not r.ok


def test_check_program_unknown_ref_and_isolated():
    prog = RoomProgram(
        nodes={"a": ProgramSpace(), "b": ProgramSpace()},
        edges=[ProgramEdge("a", "zzz", kind="wall")],
    )
    issues = check_program(prog)
    assert any("zzz" in i for i in issues)
    assert any("geïsoleerde knoop 'b'" in i for i in issues)


def test_validate_circulation_reachable():
    prog = RoomProgram(
        nodes={
            "buiten": ProgramSpace(name="buiten", exterior=True),
            "k": ProgramSpace(name="1.01"),
            "w": ProgramSpace(name="1.02"),
        },
        edges=[
            ProgramEdge("buiten", "k", kind="door"),
            ProgramEdge("k", "w", kind="door"),
        ],
    )
    r = validate_circulation(prog)
    assert r.ok
    assert not r.unreachable


def test_validate_circulation_unreachable():
    prog = RoomProgram(
        nodes={
            "buiten": ProgramSpace(name="buiten", exterior=True),
            "k": ProgramSpace(name="1.01"),
            "w": ProgramSpace(name="1.02"),
        },
        edges=[ProgramEdge("k", "w", kind="door")],  # geen entree-deur
    )
    r = validate_circulation(prog)
    assert not r.ok
    assert "k" in r.unreachable
