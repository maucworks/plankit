# This file was generated with the assistance of an AI coding tool.
"""Graaf-gedreven generatie-operatoren: deterministische geometrie uit het PvE.

De LLM roept deze operatoren aan in plaats van zelf coördinaten uit te rekenen.
Alles is deterministisch en zonder optionele dependencies.
"""

from __future__ import annotations

import math
import random

from plankit.geometry import Vec
from plankit.program import ProgramSpace, RoomProgram

_TOL = 1e-9


def _rect_of(points: list[Vec]) -> tuple[float, float, float, float] | None:
    """Return (x0, y0, x1, y1) als *points* een as-uitgelijnde rechthoek is."""
    xs = sorted({round(p.x, 9) for p in points})
    ys = sorted({round(p.y, 9) for p in points})
    if len(xs) == 2 and len(ys) == 2 and len(points) >= 4:
        return (xs[0], ys[0], xs[1], ys[1])
    return None


def _rect_points(x0: float, y0: float, x1: float, y1: float) -> list[Vec]:
    """Rechthoekvoet als CCW Vec-lijst."""
    return [Vec(x0, y0), Vec(x1, y0), Vec(x1, y1), Vec(x0, y1)]


def shape_for_area(
    area: float, max_aspect: float = 1.5, landscape: bool | None = None
) -> tuple[float, float]:
    """Kies (w, d) voor *area* binnen een aspect-cap (MFP-factorparen).

    Geeft `w * d == area` (op float-epsilon na) met
    `max(w, d) / min(w, d) <= max_aspect`. Deterministisch: `landscape=True`
    (default) geeft `w >= d`, `landscape=False` geeft `d > w`.
    """
    if area <= 0:
        raise ValueError(f"shape_for_area: area moet positief zijn, got {area!r}")
    if max_aspect < 1:
        raise ValueError(f"shape_for_area: max_aspect moet >= 1 zijn, got {max_aspect!r}")
    if landscape is None:
        landscape = True
    w = math.sqrt(area * max_aspect)
    d = area / w
    if not landscape:
        w, d = d, w
    return (w, d)


def place_space(
    program: RoomProgram,
    key: str,
    x0: float,
    y0: float,
    w: float | None = None,
    d: float | None = None,
    max_aspect: float = 1.5,
) -> list[Vec]:
    """Plaats ruimte *key* als rechthoek met oorsprong (x0, y0).

    Afmetingen honoreren ``area_min``/``area_max``: geef beide, of één (de
    ander volgt uit ``area_min``), of geen (vorm uit :func:`shape_for_area`
    binnen ``max_aspect``).
    """
    if key not in program.nodes:
        raise KeyError(f"place_space: onbekende knoop {key!r}")
    space = program.nodes[key]
    if space.area_min is None:
        raise ValueError(f"place_space: {key!r} heeft geen area_min")
    lo = space.area_min
    hi = space.area_max
    if w is not None and d is not None:
        if w <= 0 or d <= 0:
            raise ValueError(f"place_space: w en d moeten positief zijn, got {w!r}, {d!r}")
        area = w * d
        if area < lo - _TOL or (hi is not None and area > hi + _TOL):
            raise ValueError(
                f"place_space: {w!r}x{d!r} = {area:.2f} m² buiten [{lo}, {hi}] voor {key!r}"
            )
    elif w is not None:
        if w <= 0:
            raise ValueError(f"place_space: w moet positief zijn, got {w!r}")
        d = lo / w
    elif d is not None:
        if d <= 0:
            raise ValueError(f"place_space: d moet positief zijn, got {d!r}")
        w = lo / d
    else:
        w, d = shape_for_area(lo, max_aspect)
    return _rect_points(x0, y0, x0 + w, y0 + d)


def split_footprint(points: list[Vec], axis: str, at: float) -> tuple[list[Vec], list[Vec]]:
    """Splits een rechthoekige footprint langs ``x=at`` of ``y=at``."""
    rect = _rect_of(points)
    if rect is None:
        raise ValueError("split_footprint: alleen as-uitgelijnde rechthoeken")
    x0, y0, x1, y1 = rect
    if axis == "x":
        if not (x0 < at < x1):
            raise ValueError(f"split_footprint: at={at!r} buiten ({x0}, {x1})")
        return (_rect_points(x0, y0, at, y1), _rect_points(at, y0, x1, y1))
    if axis == "y":
        if not (y0 < at < y1):
            raise ValueError(f"split_footprint: at={at!r} buiten ({y0}, {y1})")
        return (_rect_points(x0, y0, x1, at), _rect_points(x0, at, x1, y1))
    raise ValueError(f"split_footprint: axis moet 'x' of 'y' zijn, got {axis!r}")


def mirror_footprint(points: list[Vec], axis: str, coord: float) -> list[Vec]:
    """Spiegel een footprint over de lijn ``x=coord`` of ``y=coord``.

    De winding blijft behouden (volgorde wordt omgekeerd).
    """
    if axis == "x":
        mirrored = [Vec(2.0 * coord - p.x, p.y) for p in points]
    elif axis == "y":
        mirrored = [Vec(p.x, 2.0 * coord - p.y) for p in points]
    else:
        raise ValueError(f"mirror_footprint: axis moet 'x' of 'y' zijn, got {axis!r}")
    return list(reversed(mirrored))


