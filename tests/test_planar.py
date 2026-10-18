# This file was generated with the assistance of an AI coding tool.
"""Tests voor de half-edge/DCEL (plankit.planar)."""

import pytest

from plankit.planar import PlanarSubdivision


def _two_room_faces():
    return [
        [(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)],
        [(4.0, 0.0), (10.0, 0.0), (10.0, 6.0), (4.0, 6.0)],
    ]


def _two_room_segments():
    return [
        ((0.0, 0.0), (10.0, 0.0)),
        ((10.0, 0.0), (10.0, 6.0)),
        ((10.0, 6.0), (0.0, 6.0)),
        ((0.0, 6.0), (0.0, 0.0)),
        ((4.0, 0.0), (4.0, 6.0)),
    ]


def test_twin_involution():
    sd = PlanarSubdivision.from_faces(_two_room_faces())
    for he_id, he in enumerate(sd.half_edges):
        assert sd.half_edges[he.twin].twin == he_id


def test_next_cycles_close_faces():
    sd = PlanarSubdivision.from_faces(_two_room_faces())
    for face_id in range(len(sd.faces)):
        start = sd.faces[face_id].half_edge
        he = start
        count = 0
        while True:
            assert sd.half_edges[he].face == face_id
            he = sd.half_edges[he].next
            count += 1
            if he == start:
                break
            assert count < 100
        assert count >= 3


def test_from_faces_two_rooms():
    sd = PlanarSubdivision.from_faces(_two_room_faces())
    assert len(sd.bounded_faces()) == 2
    assert len(sd.faces) == 3  # 2 begrensd + exterior
    assert sorted(sd.face_area(f) for f in sd.bounded_faces()) == pytest.approx(
        [24.0, 36.0]
    )
    assert sd.shared_edge(0, 1) is not None


def test_single_room_perimeter():
    sd = PlanarSubdivision.from_faces(
        [[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]]
    )
    assert sd.bounded_faces() == [0]
    assert sd.perimeter_faces() == {0}
    assert sd.face_area(0) == pytest.approx(60.0)


def test_centerline_two_rooms():
    pytest.importorskip("shapely")
    sd = PlanarSubdivision.from_centerlines(_two_room_segments())
    assert len(sd.bounded_faces()) == 2
    assert sum(sd.face_area(f) for f in sd.bounded_faces()) == pytest.approx(60.0)


def test_centerline_t_junction():
    pytest.importorskip("shapely")
    segs = [
        ((0.0, 0.0), (10.0, 0.0)),
        ((10.0, 0.0), (10.0, 6.0)),
        ((10.0, 6.0), (0.0, 6.0)),
        ((0.0, 6.0), (0.0, 0.0)),
        ((4.0, 0.0), (4.0, 4.0)),
        ((4.0, 4.0), (10.0, 4.0)),
    ]
    sd = PlanarSubdivision.from_centerlines(segs)
    assert len(sd.bounded_faces()) == 2
    assert sum(sd.face_area(f) for f in sd.bounded_faces()) == pytest.approx(60.0)


def test_mark_edge_door():
    sd = PlanarSubdivision.from_faces(_two_room_faces())
    sd.mark_edge(0, 1, "door")
    he = sd.shared_edge(0, 1)
    assert he is not None
    assert sd.half_edges[he].kind == "door"
    assert sd.half_edges[sd.half_edges[he].twin].kind == "door"


def test_mark_edge_rejects_no_shared():
    sd = PlanarSubdivision.from_faces(_two_room_faces())
    with pytest.raises(ValueError):
        sd.mark_edge(0, 0, "door")
