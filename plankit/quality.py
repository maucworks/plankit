# This file was generated with the assistance of an AI coding tool.
"""Impliciete kwaliteitsmetrieken (laag 2) op een skelet.

Wat het PvE *verzwijgt* en dus de architect-taak is: circulatie, proporties,
daglicht (facade). Deze metrieken zijn gegradeerd, niet hard pass/fail — ze
maken "goed redeneren over ruimte" zichtbaar.
"""

from __future__ import annotations

from plankit.graph import Graph
from plankit.planar import PlanarSubdivision


def access_graph(sd: PlanarSubdivision) -> Graph:
    """De verkeersgraaf: knopen = ruimten, kanten = ``door``-kanten."""
    from plankit.derive import door_pairs

    g = Graph()
    for fid in sd.bounded_faces():
        g.add_node(str(fid))
    for a, b in door_pairs(sd):
        g.add_edge(a, b, kind="door")
    return g


def aspect_ratios(sd: PlanarSubdivision) -> dict[str, float]:
    """Bounding-box aspect-ratio per ruimte (≥ 1; hoog = gang-achtig)."""
    out: dict[str, float] = {}
    for fid in sd.bounded_faces():
        pts = sd.face_vertices(fid)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        out[str(fid)] = max(w, h) / min(w, h) if min(w, h) > 0 else float("inf")
    return out


def facade_lengths(sd: PlanarSubdivision) -> dict[str, float]:
    """Totale lengte van de buitengevel per ruimte (daglicht-proxy)."""
    ext = sd.exterior_face()
    out: dict[str, float] = {}
    for fid in sd.bounded_faces():
        total = 0.0
        for he in sd.face_half_edges(fid):
            if sd.half_edges[sd.half_edges[he].twin].face != ext:
                continue
            a = sd.vertices[sd.half_edges[he].origin]
            b = sd.vertices[sd.half_edges[sd.half_edges[he].next].origin]
            total += ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
        out[str(fid)] = total
    return out


def circulation_depth(sd: PlanarSubdivision, root: str | None = None) -> dict[str, float]:
    """Diepte vanaf *root* over de access-graaf (circulatie-efficiëntie)."""
    from collections import deque

    g = access_graph(sd)
    nodes = list(g.nodes())
    if not nodes:
        return {}
    if root is None or root not in g:
        root = nodes[0]
    dist = {root: 0}
    queue: deque[str] = deque([root])
    while queue:
        cur = queue.popleft()
        for nbr in g.neighbors(cur):
            if nbr not in dist:
                dist[nbr] = dist[cur] + 1
                queue.append(nbr)
    return {n: float(d) for n, d in dist.items()}


def is_enfilade(sd: PlanarSubdivision) -> bool:
    """True als de access-graaf één keten is (max graad ≤ 2) — geen circulatie-hub."""
    g = access_graph(sd)
    return g.is_connected() and all(g.degree(n) <= 2 for n in g.nodes())
