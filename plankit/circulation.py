# This file was generated with the assistance of an AI coding tool.
"""Verkeersruimte-afleiding: gang-backbone over de wand-graaf + saneringsfilter.

Naar Marson-Musse (backbone via kortste paden, buitenmuren uitgesloten) en
Mirahmadi (minimale gang-m², misvorming eruit). De backbone is een boom van
wand-doorgangen naar een wortel — welke wanden open moeten voor circulatie.
Geometrisch uitbenen (carven) en herafstelling zijn later werk; dit is de
analyse- en poortlaag. Deterministisch, zonder extra dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from plankit.planar import PlanarSubdivision


@dataclass
class BackboneLink:
    """Eén schakel: gedeelde wand tussen twee ruimten op de route naar de wortel."""

    a: int
    b: int
    length: float
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0


@dataclass
class CorridorBackbone:
    """Boom van wand-doorgangen (faces als knopen) plus sanerings-oordeel."""

    root: int
    links: list[BackboneLink] = field(default_factory=list)


def _wall_graph(sd: PlanarSubdivision) -> dict[int, dict[int, tuple[float, tuple]]]:
    """Duale wand-graaf: fid -> buur-fid -> (gedeelde lengte, segment-eindpunten)."""
    ext = sd.exterior_face()
    graph: dict[int, dict[int, tuple[float, tuple]]] = {}
    for he_id, he in enumerate(sd.half_edges):
        if he_id > he.twin:
            continue
        twin = sd.half_edges[he.twin]
        if he.face == ext or twin.face == ext:
            continue  # buitenmuren uitgesloten (Marson-Musse)
        a = sd.vertices[he.origin]
        b = sd.vertices[sd.half_edges[he.next].origin]
        length = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
        seg = (a.x, a.y, b.x, b.y)
        for x, y in ((he.face, twin.face), (twin.face, he.face)):
            graph.setdefault(x, {})
            prev = graph[x].get(y)
            if prev is None or length > prev[0]:
                graph[x][y] = (length, seg)
    for fid in sd.bounded_faces():
        graph.setdefault(fid, {})
    return graph


def corridor_backbone(
    sd: PlanarSubdivision, root: int | None = None
) -> CorridorBackbone:
    """Boom van wand-doorgangen: elke ruimte via minste wanden naar de wortel.

    Wortel default: hoogste graad (hub), bij gelijk kleinste face-id.
    Deterministisch (Dijkstra met gesorteerde buren).
    """
    graph = _wall_graph(sd)
    if root is None:
        root = min(sorted(graph), key=lambda f: (-len(graph[f]), f))
    dist: dict[int, float] = {root: 0.0}
    parent: dict[int, int] = {}
    done: set[int] = set()
    while len(done) < len(graph):
        rest = sorted((d, f) for f, d in dist.items() if f not in done)
        if not rest:
            break  # losse component: geen route
        _, cur = rest[0]
        done.add(cur)
        for nbr in sorted(graph[cur]):
            nd = dist[cur] + 1.0
            if nbr not in dist or nd < dist[nbr] - 1e-9:
                dist[nbr] = nd
                parent[nbr] = cur
    links = []
    for fid in sorted(parent):
        length, seg = graph[parent[fid]][fid]
        links.append(
            BackboneLink(a=parent[fid], b=fid, length=length,
                         x1=seg[0], y1=seg[1], x2=seg[2], y2=seg[3])
        )
    links.sort(key=lambda link: (link.a, link.b))
    return CorridorBackbone(root=root, links=links)


def corridor_filter(
    sd: PlanarSubdivision,
    backbone: CorridorBackbone,
    width: float = 1.2,
    max_fraction: float = 0.25,
    min_length: float | None = None,
) -> tuple[bool, float]:
    """Saneringspoor (Mirahmadi): gang-aandeel en stompjes toetsen.

    Geschatte gang-m² = Σ lengte × breedte; fractie van Σ face-areas.
    Geeft `(ok, fractie)`; ok bij fractie ≤ max én elke schakel ≥ min_length
    (default = width: korter kan geen gang dragen).
    """
    if min_length is None:
        min_length = width
    total = sum(sd.face_area(fid) for fid in sd.bounded_faces())
    estimate = sum(link.length for link in backbone.links) * width
    fraction = estimate / total if total > 0 else 0.0
    ok = fraction <= max_fraction and all(
        link.length >= min_length - 1e-9 for link in backbone.links
    )
    return ok, fraction
