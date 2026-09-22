# This file was generated with the assistance of an AI coding tool.
"""Pure derivatie: ruimten en relaties uit een :class:`PlanarSubdivision`.

De tegenhanger van ``ifckit.spatial.derive``, maar IFC-vrij: de "gerealiseerde
graaf" is hier het skelet zelf.
"""

from __future__ import annotations

from plankit.graph import Graph
from plankit.planar import PlanarSubdivision


def space_footprints(sd: PlanarSubdivision) -> dict[str, list[tuple[float, float]]]:
    """Return begrensde faces als polygons, gekeyed op ``str(face_id)``."""
    return {str(fid): sd.face_vertices(fid) for fid in sd.bounded_faces()}


def space_adjacency(sd: PlanarSubdivision) -> Graph:
    """Return de duale graaf: knopen = ruimten, kanten = gedeelde wand/deur."""
    g = Graph()
    ext = sd.exterior_face()
    for fid in sd.bounded_faces():
        g.add_node(str(fid))
    seen: set[tuple[int, int]] = set()
    for he in sd.half_edges:
        if he.face == ext:
            continue
        twin_face = sd.half_edges[he.twin].face
        if twin_face == ext:
            continue
        a, b = (he.face, twin_face) if he.face < twin_face else (twin_face, he.face)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        kind = he.kind if he.kind in ("door", "wall") else "wall"
        g.add_edge(str(a), str(b), kind=kind)
    return g


def perimeter_spaces(sd: PlanarSubdivision) -> set[str]:
    """Return ruimte-keys die aan de exterior grenzen (buitengevel)."""
    return {str(fid) for fid in sd.perimeter_faces()}


def door_pairs(sd: PlanarSubdivision) -> list[tuple[str, str]]:
    """Return ``(a, b)``-paren van ruimten verbonden door een ``door``-edge."""
    ext = sd.exterior_face()
    pairs: set[tuple[str, str]] = set()
    for he in sd.half_edges:
        if he.face == ext or he.kind != "door":
            continue
        twin_face = sd.half_edges[he.twin].face
        if twin_face == ext:
            continue
        a, b = (he.face, twin_face) if he.face < twin_face else (twin_face, he.face)
        pairs.add((str(a), str(b)))
    return sorted(pairs)
