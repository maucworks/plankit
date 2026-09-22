# This file was generated with the assistance of an AI coding tool.
"""Minimale 2D-geometriekern (plankit).

Alleen wat de skelet-laag nodig heeft: een 2D-punt. Segmenten en polygonen
komen uit shapely (optioneel) of als tupel-lijsten; plankit heeft geen 3D-kern.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vec:
    """2D-punt."""

    x: float
    y: float
