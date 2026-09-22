# This file was generated with the assistance of an AI coding tool.
"""Generatie: PvE → skelet.

Een coarse voorstel (welke ruimte waar, als rechthoek) wordt gerealiseerd als
een :class:`PlanarSubdivision`. De stub :func:`propose_layout` legt ruimten in
een strip; een echte LLM kan hier een slimmer voorstel leveren (nabuurschap,
verkeersstrategie) met dezelfde interface.
"""

from __future__ import annotations

from plankit.operators import layout_row
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram

_EPS = 1e-6


def _xy(p) -> tuple[float, float]:
    if hasattr(p, "x"):
        return (p.x, p.y)
    return (p[0], p[1])


def propose_layout(program: RoomProgram, depth: float = 4.0) -> dict:
    """Coarse stub: leg niet-exterieure ruimten in een strip.

    Bepaalt per ruimte een rechthoek op basis van ``area_min``. Dit is de plek
    waar een echte LLM zijn nabuurschap-/verkeersstrategie kwijt kan.
    """
    keys = [k for k in program.nodes if not program.nodes[k].exterior]
    return layout_row(program, keys, x0=0.0, y0=0.0, depth=depth, gap=0.0)


def generate(program: RoomProgram, proposal: dict | None = None) -> PlanarSubdivision:
    """Bouw het skelet uit het PvE.

    ``proposal`` is ``{room_key: [punten...]}`` (rechthoeken). Zonder proposal
    wordt :func:`propose_layout` gebruikt. ``door``-kanten uit het PvE worden op
    de gedeelde edges gemarkeerd.
    """
    if proposal is None:
        proposal = propose_layout(program)

    segments = []
    for pts in proposal.values():
        n = len(pts)
        for i in range(n):
            segments.append((pts[i], pts[(i + 1) % n]))
    sd = PlanarSubdivision.from_centerlines(segments)

    face_by_room: dict[str, int] = {}
    for fid in sd.bounded_faces():
        pts = sd.face_vertices(fid)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        for key, rect in proposal.items():
            xs = [_xy(p)[0] for p in rect]
            ys = [_xy(p)[1] for p in rect]
            if min(xs) - _EPS < cx < max(xs) + _EPS and min(ys) - _EPS < cy < max(ys) + _EPS:
                face_by_room[key] = fid
                break

    for key, fid in face_by_room.items():
        sd.faces[fid].label = key

    for edge in program.edges:
        if edge.kind != "door":
            continue
        fa = face_by_room.get(edge.a)
        fb = face_by_room.get(edge.b)
        if fa is not None and fb is not None:
            sd.mark_edge(fa, fb, "door")
    return sd
