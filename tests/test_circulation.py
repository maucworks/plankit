# This file was generated with the assistance of an AI coding tool.
"""Tests voor gang-backbone (plankit.circulation)."""

from plankit.circulation import corridor_backbone, corridor_filter
from plankit.planar import PlanarSubdivision


def _chain3():
    return PlanarSubdivision.from_faces(
        [
            [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)],
            [(4.0, 0.0), (8.0, 0.0), (8.0, 4.0), (4.0, 4.0)],
            [(8.0, 0.0), (12.0, 0.0), (12.0, 4.0), (8.0, 4.0)],
        ]
    )


def test_backbone_root_is_hub():
    bb = corridor_backbone(_chain3())
    assert bb.root == 1
    assert sorted([(link.a, link.b) for link in bb.links]) == [(1, 0), (1, 2)]
    assert all(link.length == 4.0 for link in bb.links)


def test_backbone_explicit_root():
    bb = corridor_backbone(_chain3(), root=0)
    assert bb.root == 0
    assert sorted([(link.a, link.b) for link in bb.links]) == [(0, 1), (1, 2)]


def test_backbone_single_room_empty():
    sd = PlanarSubdivision.from_faces([[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]])
    bb = corridor_backbone(sd)
    assert bb.links == []


def test_backbone_deterministic():
    assert corridor_backbone(_chain3()).links == corridor_backbone(_chain3()).links


def test_filter_accepts_and_rejects():
    bb = corridor_backbone(_chain3())
    ok, fraction = corridor_filter(_chain3(), bb)
    assert ok and fraction == 8.0 * 1.2 / 48.0
    ok2, _ = corridor_filter(_chain3(), bb, max_fraction=0.1)
    assert not ok2
    ok3, _ = corridor_filter(_chain3(), bb, min_length=5.0)
    assert not ok3