def add_room(program: RoomProgram, key: str, space: ProgramSpace) -> RoomProgram:
    """Voeg een knoop toe (GADG-additie). Faalt bij een bestaande sleutel."""
    if key in program.nodes:
        raise KeyError(f"add_room: {key!r} bestaat al")
    program.nodes[key] = space
    return program


def remove_room(program: RoomProgram, key: str) -> RoomProgram:
    """Verwijder een knoop plus alle kanten ernaartoe (GADG-subtractie)."""
    if key not in program.nodes:
        raise KeyError(f"remove_room: onbekende knoop {key!r}")
    del program.nodes[key]
    program.edges = [e for e in program.edges if e.a != key and e.b != key]
    return program


def layout_row(
    program: RoomProgram,
    keys: list[str],
    x0: float,
    y0: float,
    depth: float,
    gap: float = 0.0,
    max_aspect: float = 1.5,
) -> dict[str, list[Vec]]:
    """Leg ruimten naast elkaar in een rij met vaste diepte.

    Elke ruimte krijgt breedte ``area_min / depth``. Deterministisch;
    samengesteld uit :func:`place_space` (``max_aspect`` wordt doorgegeven).
    """
    if depth <= 0:
        raise ValueError(f"layout_row: depth moet positief zijn, got {depth!r}")
    out: dict[str, list[Vec]] = {}
    x = x0
    for key in keys:
        if key not in program.nodes:
            raise KeyError(f"layout_row: onbekende knoop {key!r}")
        space = program.nodes[key]
        if space.area_min is None:
            raise ValueError(f"layout_row: {key!r} heeft geen area_min")
        w = space.area_min / depth
        out[key] = place_space(program, key, x, y0, w=w, d=depth, max_aspect=max_aspect)
        x += w + gap
    return out


def _rects_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    """True als interieurs overlappen (raken mag)."""
    return (
        a[0] < b[2] - _TOL
        and b[0] < a[2] - _TOL
        and a[1] < b[3] - _TOL
        and b[1] < a[3] - _TOL
    )


