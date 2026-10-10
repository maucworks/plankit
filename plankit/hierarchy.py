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


def _shared_segment(
    a: Rect, b: Rect
) -> tuple[float, float, float, float] | None:
    """Langste overlappende collineaire span tussen twee blokken (of None)."""
    best: tuple[float, tuple[float, float, float, float]] | None = None
    if abs(a[2] - b[0]) <= 1e-9 or abs(b[2] - a[0]) <= 1e-9:
        x = a[2] if abs(a[2] - b[0]) <= 1e-9 else b[2]
        lo, hi = max(a[1], b[1]), min(a[3], b[3])
        if hi - lo > 1e-9:
            best = (hi - lo, (x, lo, x, hi))
    if abs(a[3] - b[1]) <= 1e-9 or abs(b[3] - a[1]) <= 1e-9:
        y = a[3] if abs(a[3] - b[1]) <= 1e-9 else b[3]
        lo, hi = max(a[0], b[0]), min(a[2], b[2])
        if hi - lo > 1e-9 and (best is None or hi - lo > best[0]):
            best = (hi - lo, (lo, y, hi, y))
    return best[1] if best is not None else None


def _shared_segments(blocks: dict[str, Rect]) -> dict[tuple[str, str], tuple[float, float]]:
    """Middens van gedeelde blokranden (langste per paar), beide richtingen."""
    out: dict[tuple[str, str], tuple[float, float]] = {}
    keys = list(blocks)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            seg = _shared_segment(blocks[keys[i]], blocks[keys[j]])
            if seg is not None:
                mid = ((seg[0] + seg[2]) / 2.0, (seg[1] + seg[3]) / 2.0)
                out[(keys[i], keys[j])] = mid
                out[(keys[j], keys[i])] = mid
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


def _anchor_against(
    area: float,
    seg: tuple[float, float, float, float],
    block: Rect,
    left_or_below: bool,
    min_width: float | None = None,
    span: bool = False,
) -> Rect | None:
    """Leg kamer vlak tegen het segment vanuit eigen zijde, overlappend midden.

    Beide oriëntaties en vierkant proberen; score = overlap, dan mate (span:
    eerst blok overspannen voor kamers met contacten aan weerszijden).
    Past niets binnen het blok → None. Deterministisch.
    """
    vertical = abs(seg[0] - seg[2]) <= 1e-9
    seg_lo, seg_hi = (seg[1], seg[3]) if vertical else (seg[0], seg[2])
    seg_mid = (seg_lo + seg_hi) / 2.0
    if vertical:
        span_need = (block[2] - block[0]) - 1e-9  # volle breedte = overkant halen
    else:
        span_need = (block[3] - block[1]) - 1e-9  # volle hoogte = overkant halen
    best: tuple[tuple, Rect] | None = None
    for cap in (1.5, 1.0):
        for landscape in (True, False):
            w, h = shape_for_area(area, max_aspect=cap, landscape=landscape, min_width=min_width)
            if vertical:
                ox = seg[0] - w if left_or_below else seg[0]
                oy = min(max(seg_mid - h / 2.0, block[1]), block[3] - h)
            else:
                oy = seg[1] - h if left_or_below else seg[1]
                ox = min(max(seg_mid - w / 2.0, block[0]), block[2] - w)
            cand = (ox, oy, ox + w, oy + h)
            if (
                cand[0] < block[0] - 1e-9
                or cand[1] < block[1] - 1e-9
                or cand[2] > block[2] + 1e-9
                or cand[3] > block[3] + 1e-9
            ):
                continue
            if vertical:
                overlap = max(0.0, min(oy + h, seg_hi) - max(oy, seg_lo))
                extent = h
                spans = w >= span_need
            else:
                overlap = max(0.0, min(ox + w, seg_hi) - max(ox, seg_lo))
                extent = w
                spans = h >= span_need
            key = ((1 if spans else 0), round(overlap, 1), extent) if span else (round(overlap, 1), extent)
            if best is None or key > best[0]:
                best = (key, cand)
    if best is None:
        return None
    overlap_rounded = best[0][1] if span else best[0][0]
    if overlap_rounded <= 1e-9:
        return None
    return best[1]


