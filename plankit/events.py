# This file was generated with the assistance of an AI coding tool.
"""Evaluatie: bundel conformance (laag 1) en kwaliteit (laag 2) in één rapport."""

from __future__ import annotations

from dataclasses import asdict

from plankit.conform import conform
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram
from plankit.quality import (
    aspect_ratios,
    circulation_depth,
    escape_depth,
    facade_lengths,
    facade_ratio,
    is_enfilade,
)


def evaluate(
    sd: PlanarSubdivision,
    program: RoomProgram,
    boundary: list[tuple[float, float]] | None = None,
    min_widths: dict[str, float] | None = None,
) -> dict:
    """Bereken laag 1 (conformance) + laag 2 (kwaliteit) als één rapport."""
    cr = conform(sd, program, boundary=boundary, min_widths=min_widths)
    return {
        "conformance": asdict(cr),
        "quality": {
            "aspect_ratio": aspect_ratios(sd),
            "facade_length": facade_lengths(sd),
            "facade_ratio": facade_ratio(sd),
            "circulation_depth": circulation_depth(sd),
            "escape_depth": escape_depth(sd, program),
            "enfilade": is_enfilade(sd),
        },
    }
