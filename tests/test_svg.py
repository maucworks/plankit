# This file was generated with the assistance of an AI coding tool.
"""Tests voor SVG-rendering en scrubpagina (plankit.svg)."""

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.generate import generate
from plankit.store import make_variant
from plankit.svg import scrub_page, to_svg


def _two_room() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )


def test_to_svg_contains_faces_and_door():
    sd = generate(_two_room())
    svg = to_svg(sd)
    assert svg.count("<polygon") == len(sd.bounded_faces())
    assert "<line" in svg  # deur-edge


def test_scrub_page_embeds_frames():
    sd = generate(_two_room())
    v = make_variant(sd, _two_room(), step=0, label="generate")
    html = scrub_page([v])
    assert "FRAMES" in html
    assert '"step": 0' in html
    assert '"label": "generate"' in html
