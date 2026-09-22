# This file was generated with the assistance of an AI coding tool.
"""Tests voor kwaliteitsmetrieken (plankit.quality)."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.generate import generate
from plankit.quality import aspect_ratios, circulation_depth, facade_lengths, is_enfilade


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