def _anchor_toward(
    area: float,
    seg: tuple[float, float, float, float],
    block: Rect,
    fixed: Rect,
    min_width: float | None = None,
    span: bool = False,
) -> Rect | None:
    """Leg kamer vlak tegen het segment, maximaal overlappend met de vaste rect.

    Beide oriëntaties en vierkant proberen (span: eerst overspannen);
    past niets binnen het blok of geen overlap → None. Deterministisch.
    """
    vertical = abs(seg[0] - seg[2]) <= 1e-9
    if vertical:
        span_need = (block[2] - block[0]) - 1e-9
    else:
        span_need = (block[3] - block[1]) - 1e-9
    best: tuple[tuple, Rect] | None = None

    def inside(cand: Rect) -> bool:
        return (
            cand[0] >= block[0] - 1e-9
            and cand[1] >= block[1] - 1e-9
            and cand[2] <= block[2] + 1e-9
            and cand[3] <= block[3] + 1e-9
        )

    def spans(cand: Rect, w: float, h: float) -> bool:
        if vertical:
            return w >= span_need
        return h >= span_need
        return cand[0] <= block[0] + 1e-9 and cand[0] + w >= block[2] - 1e-9

    for cap in (1.5, 1.0):
        for landscape in (True, False):
            w, h = shape_for_area(area, max_aspect=cap, landscape=landscape, min_width=min_width)
            if vertical:
                extent = h
                origins = [(seg[0] - w, None), (seg[0], None)]
            else:
                extent = w
                origins = [(None, seg[1] - h), (None, seg[1])]
            for ox_opt, oy_opt in origins:
                if vertical:
                    assert ox_opt is not None
                    oy = min(max((fixed[1] + fixed[3]) / 2.0 - h / 2.0, block[1]), block[3] - h)
                    cand = (ox_opt, oy, ox_opt + w, oy + h)
                    overlap = max(0.0, min(oy + h, fixed[3]) - max(oy, fixed[1]))
                else:
                    assert oy_opt is not None
                    ox = min(max((fixed[0] + fixed[2]) / 2.0 - w / 2.0, block[0]), block[2] - w)
                    cand = (ox, oy_opt, ox + w, oy_opt + h)
                    overlap = max(0.0, min(ox + w, fixed[2]) - max(ox, fixed[0]))
                if not inside(cand):
                    continue
                key = (
                    ((1 if spans(cand, w, h) else 0), round(overlap, 1), extent)
                    if span
                    else (round(overlap, 1), extent)
                )
                if best is None or key > best[0]:
                    best = (key, cand)
    if best is None:
        return None
    overlap_rounded = best[0][1] if span else best[0][0]
    if overlap_rounded <= 1e-9:
        return None
    return best[1]


