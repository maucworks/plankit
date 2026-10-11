# This file was generated with the assistance of an AI coding tool.
"""Generatie: PvE → skelet.

Een coarse voorstel (welke ruimte waar, als rechthoek) wordt gerealiseerd als
een :class:`PlanarSubdivision`. De stub :func:`propose_layout` legt ruimten in
een strip; een echte LLM kan hier een slimmer voorstel leveren (nabuurschap,
verkeersstrategie) met dezelfde interface.
"""

from __future__ import annotations

from plankit.conform import ConformanceReport, conform
from plankit.operators import layout_row, propose_magnet
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram
from plankit.quality import adjacency_gaps, fill_ratio

_EPS = 1e-6


def _xy(p) -> tuple[float, float]:
    if hasattr(p, "x"):
        return (p.x, p.y)
    return (p[0], p[1])


def propose_layout(program: RoomProgram, depth: float = 4.0) -> dict:
    """Coarse stub: leg niet-exterieure ruimten in een strip.

    Bepaalt per ruimte een rechthoek op basis van ``area_min``. Dit is de plek
    waar een echte LLM zijn nabuurschap-/verkeersstrategie kwijt kan; zie ook
    :func:`plankit.operators.propose_magnet` voor een deterministische
    contact-gedreven strategie.
    """
    keys = [k for k in program.nodes if not program.nodes[k].exterior]
    return layout_row(program, keys, x0=0.0, y0=0.0, depth=depth, gap=0.0)


def generate(
    program: RoomProgram,
    proposal: dict | None = None,
    strategy: str = "row",
    seed: int = 0,
    min_widths: dict[str, float] | None = None,
) -> PlanarSubdivision:
    """Bouw het skelet uit het PvE.

    ``proposal`` is ``{room_key: [punten...]}`` (rechthoeken). Zonder proposal
    bepaalt ``strategy`` het voorstel: ``"row"`` (strip, default; negeert
    ``seed``) of ``"magnet"`` (contact-gedreven compositie met ``seed``).
    ``min_widths`` gaat naar de magnet-vormkeuze. ``door``-kanten uit het PvE
    worden op de gedeelde edges gemarkeerd; paren zonder gedeelde edge worden
    overgeslagen (zie :func:`plankit.conform.conform` voor rapportage).
    """
    if proposal is None:
        if strategy == "magnet":
            proposal = propose_magnet(program, seed=seed, min_widths=min_widths)
        elif strategy == "row":
            proposal = propose_layout(program)
        else:
            raise ValueError(f"generate: onbekende strategy {strategy!r}")

    segments = []
    for pts in proposal.values():
        n = len(pts)
        for i in range(n):
            segments.append((pts[i], pts[(i + 1) % n]))
    sd = PlanarSubdivision.from_centerlines(segments)

    face_by_room: dict[str, int] = {}
    best: dict[str, tuple[float, int]] = {}
    for fid in sd.bounded_faces():
        area = sd.face_area(fid)
        if area <= _EPS:
            continue  # splinter-face uit de noding krijgt geen label
        pts = sd.face_vertices(fid)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        for key, rect in proposal.items():
            xs = [_xy(p)[0] for p in rect]
            ys = [_xy(p)[1] for p in rect]
            if min(xs) - _EPS < cx < max(xs) + _EPS and min(ys) - _EPS < cy < max(ys) + _EPS:
                if key not in best or area > best[key][0]:
                    best[key] = (area, fid)
                break
    face_by_room = {key: fid for key, (_, fid) in best.items()}

    for key, fid in face_by_room.items():
        sd.faces[fid].label = key

    for edge in program.edges:
        if edge.kind != "door":
            continue
        fa = face_by_room.get(edge.a)
        fb = face_by_room.get(edge.b)
        if fa is not None and fb is not None and sd.shared_edge(fa, fb) is not None:
            sd.mark_edge(fa, fb, "door")
    return sd


