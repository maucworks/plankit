# This file was generated with the assistance of an AI coding tool.
"""Tests voor kwaliteitsmetrieken (plankit.quality)."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.generate import generate
from plankit.planar import PlanarSubdivision
from plankit.quality import (
    adjacency_gaps,
    aspect_ratios,
    circulation_depth,
    escape_depth,
    facade_lengths,
    facade_ratio,
    fill_ratio,
    is_enfilade,
)


def _two_room() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )


def test_aspect_ratios():
    sd = generate(_two_room())  # k = 2x4, w = 5x4
    ratios = sorted(aspect_ratios(sd).values())
    assert ratios == pytest.approx([1.25, 2.0])


def test_facade_lengths():
    sd = generate(_two_room())  # k facade = 8, w facade = 14
    lengths = sorted(facade_lengths(sd).values())
    assert lengths == pytest.approx([8.0, 14.0])


def test_circulation_depth():
    sd = generate(_two_room())
    depth = circulation_depth(sd)
    assert set(depth.values()) == {0.0, 1.0}


def test_is_enfilade():
    sd = generate(_two_room())
    assert is_enfilade(sd) is True


def _label_by_x(sd, labels: dict) -> None:
    """Label faces naar x-positie van de centroid (kleinste x eerst)."""
    order = sorted(
        sd.bounded_faces(),
        key=lambda fid: sum(p[0] for p in sd.face_vertices(fid)),
    )
    for fid, label in zip(order, labels):
        sd.faces[fid].label = label


def test_fill_ratio_full_and_half():
    sd = PlanarSubdivision.from_faces(
        [[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]]
    )
    full = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    assert fill_ratio(sd, full) == pytest.approx(1.0)
    half = [(0.0, 0.0), (10.0, 0.0), (10.0, 12.0), (0.0, 12.0)]
    assert fill_ratio(sd, half) == pytest.approx(0.5)


def test_fill_ratio_rejects_empty_boundary():
    sd = PlanarSubdivision.from_faces(
        [[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]]
    )
    with pytest.raises(ValueError):
        fill_ratio(sd, [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)])


def test_adjacency_gaps_touching_zero():
    sd = generate(_two_room())
    assert adjacency_gaps(sd, _two_room()) == {("k", "w"): 0.0}


def test_adjacency_gaps_separated_positive():
    sd = PlanarSubdivision.from_faces(
        [
            [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)],
            [(10.0, 0.0), (14.0, 0.0), (14.0, 3.0), (10.0, 3.0)],
        ]
    )
    _label_by_x(sd, ["k", "w"])
    gaps = adjacency_gaps(sd, _two_room())
    assert gaps == {("k", "w"): pytest.approx(6.0)}


def test_adjacency_gaps_skips_soft_and_unplaced():
    sd = generate(_two_room())
    prog = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
            "z": ProgramSpace(name="1.03", area_min=5),
        },
        edges=[
            ProgramEdge("k", "w", kind="wall", required=False),
            ProgramEdge("k", "z", kind="door"),
        ],
    )
    assert adjacency_gaps(sd, prog) == {}


def test_facade_ratio_strip():
    sd = generate(_two_room())  # k = 2x4 (gevel 8), w = 5x4 (gevel 14)
    assert facade_ratio(sd) == pytest.approx(22.0 / 28.0)


def test_escape_depth_from_core():
    prog = RoomProgram(
        nodes={
            "kern": ProgramSpace(name="Kern", core=True),
            "g": ProgramSpace(name="Gang"),
            "k": ProgramSpace(name="Kamer"),
        },
        edges=[
            ProgramEdge("kern", "g", kind="door"),
            ProgramEdge("g", "k", kind="door"),
        ],
    )
    proposal = {
        "kern": [(0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)],
        "g": [(3.0, 0.0), (6.0, 0.0), (6.0, 3.0), (3.0, 3.0)],
        "k": [(6.0, 0.0), (9.0, 0.0), (9.0, 3.0), (6.0, 3.0)],
    }
    sd = generate(prog, proposal=proposal)
    assert escape_depth(sd, prog) == {"kern": 0.0, "g": 1.0, "k": 2.0}


def test_escape_depth_without_core_empty():
    sd = generate(_two_room())
    assert escape_depth(sd, _two_room()) == {}