def _anchor_pairs(
    program: RoomProgram,
    members: dict[str, list[str]],
    blocks: dict[str, Rect],
    min_widths: dict[str, float] | None = None,
) -> tuple[dict[str, Rect], list[str], list[tuple[str, str]]]:
    """Veranker deur-paren over blokranden: één paar per blokkenpaar.

    Geeft (ankers, issues, beoogde paren). Beide kamers vlak tegen het langste
    gedeelde segment, overlappend interval; staat één zijde al vast, dan schuift
    de ander ernaartoe. Past het niet → issue i.p.v. stilzwijgen.
    """
    from plankit.operators import _rects_overlap, _shared_wall

    room_super = {k: s for s, keys in members.items() for k in keys}
    anchors: dict[str, Rect] = {}
    issues: list[str] = []
    intended: list[tuple[str, str]] = []
    done: set[frozenset] = set()
    edges = sorted(
        (e for e in program.edges if e.kind in ("door", "wall") and e.required),
        key=lambda e: (e.a, e.b),
    )
    contact_supers: dict[str, set[str]] = {}
    for edge in edges:
        sa, sb = room_super.get(edge.a), room_super.get(edge.b)
        if sa is None or sb is None or sa == sb:
            continue
        contact_supers.setdefault(edge.a, set()).add(sb)
        contact_supers.setdefault(edge.b, set()).add(sa)
    span_map = {k: len(s) >= 2 for k, s in contact_supers.items()}
    for edge in edges:
        sa, sb = room_super.get(edge.a), room_super.get(edge.b)
        if sa is None or sb is None or sa == sb:
            continue
        pair = frozenset((sa, sb))
        if pair in done:
            continue
        seg = _shared_segment(blocks[sa], blocks[sb])
        if seg is None:
            issues.append(f"geen gedeelde rand voor {edge.a}-{edge.b} ({sa}/{sb})")
            done.add(pair)
            continue
        area_a = program.nodes[edge.a].area_min
        area_b = program.nodes[edge.b].area_min
        if area_a is None or area_b is None:
            issues.append(f"paar {edge.a}-{edge.b} zonder oppervlak")
            done.add(pair)
            continue
        mw = min_widths or {}
        a_anchored = edge.a in anchors
        b_anchored = edge.b in anchors
        if a_anchored and b_anchored:
            done.add(pair)
            if _shared_wall(anchors[edge.a], anchors[edge.b]) <= 1e-9:
                issues.append(f"paar {edge.a}-{edge.b} zonder overlap aan gedeelde rand")
            continue
        if not a_anchored and not b_anchored:
            vertical = abs(seg[0] - seg[2]) <= 1e-9
            ra = blocks[sa]
            a_left = (ra[2] <= blocks[sb][0] + 1e-9) if vertical else (ra[3] <= blocks[sb][1] + 1e-9)
            rect_a = _anchor_against(area_a, seg, blocks[sa], a_left, mw.get(edge.a), span_map.get(edge.a, False))
            rect_b = _anchor_against(area_b, seg, blocks[sb], not a_left, mw.get(edge.b), span_map.get(edge.b, False))
            if rect_a is None or rect_b is None:
                issues.append(f"paar {edge.a}-{edge.b} past niet aan gedeelde rand")
                done.add(pair)
                continue
            clash = any(
                _rects_overlap(rect_a, r) for k, r in anchors.items() if room_super[k] == sa
            ) or any(
                _rects_overlap(rect_b, r) for k, r in anchors.items() if room_super[k] == sb
            )
            if clash or _shared_wall(rect_a, rect_b) <= 1e-9:
                issues.append(f"paar {edge.a}-{edge.b} zonder overlap aan gedeelde rand")
                done.add(pair)
                continue
            anchors[edge.a], anchors[edge.b] = rect_a, rect_b
            intended.append((edge.a, edge.b))
            done.add(pair)
            continue
        mover, fixed, mblock = (
            (edge.a, anchors[edge.b], blocks[sa])
            if b_anchored
            else (edge.b, anchors[edge.a], blocks[sb])
        )
        mover_area = program.nodes[mover].area_min
        if mover_area is None:
            issues.append(f"paar {edge.a}-{edge.b} zonder oppervlak")
            done.add(pair)
            continue
        mover_rect = _anchor_toward(
            mover_area, seg, mblock, fixed, mw.get(mover), span_map.get(mover, False)
        )
        clash = mover_rect is None or any(
            _rects_overlap(mover_rect, r)
            for k, r in anchors.items()
            if room_super[k] == room_super[mover]
        )
        if clash or (mover_rect is not None and _shared_wall(mover_rect, fixed) <= 1e-9):
            issues.append(f"paar {edge.a}-{edge.b} zonder overlap aan gedeelde rand")
            done.add(pair)
            continue
        assert mover_rect is not None
        anchors[mover] = mover_rect
        intended.append((edge.a, edge.b))
        done.add(pair)
    return anchors, sorted(set(issues)), intended


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
    breedte-eis. Vereiste contacten over blokranden worden eerst als paar
    verankerd (één per blokkenpaar); de rest vult magnetisch. Geeft
    ``(proposal, issues)``: kamers die buiten hun blok vallen worden
    wel opgenomen maar gemeld als envelop-issue (graceful, M12a-lijn).
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
    anchors, anchor_issues, intended = _anchor_pairs(program, members, blocks, min_widths)
    for superkey, block in blocks.items():
        room_keys = members[superkey]
        sub_attractors = {k: attractors[k] for k in room_keys if k in attractors}
        sub_placed = {k: anchors[k] for k in room_keys if k in anchors}
        sub = _sub_program(program, room_keys)
        opt_a = propose_magnet(
            sub, seed=seed, bounds=block, attractors=sub_attractors,
            min_widths=min_widths, placed=sub_placed or None,
        )
        opt_b = propose_magnet(
            sub, seed=seed, bounds=block, attractors=sub_attractors, min_widths=min_widths,
        )

        def score(prop: dict[str, list[Vec]]) -> tuple[int, int, int]:
            """(kamers buiten blok, -intra-contacten, -paar-contacten): lager beter."""
            over = 0
            for pts in prop.values():
                xs = [p.x for p in pts]
                ys = [p.y for p in pts]
                if (
                    min(xs) < block[0] - 1e-9
                    or min(ys) < block[1] - 1e-9
                    or max(xs) > block[2] + 1e-9
                    or max(ys) > block[3] + 1e-9
                ):
                    over += 1
            boxes = {}
            for key, pts in prop.items():
                xs = [p.x for p in pts]
                ys = [p.y for p in pts]
                boxes[key] = (min(xs), min(ys), max(xs), max(ys))
            intra = 0
            for edge in program.edges:
                if edge.kind not in ("door", "wall") or not edge.required:
                    continue
                if edge.a in boxes and edge.b in boxes:
                    if _shared_wall(boxes[edge.a], boxes[edge.b]) > 1e-9:
                        intra += 1
            touch = sum(
                1 for a, b in intended
                if a in boxes and b in boxes and _shared_wall(boxes[a], boxes[b]) > 1e-9
            )
            return (over, -intra, -touch)

        keep_anchors = score(opt_a) <= score(opt_b)
        fine = opt_a if keep_anchors else opt_b
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
    boxes = {}
    for key, pts in proposal.items():
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        boxes[key] = (min(xs), min(ys), max(xs), max(ys))
    ok_pairs = {
        (a, b) for a, b in intended if _shared_wall(boxes[a], boxes[b]) > 1e-9
    }
    pair_issues = [i for i in anchor_issues]
    issues.extend(
        i for i in pair_issues
        if not any(f"paar {a}-{b}" in i for a, b in ok_pairs)
    )
    return proposal, sorted(set(issues))
