# This file was generated with the assistance of an AI coding tool.
"""Hiërarchische generatie: eerst woningblokken rond de kern (grof), dan kamers
per woning (fijn, bestaande magnet).

Typologie ``open-kern`` legt concentrisch: kern in het midden, verkeer eromheen,
woningen in de buitenring. ``portiek``/``galerij`` zijn als namen vastgelegd,
implementatie volgt later. Deterministisch (seeded), zonder extra dependencies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from plankit.geometry import Vec
from plankit.operators import (
    _rects_overlap,
    _shared_wall,
    propose_magnet,
    shape_for_area,
    squarify_rects,
)
from plankit.program import RoomProgram, dwelling_budget

#: Ontsluitingstypologieën. Alleen ``open-kern`` is geïmplementeerd.
TOPOLOGIES = ("open-kern", "portiek", "galerij")

#: Pakking-slack op blok-oppervlak: een budget-groot blok is in bbox-termen
#: systematisch te klein voor rechthoek-pakking; 1.5 is een heurtistiek
#: (restruimte binnen het blok is in-woning-residu; tuning is later werk).
OVERSIZE = 1.5

Rect = tuple[float, float, float, float]


@dataclass
class DwellingEnvelope:
    """Neerwaartse envelop van een woninggroep: waaraan een blok moet voldoen.

    Attributes:
        group: Woningcode.
        area_lo: Som kamer-minima (nominaal bruto).
        area_hi: Som kamer-maxima (bruto bij volle slack).
        n_rooms: Aantal kamers.
        n_daylight: Aantal daglicht-kamers.
        daylight_area: Som minima van daglicht-kamers (gevel-behoefte).
    """

    group: str
    area_lo: float
    area_hi: float
    n_rooms: int
    n_daylight: int
    daylight_area: float


def dwelling_envelope(program: RoomProgram, group: str) -> DwellingEnvelope:
    """Leid de envelop van een woninggroep af uit het woningprogramma."""
    lo, hi = dwelling_budget(program, group)
    members = [s for s in program.nodes.values() if s.group == group]
    day = [s for s in members if s.daylight]
    return DwellingEnvelope(
        group=group,
        area_lo=lo,
        area_hi=hi,
        n_rooms=len(members),
        n_daylight=len(day),
        daylight_area=sum(s.area_min or 0.0 for s in day),
    )


def supernodes(program: RoomProgram) -> dict[str, list[str]]:
    """Groepeer kamer-keys: per woningcode, groeploze ruimten als eigen knoop."""
    out: dict[str, list[str]] = {}
    for key, space in program.nodes.items():
        if space.exterior:
            continue
        superkey = space.group if space.group is not None else key
        out.setdefault(superkey, []).append(key)
    return out


def _super_of(members: dict[str, list[str]], key: str) -> str | None:
    """Superknoop van een kamer-key (None als onbekend)."""
    for superkey, room_keys in members.items():
        if key in room_keys:
            return superkey
    return None


def _supernode_area(program: RoomProgram, members: list[str]) -> float:
    """Blok-oppervlak: budget-max bij groepen, area_min bij losse ruimten."""
    group = program.nodes[members[0]].group
    if group is not None:
        return dwelling_budget(program, group)[1]
    return sum(program.nodes[k].area_min or 0.0 for k in members)


def _cluster_bbox(rects: dict[str, Rect]) -> Rect:
    """Omhullende bbox van geplaatste blokken."""
    return (
        min(r[0] for r in rects.values()),
        min(r[1] for r in rects.values()),
        max(r[2] for r in rects.values()),
        max(r[3] for r in rects.values()),
    )


def _side_origins(bbox: Rect, side: str, w: float, h: float, step: float = 0.5):
    """Kandidaat-oorsprongen vlak tegen *side* van de cluster-bbox, scannend."""
    x0, y0, x1, y1 = bbox
    if side in ("top", "bottom"):
        oy = y1 if side == "top" else y0 - h
        t = x0 - w
        while t <= x1 + 1e-9:
            yield (t, oy)
            t += step
    else:
        ox = x1 if side == "right" else x0 - w
        t = y0 - h
        while t <= y1 + 1e-9:
            yield (ox, t)
            t += step


def _shared_segments(blocks: dict[str, Rect]) -> dict[tuple[str, str], tuple[float, float]]:
    """Middens van gedeelde blokranden (langste per paar), beide richtingen."""
    out: dict[tuple[str, str], tuple[float, float]] = {}
    keys = list(blocks)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = blocks[keys[i]], blocks[keys[j]]
            cands: list[tuple[float, tuple[float, float]]] = []
            if abs(a[2] - b[0]) <= 1e-9 or abs(b[2] - a[0]) <= 1e-9:
                lo, hi = max(a[1], b[1]), min(a[3], b[3])
                if hi - lo > 1e-9:
                    x = a[2] if abs(a[2] - b[0]) <= 1e-9 else b[2]
                    cands.append((hi - lo, (x, (lo + hi) / 2.0)))
            if abs(a[3] - b[1]) <= 1e-9 or abs(b[3] - a[1]) <= 1e-9:
                lo, hi = max(a[0], b[0]), min(a[2], b[2])
                if hi - lo > 1e-9:
                    y = a[3] if abs(a[3] - b[1]) <= 1e-9 else b[3]
                    cands.append((hi - lo, ((lo + hi) / 2.0, y)))
            if cands:
                cands.sort()
                out[(keys[i], keys[j])] = cands[-1][1]
                out[(keys[j], keys[i])] = cands[-1][1]
    return out


def coarse_open_kern(program: RoomProgram, seed: int = 0) -> dict[str, Rect]:
    """Leg superknopen concentrisch: kern centraal, verkeer eromheen, dan woningen.

    Blokgrootte uit budget-max (groepen) of area_min (los). Volgorde: kern,
    verkeers-buren van de kern, overige op budget aflopend. Zijde-volgorde per
    blok uit de seed (ring-spreiding). Deterministisch bij gelijke seed.
    """
    rng = random.Random(seed)
    members = supernodes(program)
    core = [s for s in members if any(program.nodes[k].core for k in members[s])]
    center = core[0] if core else sorted(members)[0]
    linked: set[str] = set()
    for edge in program.edges:
        if edge.kind not in ("door", "wall"):
            continue
        sa = _super_of(members, edge.a)
        sb = _super_of(members, edge.b)
        if sa == center and sb is not None and sb != center:
            linked.add(sb)
        elif sb == center and sa is not None and sa != center:
            linked.add(sa)
    rest = sorted(
        (s for s in members if s != center and s not in linked),
        key=lambda s: (-_supernode_area(program, members[s]), s),
    )
    order = [center] + sorted(linked) + rest
    sizes = {
        s: shape_for_area(max(_supernode_area(program, members[s]) * OVERSIZE, 1e-9))
        for s in order
    }
    rects: dict[str, Rect] = {}
    cw, ch = sizes[center]
    rects[center] = (-cw / 2.0, -ch / 2.0, cw / 2.0, ch / 2.0)
    sides = ["top", "right", "bottom", "left"]
    for key in order[1:]:
        w, h = sizes[key]
        start = rng.randrange(len(sides))
        rotated = sides[start:] + sides[:start]
        best_rect: Rect | None = None
        best_score = -1.0
        for side in rotated:
            for ox, oy in _side_origins(_cluster_bbox(rects), side, w, h):
                cand = (ox, oy, ox + w, oy + h)
                if any(_rects_overlap(cand, r) for r in rects.values()):
                    continue
                score = sum(_shared_wall(cand, r) for r in rects.values())
                if score > best_score:
                    best_score = score
                    best_rect = cand
        if best_rect is None:  # volgebouwd: rechts van de bbox plakken
            x = _cluster_bbox(rects)[2]
            best_rect = (x, 0.0, x + w, h)
        rects[key] = best_rect
    return rects


def coarse_layout(
    program: RoomProgram, topology: str = "open-kern", seed: int = 0
) -> dict[str, Rect]:
    """Grof-layout van superknopen per ontsluitingstypologie."""
    if topology not in TOPOLOGIES:
        raise ValueError(f"coarse_layout: onbekende typologie {topology!r}")
    if topology != "open-kern":
        raise NotImplementedError(f"coarse_layout: typologie {topology!r} volgt later")
    return coarse_open_kern(program, seed=seed)


def _polygon_area(poly: list[tuple[float, float]]) -> float:
    """Oppervlak van een polygoon (shoelace)."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def squarify_blocks(
    program: RoomProgram, boundary: list[tuple[float, float]]
) -> dict[str, Rect]:
    """Squarify-grof: verdeel de outline-bbox in woningblokken uit budgetten (D3).

    Budget-maxima worden geschaald naar de outline-m² (top-down budget-antwoord);
    groeploze ruimten doen mee op area_min. Exacte oppervlakten, aspect-gestuurd.
    """
    members = supernodes(program)
    areas: dict[str, float] = {}
    for superkey, room_keys in members.items():
        group = program.nodes[room_keys[0]].group
        if group is not None:
            areas[superkey] = dwelling_budget(program, group)[1]
        else:
            areas[superkey] = sum(program.nodes[k].area_min or 0.0 for k in room_keys)
    total = sum(areas.values())
    if total <= 0:
        raise ValueError("squarify_blocks: geen oppervlak om te verdelen")
    if _polygon_area(boundary) <= 0:
        raise ValueError("squarify_blocks: boundary heeft geen oppervlak")
    scale = _polygon_area(boundary) / total
    xs = [p[0] for p in boundary]
    ys = [p[1] for p in boundary]
    rect = (min(xs), min(ys), max(xs), max(ys))
    return squarify_rects([(key, area * scale) for key, area in areas.items()], rect)


