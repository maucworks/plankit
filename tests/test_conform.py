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
    sd = PlanarSubdivision.from_faces(
        [[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]]
    )
    sd.faces[0].label = "k"
    r = conform(sd, _two_room())
    assert "space:w" in r.missing
    assert not r.ok


def test_conform_area_violation():
    prog = RoomProgram(nodes={"k": ProgramSpace(name="1.01", area_min=100)}, edges=[])
    sd = PlanarSubdivision.from_faces(
        [[(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)]]
    )
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


def test_check_program_two_entrances_one_component():
    prog = RoomProgram(
        nodes={
            "h1": ProgramSpace(name="Hal 1", entrance=True),
            "h2": ProgramSpace(name="Hal 2", entrance=True),
        },
        edges=[ProgramEdge("h1", "h2", kind="door")],
    )
    issues = check_program(prog)
    assert any("meerdere entrances" in i and "h1" in i and "h2" in i for i in issues)


def test_check_program_two_entrances_separate_components_ok():
    prog = RoomProgram(
        nodes={
            "h1": ProgramSpace(name="Hal 1", entrance=True),
            "k1": ProgramSpace(name="Keuken 1"),
            "h2": ProgramSpace(name="Hal 2", entrance=True),
            "k2": ProgramSpace(name="Keuken 2"),
        },
        edges=[
            ProgramEdge("h1", "k1", kind="door"),
            ProgramEdge("h2", "k2", kind="door"),
        ],
    )
    issues = check_program(prog)
    assert not any("meerdere entrances" in i for i in issues)


def test_check_program_two_entrances_same_dwelling():
    prog = RoomProgram(
        nodes={
            "h1": ProgramSpace(name="Hal 1", entrance=True, group="A1"),
            "h2": ProgramSpace(name="Hal 2", entrance=True, group="A1"),
        },
        edges=[ProgramEdge("h1", "h2", kind="door")],
    )
    issues = check_program(prog)
    assert any("meerdere entrances" in i and "A1" in i for i in issues)


def test_check_program_entrances_across_dwellings_ok():
    prog = RoomProgram(
        nodes={
            "h1": ProgramSpace(name="Hal 1", entrance=True, group="A1"),
            "k1": ProgramSpace(name="Keuken 1", group="A1"),
            "h2": ProgramSpace(name="Hal 2", entrance=True, group="A2"),
            "k2": ProgramSpace(name="Keuken 2", group="A2"),
        },
        edges=[
            ProgramEdge("h1", "k1", kind="door"),
            ProgramEdge("h2", "k2", kind="door"),
            ProgramEdge("k1", "k2", kind="wall"),
        ],
    )
    issues = check_program(prog)
    assert not any("meerdere entrances" in i for i in issues)


def test_validate_circulation_starts_at_entrance():
    prog = RoomProgram(
        nodes={
            "h": ProgramSpace(name="Hal", entrance=True),
            "k": ProgramSpace(name="Keuken"),
        },
        edges=[ProgramEdge("h", "k", kind="door")],
    )
    r = validate_circulation(prog)
    assert r.root == "h"
    assert r.ok


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


def _separated_rooms() -> tuple:
    from plankit.planar import PlanarSubdivision

    sd = PlanarSubdivision.from_faces(
        [
            [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)],
            [(10.0, 0.0), (14.0, 0.0), (14.0, 3.0), (10.0, 3.0)],
        ]
    )
    order = sorted(
        sd.bounded_faces(),
        key=lambda fid: sum(p[0] for p in sd.face_vertices(fid)),
    )
    for fid, label in zip(order, ["k", "w"]):
        sd.faces[fid].label = label
    prog = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=12),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )
    return sd, prog


def test_conform_missing_adj_reported():
    sd, prog = _separated_rooms()
    r = conform(sd, prog)
    assert not r.ok
    assert r.missing_adj == {"k": ["w"], "w": ["k"]}


def test_conform_missing_adj_empty_when_ok():
    r = conform(generate(_two_room()), _two_room())
    assert r.ok
    assert r.missing_adj == {}


def test_conform_missing_adj_skips_unplaced():
    sd = PlanarSubdivision.from_faces(
        [[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]]
    )
    sd.faces[0].label = "k"
    prog = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=12),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )
    r = conform(sd, prog)
    assert "space:w" in r.missing
    assert r.missing_adj == {}


def _bounded_two_room():
    prog = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )
    sd = generate(prog)
    return sd, prog


def test_conform_boundary_inside_ok():
    sd, prog = _bounded_two_room()
    boundary = [(-5.0, -5.0), (30.0, -5.0), (30.0, 15.0), (-5.0, 15.0)]
    r = conform(sd, prog, boundary=boundary)
    assert r.ok


def test_conform_boundary_outside_violated():
    sd, prog = _bounded_two_room()
    boundary = [(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)]
    r = conform(sd, prog, boundary=boundary)
    assert not r.ok
    assert any("buiten-outline" in v for v in r.violated)


def test_conform_min_widths_pass_and_fail():
    sd, prog = _bounded_two_room()  # rij: k is 2,0 breed (8 m² bij diepte 4,0)
    r = conform(sd, prog, min_widths={"k": 2.0, "w": 2.1})
    assert r.ok
    r2 = conform(sd, prog, min_widths={"k": 2.1})
    assert any("breedte<2.1" in v for v in r2.violated)
    assert not r2.ok
