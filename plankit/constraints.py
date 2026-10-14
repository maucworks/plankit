# This file was generated with the assistance of an AI coding tool.
"""Groeibare constraint-laag: declaratieve predicaten op een skelet.

v1 kent alleen de constraints die direct uit het PvE volgen (oppervlakte,
getypeerde kanten). Vorm-constraints (max breedte, entree-locatie) komen later
als nieuwe :class:`Constraint`-typen.
"""

from __future__ import annotations

from dataclasses import dataclass

from plankit.program import RoomProgram


@dataclass
class Constraint:
    kind: str  # "area" | "edge"
    a: str | None = None  # ruimte-key (area) of edge-a (edge)
    b: str | None = None  # edge-b (edge)
    edge_kind: str | None = None  # "door" | "forbidden" | "facade" | "wall"
    area_min: float | None = None
    area_max: float | None = None


def program_constraints(program: RoomProgram) -> list[Constraint]:
    """Vertaal een PvE naar declaratieve constraints (exterieure knopen overgeslagen)."""
    cs: list[Constraint] = []
    for key, space in program.nodes.items():
        if space.exterior:
            continue
        if space.area_min is not None or space.area_max is not None:
            cs.append(
                Constraint(
                    kind="area", a=key, area_min=space.area_min, area_max=space.area_max
                )
            )
    for edge in program.edges:
        cs.append(Constraint(kind="edge", a=edge.a, b=edge.b, edge_kind=edge.kind))
    return cs
