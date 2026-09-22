# This file was generated with the assistance of an AI coding tool.
"""Tests voor pure derivatie (plankit.derive) uit een PlanarSubdivision."""

from plankit.derive import door_pairs, perimeter_spaces, space_adjacency, space_footprints
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
