# This file was generated with the assistance of an AI coding tool.
"""Pure derivatie: ruimten en relaties uit een :class:`PlanarSubdivision`.

De tegenhanger van ``ifckit.spatial.derive``, maar IFC-vrij: de "gerealiseerde
graaf" is hier het skelet zelf.
"""

from __future__ import annotations

from dataclasses import dataclass

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


#: Wandfuncties per lijnstuk: buitengevel (twin = exterior), doorgang
#: (deur-markering), scheidend (gedeelde wand).
WALL_FUNCTIONS = ("buitengevel", "doorgang", "scheidend")


@dataclass
class WallSegment:
    """Eén wandsegment (twin-paar) met functie en PvE-koppeling.

    Attributes:
        a: Label of face-id van de ene kamer (`"buiten"` bij exterior).
        b: Label of face-id van de andere kamer.
        x1, y1, x2, y2: Eindpunten (voor render/IFC).
        length: Lengte in meters.
        function: ``"buitengevel"`` | ``"doorgang"`` | ``"scheidend"``.
        edge: PvE-label `"a-b:kind"` als een eis dit segment verklaart, anders `None`.
    """

    a: str
    b: str
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    function: str
    edge: str | None = None


def wall_segments(sd: PlanarSubdivision, program=None) -> list[WallSegment]:
    """Leid per lijnstuk de wandfunctie af (M13a): buitengevel/doorgang/scheidend.

    Met een PvE wordt per segment de verklarende eis gezocht (`door`-eis bij
    doorgang, `facade`-eis bij buitengevel, `wall`-eis bij scheidend).
    """
    ext = sd.exterior_face()

    def label(fid: int) -> str:
        if fid == ext:
            return "buiten"
        return sd.faces[fid].label or str(fid)

    out: list[WallSegment] = []
    for he_id, he in enumerate(sd.half_edges):
        if he_id > he.twin:
            continue  # twin-paar één keer
        twin = sd.half_edges[he.twin]
        a = sd.vertices[he.origin]
        b = sd.vertices[sd.half_edges[he.next].origin]
        length = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
        la, lb = label(he.face), label(twin.face)
        if twin.face == ext or he.face == ext:
            function = "buitengevel"
        elif he.kind == "door":
            function = "doorgang"
        else:
            function = "scheidend"
        edge_label = None
        if program is not None:
            for edge in program.edges:
                kinds = {"buitengevel": ("facade",), "doorgang": ("door",), "scheidend": ("wall",)}
                if edge.kind not in kinds[function]:
                    continue
                pair = {edge.a, edge.b}
                if function == "buitengevel":
                    nodes = {la, lb} - {"buiten"}
                    if len(nodes) == 1 and next(iter(nodes)) in pair:
                        edge_label = f"{edge.a}-{edge.b}:{edge.kind}"
                        break
                elif {la, lb} == pair:
                    edge_label = f"{edge.a}-{edge.b}:{edge.kind}"
                    break
        out.append(
            WallSegment(
                a=la, b=lb, x1=a.x, y1=a.y, x2=b.x, y2=b.y,
                length=length, function=function, edge=edge_label,
            )
        )
    return out
