# This file was generated with the assistance of an AI coding tool.
"""Tests voor pure derivatie (plankit.derive) uit een PlanarSubdivision."""

import pytest

from plankit.derive import (
    door_pairs,
    perimeter_spaces,
    space_adjacency,
    space_footprints,
    wall_segments,
)
from plankit.planar import PlanarSubdivision


def _two_room():
    return PlanarSubdivision.from_faces(
        [
            [(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)],
            [(4.0, 0.0), (10.0, 0.0), (10.0, 6.0), (4.0, 6.0)],
        ]
    )


def test_space_adjacency_wall():
    g = space_adjacency(_two_room())
    assert g.has_edge("0", "1")
    assert g.edge_attrs("0", "1")["kind"] == "wall"


def test_perimeter_spaces():
    assert perimeter_spaces(_two_room()) == {"0", "1"}


def test_space_footprints_area():
    fp = space_footprints(_two_room())
    assert set(fp) == {"0", "1"}
    assert len(fp["0"]) == 4


def test_door_pairs_empty_then_door():
    sd = _two_room()
    assert door_pairs(sd) == []
    sd.mark_edge(0, 1, "door")
    assert door_pairs(sd) == [("0", "1")]


def test_single_room_no_adjacency():
    sd = PlanarSubdivision.from_faces([[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]])
    g = space_adjacency(sd)
    assert list(g.edges()) == []


def test_wall_segments_functions():
    from plankit import ProgramEdge, ProgramSpace, RoomProgram

    sd = PlanarSubdivision.from_faces(
        [
            [(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)],
            [(4.0, 0.0), (10.0, 0.0), (10.0, 6.0), (4.0, 6.0)],
            [(4.0, -4.0), (10.0, -4.0), (10.0, 0.0), (4.0, 0.0)],
        ]
    )
    sd.faces[0].label = "k"
    sd.faces[1].label = "w"
    sd.faces[2].label = "u"
    sd.mark_edge(0, 1, "door")
    prog = RoomProgram(
        nodes={
            "k": ProgramSpace(name="K"),
            "w": ProgramSpace(name="W"),
            "u": ProgramSpace(name="U"),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[
            ProgramEdge("k", "w", kind="door"),
            ProgramEdge("w", "u", kind="wall"),
            ProgramEdge("k", "buiten", kind="facade"),
        ],
    )
    segs = wall_segments(sd, prog)
    by_function: dict[str, list] = {}
    for s in segs:
        by_function.setdefault(s.function, []).append(s)
    assert set(by_function) == {"buitengevel", "doorgang", "scheidend"}
    doors = by_function["doorgang"]
    assert len(doors) == 1
    assert doors[0].edge == "k-w:door"
    assert doors[0].length == pytest.approx(6.0)
    assert any(s.edge == "k-buiten:facade" for s in by_function["buitengevel"])
    assert any(s.edge == "w-u:wall" for s in by_function["scheidend"])
    total = sum(s.length for s in segs)
    assert total == pytest.approx(40.0 + 12.0)  # omtrek unie + 2 gedeelde wanden


def test_wall_segments_without_program():
    sd = PlanarSubdivision.from_faces([[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]])
    segs = wall_segments(sd)
    assert segs and all(s.function == "buitengevel" for s in segs)
    assert all(s.edge is None for s in segs)
