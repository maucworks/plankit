# This file was generated with the assistance of an AI coding tool.
"""Evaluatie: bundel conformance (laag 1) en kwaliteit (laag 2) in één rapport."""

from __future__ import annotations

from dataclasses import asdict

from plankit.conform import conform
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram
from plankit.quality import aspect_ratios, circulation_depth, facade_lengths, is_enfilade


def evaluate(sd: PlanarSubdivision, program: RoomProgram) -> dict:
    """Bereken laag 1 (conformance) + laag 2 (kwaliteit) als één rapport."""
    cr = conform(sd, program)
    return {
        "conformance": asdict(cr),
        "quality": {
            "aspect_ratio": aspect_ratios(sd),
            "facade_length": facade_lengths(sd),
            "circulation_depth": circulation_depth(sd),
            "enfilade": is_enfilade(sd),
        },
    }
