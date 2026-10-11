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
    area: float,
    max_aspect: float = 1.5,
    landscape: bool | None = None,
    min_width: float | None = None,
) -> tuple[float, float]:
    """Kies (w, d) voor *area* binnen een aspect-cap (MFP-factorparen).

    Geeft `w * d == area` (op float-epsilon na) met
    `max(w, d) / min(w, d) <= max_aspect`. Deterministisch: `landscape=True`
    (default) geeft `w >= d`, `landscape=False` geeft `d > w`. Met
    `min_width`: cap-effectief = min(cap, area/min_width²) zodat de smalste
    zijde ≥ min_width; onhaalbaar (zelfs vierkant te smal) → vierkant op
    min_width (grotere m²; conform meldt area>max).
    """
    if area <= 0:
        raise ValueError(f"shape_for_area: area moet positief zijn, got {area!r}")
    if max_aspect < 1:
        raise ValueError(f"shape_for_area: max_aspect moet >= 1 zijn, got {max_aspect!r}")
    if min_width is not None:
        if min_width <= 0:
            raise ValueError(f"shape_for_area: min_width moet positief zijn, got {min_width!r}")
        if area < min_width * min_width:
            return (min_width, min_width)
        max_aspect = min(max_aspect, area / (min_width * min_width))
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
    min_width: float | None = None,
) -> list[Vec]:
    """Plaats ruimte *key* als rechthoek met oorsprong (x0, y0).

    Afmetingen honoreren ``area_min``/``area_max``: geef beide, of één (de
    ander volgt uit ``area_min``), of geen (vorm uit :func:`shape_for_area`
    binnen ``max_aspect`` en ``min_width``).
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
        w, d = shape_for_area(lo, max_aspect, min_width=min_width)
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
    min_width: float | None = None,
) -> dict[str, list[Vec]]:
    """Leg ruimten naast elkaar in een rij met vaste diepte.

    Elke ruimte krijgt breedte ``area_min / depth``. Deterministisch;
    samengesteld uit :func:`place_space` (``max_aspect``/``min_width`` worden
    doorgegeven).
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
        out[key] = place_space(
            program, key, x, y0, w=w, d=depth, max_aspect=max_aspect, min_width=min_width
        )
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
    min_widths: dict[str, float] | None = None,
    placed: dict[str, tuple[float, float, float, float]] | None = None,
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
    buiten het blok naar de gedeelde blokrand (grens-coördinatie). Met
    ``min_widths`` (kamer-key → meters) respecteert de vormkeuze de breedte-eis.
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
        done = set(order)
        scored = [
            (len(partners[key] & done) + rng.random() * 0.05, key) for key in remaining
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
    if placed:
        for key, rect in placed.items():
            if key not in keys:
                raise KeyError(f"propose_magnet: placed onbekende knoop {key!r}")
            rects[key] = rect
            out[key] = _rect_points(*rect)
    for key in order:
        if key in rects:
            continue  # voorgeplaatst: doet mee als obstakel/partner
        area = program.nodes[key].area_min
        min_width = min_widths.get(key) if min_widths is not None else None
        if bounds is None:
            orientations = (rng.random() < 0.5,)
        else:
            orientations = (True, False)  # beide proberen: passing in de envelop
        if not rects:
            landscape = orientations[0]
            w, h = shape_for_area(area, max_aspect, landscape=landscape, min_width=min_width)
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
                w, h = shape_for_area(area, max_aspect, landscape=landscape, min_width=min_width)
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
                    w, h = shape_for_area(area, max_aspect, landscape=landscape, min_width=min_width)
                    best_rect = free_inside(w, h)
                    if best_rect is not None:
                        break
            if best_rect is None:  # volgebouwd: rechts van de bbox plakken
                w, h = shape_for_area(area, max_aspect, landscape=orientations[0], min_width=min_width)
                x = max(r[2] for r in rects.values())
                best_rect = (x, 0.0, x + w, h)
            rect = best_rect
        rects[key] = rect
        out[key] = _rect_points(*rect)
    return out


def _worst(row: list[float], side: float) -> float:
    """Slechtste aspect-ratio als rij *row* een strook langs zijde *side* vormt."""
    s = sum(row)
    if s <= 0 or side <= 0:
        return float("inf")
    return max(max(a * side * side / (s * s), (s * s) / (a * side * side)) for a in row)


def squarify_rects(
    items: list[tuple[str, float]], rect: tuple[float, float, float, float]
) -> dict[str, tuple[float, float, float, float]]:
    """Squarified treemap: verdeel *rect* in kamer-m² met lage aspect-ratio's.

    Naar Bruls e.a.: dalend sorteren, rijen langs de langste zijde, rij
    fixeren zodra toevoegen verslechtert (`worst()`). Deterministisch; exacte
    oppervlakten; betegeling zonder gaten (op float-epsilon na).
    """
    children = sorted(
        ((k, float(a)) for k, a in items), key=lambda kv: -kv[1]
    )
    for key, area in children:
        if area <= 0:
            raise ValueError(f"squarify_rects: area moet positief zijn, got {key!r}={area!r}")
    out: dict[str, tuple[float, float, float, float]] = {}
    x0, y0, x1, y1 = rect
    row: list[tuple[str, float]] = []

    def layout(row: list[tuple[str, float]]) -> None:
        """Leg rij als strook langs de korte zijde (links/onder) en krimpt rest in."""
        nonlocal x0, y0, x1, y1
        s = sum(a for _, a in row)
        if (y1 - y0) <= (x1 - x0):  # kort = hoogte: strook links, volle hoogte
            t = s / (y1 - y0)
            y = y0
            for key, a in row:
                h = a / t
                out[key] = (x0, y, x0 + t, y + h)
                y += h
            x0 += t
        else:  # kort = breedte: strook onder, volle breedte
            t = s / (x1 - x0)
            x = x0
            for key, a in row:
                w = a / t
                out[key] = (x, y0, x + w, y0 + t)
                x += w
            y0 += t

    for key, area in children:
        side = min(x1 - x0, y1 - y0)
        trial = [a for _, a in row] + [area]
        if row and _worst(trial, side) > _worst([a for _, a in row], side):
            layout(row)
            row = [(key, area)]
        else:
            row.append((key, area))
    if row:
        layout(row)
    return out


def _bbox_of(pts: list) -> tuple[float, float, float, float]:
    """Bounding box van een puntenlijst (Vec of tuple)."""
    xs = [_xy(p)[0] for p in pts]
    ys = [_xy(p)[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _xy(p) -> tuple[float, float]:
    """Coördinaten uit Vec of tuple."""
    if hasattr(p, "x"):
        return (p.x, p.y)
    return (p[0], p[1])


def move_room(
    proposal: dict[str, list[Vec]], key: str, dx: float, dy: float
) -> dict[str, list[Vec]]:
    """Transleer één kamer; puur (invoer ongewijzigd). Accepteert Vec/tuple."""
    if key not in proposal:
        raise KeyError(f"move_room: onbekende knoop {key!r}")
    out: dict[str, list[Vec]] = {}
    for k, pts in proposal.items():
        if k == key:
            out[k] = [Vec(_xy(p)[0] + dx, _xy(p)[1] + dy) for p in pts]
        else:
            out[k] = [Vec(_xy(p)[0], _xy(p)[1]) for p in pts]
    return out


def swap_rooms(
    proposal: dict[str, list[Vec]], a: str, b: str
) -> dict[str, list[Vec]]:
    """Wissel de oorsprong van twee kamers (eigen maat behouden); puur."""
    for key in (a, b):
        if key not in proposal:
            raise KeyError(f"swap_rooms: onbekende knoop {key!r}")
    out: dict[str, list[Vec]] = {}
    for key, pts in proposal.items():
        if key == a:
            base = proposal[b]
        elif key == b:
            base = proposal[a]
        else:
            out[key] = [Vec(_xy(p)[0], _xy(p)[1]) for p in pts]
            continue
        w = max(_xy(p)[0] for p in pts) - min(_xy(p)[0] for p in pts)
        h = max(_xy(p)[1] for p in pts) - min(_xy(p)[1] for p in pts)
        ox = min(_xy(p)[0] for p in base)
        oy = min(_xy(p)[1] for p in base)
        out[key] = [Vec(ox, oy), Vec(ox + w, oy), Vec(ox + w, oy + h), Vec(ox, oy + h)]
    return out


def move_toward(
    proposal: dict[str, list[Vec]], key: str, target: str, extra: float = 0.0
) -> dict[str, list[Vec]]:
    """Schuif kamer *key* naar *target* tot raken (plus *extra* overlap); puur.

    Hoofdas = grootste bbox-tussenruimte (daar raken); nevensaansluiting =
    intervallen overlappend uitlijnen. Stopt bij het eerste obstakel (geen
    overlap met derden). Al rakend → ongewijzigd terug.
    """
    if key not in proposal:
        raise KeyError(f"move_toward: onbekende knoop {key!r}")
    if target not in proposal:
        raise KeyError(f"move_toward: onbekend doel {target!r}")
    ax0, ay0, ax1, ay1 = _bbox_of(proposal[key])
    bx0, by0, bx1, by1 = _bbox_of(proposal[target])
    dx_gap = max(0.0, ax0 - bx1, bx0 - ax1)
    dy_gap = max(0.0, ay0 - by1, by0 - ay1)
    if dx_gap <= 0 and dy_gap <= 0:
        return {k: list(pts) for k, pts in proposal.items()}
    if dx_gap >= dy_gap:
        dx = (bx1 - ax0 - extra) if ax0 >= bx1 - 1e-9 else -(ax1 - bx0 - extra)
        dy = (by0 + by1) / 2.0 - (ay0 + ay1) / 2.0
    else:
        dy = (by1 - ay0 - extra) if ay0 >= by1 - 1e-9 else -(ay1 - by0 - extra)
        dx = (bx0 + bx1) / 2.0 - (ax0 + ax1) / 2.0
    others = [proposal[k] for k in proposal if k not in (key, target)]
    step_dx, step_dy = dx / 8.0, dy / 8.0
    best = (0.0, 0.0)
    for i in range(1, 9):
        cand = (ax0 + step_dx * i, ay0 + step_dy * i, ax1 + step_dx * i, ay1 + step_dy * i)
        blocked = False
        for pts in others:
            ox0 = min(_xy(p)[0] for p in pts)
            oy0 = min(_xy(p)[1] for p in pts)
            ox1 = max(_xy(p)[0] for p in pts)
            oy1 = max(_xy(p)[1] for p in pts)
            if not (
                cand[2] <= ox0 + 1e-9
                or cand[0] >= ox1 - 1e-9
                or cand[3] <= oy0 + 1e-9
                or cand[1] >= oy1 - 1e-9
            ):
                blocked = True
                break
        if blocked:
            break
        best = (step_dx * i, step_dy * i)
    return move_room(proposal, key, *best)
