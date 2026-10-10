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
from plankit.circulation import (
    BackboneLink,
    CorridorBackbone,
    corridor_backbone,
    corridor_filter,
)
from plankit.conform import (
    CirculationReport,
    ConformanceReport,
    check_program,
    conform,
    validate_circulation,
)
from plankit.constraints import Constraint, program_constraints
from plankit.derive import (
    WallSegment,
    door_pairs,
    perimeter_spaces,
    space_adjacency,
    space_footprints,
    wall_segments,
)
from plankit.events import evaluate
from plankit.generate import generate, generate_many, propose_layout, select_best
from plankit.geometry import Vec
from plankit.graph import Graph
from plankit.hierarchy import (
    TOPOLOGIES,
    DwellingEnvelope,
    coarse_layout,
    dwelling_envelope,
    squarify_blocks,
    supernodes,
    two_step,
)
from plankit.operators import (
    add_room,
    layout_row,
    mirror_footprint,
    place_space,
    propose_magnet,
    remove_room,
    shape_for_area,
    split_footprint,
    squarify_rects,
)
from plankit.planar import Face, HalfEdge, PlanarSubdivision, Vertex
from plankit.program import (
    EDGE_KINDS,
    SPACE_ROLES,
    ProgramEdge,
    ProgramSpace,
    RoomProgram,
    dwelling_budget,
)
from plankit.quality import (
    adjacency_gaps,
    aspect_ratios,
    circulation_depth,
    escape_depth,
    facade_lengths,
    facade_ratio,
    fill_ratio,
    is_enfilade,
)
from plankit.store import Variant, VariantStore, make_variant
from plankit.svg import scrub_page, to_svg

__all__ = [
    # program
    "Graph",
    "RoomProgram",
    "ProgramSpace",
    "ProgramEdge",
    "dwelling_budget",
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
    "wall_segments",
    "WallSegment",
    # generatie
    "generate",
    "generate_many",
    "select_best",
    "propose_layout",
    "propose_magnet",
    "place_space",
    "shape_for_area",
    "squarify_rects",
    "split_footprint",
    "mirror_footprint",
    "add_room",
    "remove_room",
    "layout_row",
    # hiërarchie (two-step)
    "TOPOLOGIES",
    "DwellingEnvelope",
    "dwelling_envelope",
    "supernodes",
    "coarse_layout",
    "two_step",
    "squarify_blocks",
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
    "facade_ratio",
    "circulation_depth",
    "escape_depth",
    "is_enfilade",
    "fill_ratio",
    "adjacency_gaps",
    # observatie
    "evaluate",
    "Variant",
    "VariantStore",
    "make_variant",
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
    "corridor_backbone",
    "corridor_filter",
    "BackboneLink",
    "CorridorBackbone",
]
