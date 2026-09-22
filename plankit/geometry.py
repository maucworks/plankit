# This file was generated with the assistance of an AI coding tool.
"""Minimale 2D-geometriekern (plankit).

Alleen wat de skelet-laag nodig heeft: een 2D-punt. Segmenten en polygonen komen
in M1 (half-edge/DCEL).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vec:
    """2D-punt; ``z`` is optioneel (default 0.0) voor compat met 3D-interfaces."""

    x: float
    y: float
    z: float = 0.0
