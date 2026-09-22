# This file was generated with the assistance of an AI coding tool.
"""plankit — skelet-generatie (PvE → plattegrond), IFC-vrij.

Het fundament: een PvE als getypeerde graaf (:class:`RoomProgram`), een
half-edge/DCEL-skelet (:class:`PlanarSubdivision`), generatie
(:func:`generate`), conformance + kwaliteit (:mod:`plankit.conform`,
:mod:`plankit.quality`) en een event-log met browser-scrub (:mod:`plankit.svg`).
Alles draait op stdlib; ``networkx`` en ``shapely`` zijn optioneel.
"""

from plankit.analysis import (
    D_VALUES,
    SpaceSyntax,
    analyze,
    choice,
    connectivity,
    control,
    diamond_value,
    integration,
    mean_depth,
    relative_asymmetry,
    total_depth,
)
from plankit.conform import (
    CirculationReport,
    ConformanceReport,
    check_program,
    conform,
    validate_circulation,
)
from plankit.constraints import Constraint, program_constraints
from plankit.derive import door_pairs, perimeter_spaces, space_adjacency, space_footprints
from plankit.events import Event, append_event, evaluate, read_events, record
from plankit.generate import generate, propose_layout
from plankit.geometry import Vec
from plankit.graph import Graph
from plankit.operators import (
    add_room,
    layout_row,
    mirror_footprint,
    place_space,
    remove_room,
    split_footprint,
)
from plankit.planar import Face, HalfEdge, PlanarSubdivision, Vertex
from plankit.program import EDGE_KINDS, SPACE_ROLES, ProgramEdge, ProgramSpace, RoomProgram
from plankit.quality import aspect_ratios, circulation_depth, facade_lengths, is_enfilade
from plankit.svg import scrub_page, to_svg

__all__ = [
    # program
    "Graph",
    "RoomProgram",
    "ProgramSpace",
    "ProgramEdge",
    "EDGE_KINDS",
    "SPACE_ROLES",
    # geometrie
    "Vec",
    # skelet (DCEL)
    "PlanarSubdivision",
    "Vertex",
    "HalfEdge",
    "Face",
    # derivatie
    "space_adjacency",
    "perimeter_spaces",
    "space_footprints",
    "door_pairs",
    # generatie
    "generate",
    "propose_layout",
    "place_space",
    "split_footprint",
    "mirror_footprint",
    "add_room",
    "remove_room",
    "layout_row",
    # constraints
    "Constraint",
    "program_constraints",
    # conformance (laag 1)
    "conform",
    "ConformanceReport",
    "check_program",
    "validate_circulation",
    "CirculationReport",
    # kwaliteit (laag 2)
    "aspect_ratios",
    "facade_lengths",
    "circulation_depth",
    "is_enfilade",
    # observatie
    "Event",
    "append_event",
    "read_events",
    "evaluate",
    "record",
    "to_svg",
    "scrub_page",
    # analyse (space syntax)
    "D_VALUES",
    "SpaceSyntax",
    "analyze",
    "total_depth",
    "mean_depth",
    "relative_asymmetry",
    "diamond_value",
    "integration",
    "connectivity",
    "control",
    "choice",
]