def _shared_wall(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Gedeelde wandlengte van twee as-uitgelijnde rechthoeken."""
    total = 0.0
    if abs(a[2] - b[0]) <= _TOL or abs(b[2] - a[0]) <= _TOL:
        total += max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    if abs(a[3] - b[1]) <= _TOL or abs(b[3] - a[1]) <= _TOL:
        total += max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    return total


def _anchors(
    rect: tuple[float, float, float, float], w: float, h: float
) -> list[tuple[float, float]]:
    """Kandidaat-oorsprongen: nieuwe rect (w, h) vlak tegen elke zijde van
    *rect*, telkens uitgelijnd op beide hoeken."""
    x0, y0, x1, y1 = rect
    return [
        (x1, y0),
        (x1, y1 - h),
        (x0 - w, y0),
        (x0 - w, y1 - h),
        (x0, y1),
        (x1 - w, y1),
        (x0, y0 - h),
        (x1 - w, y0 - h),
    ]


def propose_magnet(
    program: RoomProgram,
    seed: int = 0,
    max_aspect: float = 1.5,
    partner_bonus: float = 2.0,
    wet_bonus: float = 1.5,
    daylight_bonus: float = 1.0,
    bounds: tuple[float, float, float, float] | None = None,
    attractors: dict[str, tuple[float, float]] | None = None,
    attract_bonus: float = 0.5,
) -> dict[str, list[Vec]]:
    """Greedy compositie: kamers magnetiseren tegen elkaar (MFP-volgorde+score).

    Plaatsvolgorde: entrance eerst, daarna de kamer met de meeste reeds
    geplaatste adjacentie-buren (`door`/`wall`; seeded jitter als tie-break).
    Elke kamer krijgt een vorm uit :func:`shape_for_area` (oriëntatie seeded;
    binnen bounds beide oriëntaties) en de overlap-vrije positie met de meeste
    gedeelde wand (partners tellen ``partner_bonus`` keer). Natte cellen (`wet`)
    clusteren via ``wet_bonus`` (additief); daglicht-kamers (`daylight`) scoren
    ``daylight_bonus`` per meter niet-rakende wand. Met ``bounds`` blijft alles
    binnen de envelop (two-step); ``attractors`` trekt kamers met partners
    buiten het blok naar de gedeelde blokrand (grens-coördinatie).
    Deterministisch bij gelijke *seed*.
    """
    keys = [k for k in program.nodes if not program.nodes[k].exterior]
    for key in keys:
        if program.nodes[key].area_min is None:
            raise ValueError(f"propose_magnet: {key!r} heeft geen area_min")
    partners: dict[str, set[str]] = {k: set() for k in keys}
    for edge in program.edges:
        if edge.kind in ("door", "wall") and edge.a in partners and edge.b in partners:
            partners[edge.a].add(edge.b)
            partners[edge.b].add(edge.a)
    wet_rooms = {k for k in keys if program.nodes[k].wet}
    rng = random.Random(seed)
    order: list[str] = []
    remaining = list(keys)
    for key in remaining:
        if program.nodes[key].entrance:
            order.append(key)
            break
    for key in order:
        remaining.remove(key)
    while remaining:
        placed = set(order)
        scored = [
            (len(partners[key] & placed) + rng.random() * 0.05, key) for key in remaining
        ]
        scored.sort()
        best = scored[-1][1]
        order.append(best)
        remaining.remove(best)

    def inside(cand: tuple[float, float, float, float]) -> bool:
        """Past de kandidaat binnen de bounds (of geen bounds)."""
        if bounds is None:
            return True
        return (
            cand[0] >= bounds[0] - _TOL
            and cand[1] >= bounds[1] - _TOL
            and cand[2] <= bounds[2] + _TOL
            and cand[3] <= bounds[3] + _TOL
        )

    def score_of(
        cand: tuple[float, float, float, float], key: str, w: float, h: float
    ) -> float:
        """Contact-score van een kandidaat (partners, nat, daglicht, attractor)."""
        shared_total = 0.0
        score = 0.0
        for okey, orect in rects.items():
            shared = _shared_wall(cand, orect)
            shared_total += shared
            if okey in partners[key]:
                score += shared * partner_bonus
            else:
                score += shared
            if key in wet_rooms and okey in wet_rooms:
                score += shared * wet_bonus
        if program.nodes[key].daylight:
            score += (2 * (w + h) - shared_total) * daylight_bonus
        if attractors is not None and key in attractors and bounds is not None:
            ax, ay = attractors[key]
            cx, cy = (bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0
            dx, dy = ax - cx, ay - cy
            norm = (dx * dx + dy * dy) ** 0.5
            if norm > 1e-9:
                px, py = (cand[0] + cand[2]) / 2.0 - cx, (cand[1] + cand[3]) / 2.0 - cy
                score += max(0.0, (px * dx + py * dy) / norm) * attract_bonus
        return score

    def free_inside(
        w: float, h: float, step: float = 0.5
    ) -> tuple[float, float, float, float] | None:
        """Eerste overlap-vrije plek binnen de bounds (scan, deterministisch)."""
        assert bounds is not None
        oy = bounds[1]
        while oy + h <= bounds[3] + _TOL:
            ox = bounds[0]
            while ox + w <= bounds[2] + _TOL:
                cand = (ox, oy, ox + w, oy + h)
                if not any(_rects_overlap(cand, r) for r in rects.values()):
                    return cand
                ox += step
            oy += step
        return None

    rects: dict[str, tuple[float, float, float, float]] = {}
    out: dict[str, list[Vec]] = {}
    for key in order:
        area = program.nodes[key].area_min
        if bounds is None:
            orientations = (rng.random() < 0.5,)
        else:
            orientations = (True, False)  # beide proberen: passing in de envelop
        if not rects:
            landscape = orientations[0]
            w, h = shape_for_area(area, max_aspect, landscape=landscape)
            if bounds is not None and attractors is not None and key in attractors:
                ax, ay = attractors[key]
                corners = [
                    (bounds[0], bounds[1]),
                    (bounds[2] - w, bounds[1]),
                    (bounds[0], bounds[3] - h),
                    (bounds[2] - w, bounds[3] - h),
                ]
                corners = [
                    c
                    for c in corners
                    if c[0] >= bounds[0] - _TOL
                    and c[1] >= bounds[1] - _TOL
                    and c[0] + w <= bounds[2] + _TOL
                    and c[1] + h <= bounds[3] + _TOL
                ] or [(bounds[0], bounds[1])]
                ox, oy = min(corners, key=lambda c: (c[0] - ax) ** 2 + (c[1] - ay) ** 2)
            else:
                ox, oy = (bounds[0], bounds[1]) if bounds is not None else (0.0, 0.0)
            rect = (ox, oy, ox + w, oy + h)
        else:
            best_rect: tuple[float, float, float, float] | None = None
            best_score = -1.0
            for landscape in orientations:
                w, h = shape_for_area(area, max_aspect, landscape=landscape)
                for other in rects.values():
                    for ox, oy in _anchors(other, w, h):
                        cand = (ox, oy, ox + w, oy + h)
                        if not inside(cand):
                            continue
                        if any(_rects_overlap(cand, r) for r in rects.values()):
                            continue
                        score = score_of(cand, key, w, h)
                        if score > best_score:
                            best_score = score
                            best_rect = cand
            if best_rect is None and bounds is not None:
                for landscape in orientations:
                    w, h = shape_for_area(area, max_aspect, landscape=landscape)
                    best_rect = free_inside(w, h)
                    if best_rect is not None:
                        break
            if best_rect is None:  # volgebouwd: rechts van de bbox plakken
                w, h = shape_for_area(area, max_aspect, landscape=orientations[0])
                x = max(r[2] for r in rects.values())
                best_rect = (x, 0.0, x + w, h)
            rect = best_rect
        rects[key] = rect
        out[key] = _rect_points(*rect)
    return out