def _sub_program(program: RoomProgram, members: list[str]) -> RoomProgram:
    """Deel-PvE van een woninggroep (alleen interne kanten)."""
    return RoomProgram(
        nodes={k: program.nodes[k] for k in members},
        edges=[e for e in program.edges if e.a in members and e.b in members],
    )


def two_step(
    program: RoomProgram,
    topology: str = "open-kern",
    seed: int = 0,
    blocks: dict[str, Rect] | None = None,
    min_widths: dict[str, float] | None = None,
) -> tuple[dict[str, list[Vec]], list[str]]:
    """Two-step-voorstel: grof blokken, fijn kamers per woning in het blok.

    Met ``blocks`` (bv. uit :func:`squarify_blocks`) wordt de grof-stap
    overgeslagen. Met ``min_widths`` respecteert de fijne vormkeuze de
    breedte-eis. Geeft ``(proposal, issues)``: kamers die buiten hun blok vallen
    worden wel opgenomen maar gemeld als envelop-issue (graceful, M12a-lijn).
    """
    if topology not in TOPOLOGIES:
        raise ValueError(f"two_step: onbekende typologie {topology!r}")
    if blocks is None:
        if topology != "open-kern":
            raise NotImplementedError(f"two_step: typologie {topology!r} volgt later")
        blocks = coarse_layout(program, topology=topology, seed=seed)
    members = supernodes(program)
    segments = _shared_segments(blocks)
    room_super = {k: s for s, keys in members.items() for k in keys}
    attractors: dict[str, tuple[float, float]] = {}
    for edge in program.edges:
        if edge.kind not in ("door", "wall"):
            continue
        for a, b in ((edge.a, edge.b), (edge.b, edge.a)):
            sa, sb = room_super.get(a), room_super.get(b)
            if sa is None or sb is None or sa == sb:
                continue
            mid = segments.get((sa, sb))
            if mid is not None:
                attractors.setdefault(a, []).append(mid)
    attractors = {
        k: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        for k, pts in attractors.items()
    }
    proposal: dict[str, list[Vec]] = {}
    issues: list[str] = []
    for superkey, block in blocks.items():
        room_keys = members[superkey]
        sub_attractors = {k: attractors[k] for k in room_keys if k in attractors}
        fine = propose_magnet(
            _sub_program(program, room_keys),
            seed=seed,
            bounds=block,
            attractors=sub_attractors,
            min_widths=min_widths,
        )
        for key, pts in fine.items():
            proposal[key] = pts
            mxs = [p.x for p in pts]
            mys = [p.y for p in pts]
            if (
                min(mxs) < block[0] - 1e-9
                or min(mys) < block[1] - 1e-9
                or max(mxs) > block[2] + 1e-9
                or max(mys) > block[3] + 1e-9
            ):
                issues.append(f"envelop te klein voor {key} ({superkey})")
    return proposal, sorted(set(issues))