def select_best(
    program: RoomProgram,
    sds: list[PlanarSubdivision],
    boundary: list[tuple[float, float]] | None = None,
    min_widths: dict[str, float] | None = None,
) -> int:
    """Index van het beste skelet: eerst `conform.ok`, dan minste violations,
    dan minste missing, dan kleinste adjacency-gaps-som (MFP-T), dan hoogste
    fill_ratio (MFP-G; alleen met boundary). Deterministisch (eerste bij gelijk).
    """
    if not sds:
        raise ValueError("select_best: geen varianten om uit te kiezen")
    best, best_key = 0, None
    for i, sd in enumerate(sds):
        report = conform(sd, program, boundary=boundary, min_widths=min_widths)
        gaps = sum(adjacency_gaps(sd, program).values())
        fill = fill_ratio(sd, boundary) if boundary is not None else 0.0
        key = (report.ok, -len(report.violated), -len(report.missing), -gaps, fill)
        if best_key is None or key > best_key:
            best_key, best = key, i
    return best


def generate_many(
    program: RoomProgram,
    strategy: str = "magnet",
    seeds: range = range(10),
    store=None,
    min_widths: dict[str, float] | None = None,
    boundary: list[tuple[float, float]] | None = None,
) -> tuple[PlanarSubdivision, ConformanceReport]:
    """Genereer per seed een variant, bewaar alle in de store, geef de beste terug.

    Labels als ``"{strategy}/s{seed}"`` (roots, parent_id None). Geeft
    ``(skelet, ConformanceReport)`` van de winnaar volgens :func:`select_best`.
    Zonder store alleen genereren + selecteren.
    """
    sds: list[PlanarSubdivision] = []
    for n, seed in enumerate(seeds):
        sd = generate(program, strategy=strategy, seed=seed, min_widths=min_widths)
        sds.append(sd)
        if store is not None:
            from plankit.store import make_variant

            store.add(make_variant(sd, program, step=n, label=f"{strategy}/s{seed}"))
    best = select_best(program, sds, boundary=boundary, min_widths=min_widths)
    return sds[best], conform(sds[best], program, boundary=boundary, min_widths=min_widths)


def revise(
    program: RoomProgram,
    proposal: dict,
    rounds: int = 3,
    boundary: list[tuple[float, float]] | None = None,
    min_widths: dict[str, float] | None = None,
) -> tuple[dict, ConformanceReport]:
    """Revise-lus (mechanisch): repareer violated deur/`wall`-kanten per mutatie.

    Per ronde: voor elke geschonden vereiste kant de kamer naar de partner
    schuiven (`move_toward`) plus het paar swappen; alles genereren en met
    :func:`select_best` kiezen. Monotoon: nooit slechter dan de invoer.
    Geeft (voorstel, rapport) van de winnaar.
    """
    from plankit.operators import move_toward, swap_rooms

    best_prop = {k: list(v) for k, v in proposal.items()}
    best_sd = generate(program, proposal=best_prop)
    best_report = conform(best_sd, program, boundary=boundary, min_widths=min_widths)
    keys = set(best_prop)
    for _ in range(rounds):
        cands: list[dict] = [best_prop]
        violated = [v for v in best_report.violated if ":door" in v or ":wall" in v]
        for label in violated:
            parts = label.split(":")
            if len(parts) != 3:
                continue
            _, pair, _ = parts
            found = None
            for a in keys:
                if pair.startswith(a + "-") and pair[len(a) + 1 :] in keys:
                    found = (a, pair[len(a) + 1 :])
                    break
                if pair.endswith("-" + a) and pair[: -(len(a) + 1)] in keys:
                    found = (pair[: -(len(a) + 1)], a)
                    break
            if found is None:
                continue
            a, b = found
            cands.append(move_toward(best_prop, a, b))
            cands.append(move_toward(best_prop, b, a))
            cands.append(swap_rooms(best_prop, a, b))
        sds = [generate(program, proposal=c) for c in cands]
        idx = select_best(program, sds, boundary=boundary, min_widths=min_widths)
        best_prop = cands[idx]
        best_sd = sds[idx]
        best_report = conform(best_sd, program, boundary=boundary, min_widths=min_widths)
        if best_report.ok:
            break
    return best_prop, best_report
