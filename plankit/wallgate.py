# This file was generated with the assistance of an AI coding tool.
"""plankit.wallgate — the evaluation harness on solved wall graphs.

The wall-graph track has its own geometry contract: strokes, rooms as
noded faces, per-face tags. The harness (``conform`` + ``quality``) was
written against ``PlanarSubdivision`` + ``Face.label``, one label per
face. ``wallgate`` is the projection layer between the two, so a solved
drawing is scored by the *same* gate that used to score the retired
strip generator — no second, weaker judge.

Projection rules, and why they are what they are:

- A face tag resolves its item patterns (``slaap.*``, ``B*-woon``) against
  the PvE keys. A face covering **exactly one** key is labelled with that
  key and handed to ``conform`` unchanged: area band, min width and
  boundary checks are then exact.
- A face covering **several** keys is an *ensemble* (a dwelling with a
  bleeding kitchen; one cell holding a wet cluster). ``conform`` cannot
  split it, so those keys are demoted to ``unconstrained`` for the run
  and judged as an **aggregate**: the face area must fall inside the sum
  of the keys' bands. That is deliberately weaker than a per-item check.
  The per-item split needs open-edge accounting (not built yet), so the
  weakness is reported as a note instead of being papered over.
- Doors: a program ``door`` edge is satisfied only where two labelled
  faces share a noded edge whose covering stroke is tagged ``open`` or
  ``access`` — a passage the author actually drew. A shared *wall* is not
  a door yet (door slots with min widths are not built), so the gate
  reports that gap instead of hiding it.
- Metrics keyed by face id come from ``quality`` unchanged; ``labels``
  maps face id → program key so the canvas can show names.

Everything here is a pure function of (draft, solved junctions,
program): same inputs, same report, byte for byte.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from plankit import quality
from plankit.conform import conform
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram
from plankit.templates import pattern_matches
from plankit.wallgraph import EPS_AREA, FACE_MATCH_TOL, WallGraphDraft

OPENING_KINDS = ("open", "access", "door")
_TOL = 1e-6
_PT_TOL = 1e-6  # m; a stroke must pass within this of the shared-edge midpoint


def _dm(v: float) -> int:
    """Metres → decimetres, identical to :func:`plankit.wallsolve._dm`."""
    return int(round(v * 10))


def _junction_map(junctions: Any) -> Dict[Tuple[int, int], Tuple[float, float]]:
    """Solve-report ``junctions`` (or a plain mapping) → dm-key → metres."""
    out: Dict[Tuple[int, int], Tuple[float, float]] = {}
    if not junctions:
        return out
    if isinstance(junctions, dict):
        pairs = [(k, v) for k, v in junctions.items()]
    else:
        pairs = [(j["orig"], j["solved"]) for j in junctions]
    for orig, solved in pairs:
        if isinstance(orig, dict):
            ox, oy = orig["x"], orig["y"]
        elif isinstance(orig, (list, tuple)) and len(orig) == 2:
            ox, oy = orig
        else:
            ox, oy = orig[0], orig[1]
        out[(_dm(ox), _dm(oy))] = (float(solved[0]), float(solved[1]))
    return out


def solved_strokes(
    draft: WallGraphDraft, junctions: Any = None
) -> List[Dict[str, float]]:
    """The draft's strokes with solved junction coordinates substituted.

    ``junctions`` is the solve report's junction list (``orig``/
    ``solved``); junctions absent from it keep their drawn coordinate, so
    the gate also runs on a raw, unsolved draft.
    """
    jmap = _junction_map(junctions)
    out: List[Dict[str, float]] = []
    for s in draft.segments:
        seg = dict(s)
        for kx, ky in (("x0", "y0"), ("x1", "y1")):
            solved = jmap.get((_dm(s[kx]), _dm(s[ky])))
            if solved is not None:
                seg[kx], seg[ky] = solved
        out.append({k: round(float(seg[k]), 3) for k in ("x0", "y0", "x1", "y1")})
    return out


def _nearest_tag(
    drawn: List[Dict[str, Any]], cx: float, cy: float, tol: float
) -> Optional[Dict[str, Any]]:
    """The drawn face whose tag follows this face (nearest centroid)."""
    best: Optional[Dict[str, Any]] = None
    best_d = tol
    for f in drawn:
        c = f.get("centroid") or [0.0, 0.0]
        d = math.hypot(c[0] - cx, c[1] - cy)
        if d < best_d:
            best, best_d = f, d
    return best


def _resolve_keys(tag: Optional[Dict[str, Any]], program: RoomProgram) -> List[str]:
    """PvE keys covered by a face tag's item patterns (exterior skipped)."""
    if not tag:
        return []
    keys: List[str] = []
    for key, space in program.nodes.items():
        if getattr(space, "exterior", False):
            continue
        if any(pattern_matches(key, pat) for pat in tag.get("items", [])):
            keys.append(key)
    return sorted(keys)


def open_strokes(
    draft: WallGraphDraft, junctions: Any = None
) -> List[Dict[str, float]]:
    """The ``open``/``access`` strokes *in their solved position*.

    The passage test runs on solved geometry: a shared noded edge lies on
    a solved stroke by construction, while the drawn strokes may sit a
    few decimetres away after the rubber-band.
    """
    return [
        s
        for i, s in enumerate(solved_strokes(draft, junctions))
        if draft.edges.get(i, "wall") in OPENING_KINDS
    ]


def _opening_at(strokes: List[Dict[str, float]], pt: Tuple[float, float]) -> bool:
    """True when an ``open``/``access`` stroke passes through ``pt``."""
    px, py = pt
    for s in strokes:
        ax, ay, bx, by = s["x0"], s["y0"], s["x1"], s["y1"]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = ((px - ax) * dx + (py - ay) * dy) / L2
        if t < -_PT_TOL or t > 1 + _PT_TOL:
            continue
        if math.hypot(px - (ax + t * dx), py - (ay + t * dy)) < 1e-3:
            return True
    return False


def shared_edges(sd: PlanarSubdivision, fa: int, fb: int) -> List[int]:
    """Every half-edge of face ``fa`` whose twin lies on face ``fb``.

    ``PlanarSubdivision.shared_edge`` returns the first match only, which
    is not enough here: two rooms separated by a wall with a door in it
    share three noded edges (wall, passage, wall) and the passage must be
    found among all of them.
    """
    return [
        he
        for he in sd.face_half_edges(fa)
        if sd.half_edges[he].twin >= 0
        and sd.half_edges[sd.half_edges[he].twin].face == fb
    ]


def doors(
    sd: PlanarSubdivision,
    faces_by_key: Dict[str, List[int]],
    program: RoomProgram,
    openings: List[Dict[str, float]],
) -> List[Dict[str, Any]]:
    """Realise program ``door`` edges on the drawing and report each one.

    A key can live in an ensemble region, so doors are resolved between
    the *regions* holding each key, not between single faces. Per program
    door edge:

    ``drawn``        the two regions share a noded edge covered by a
                     drawn ``open``/``access`` stroke — a passage. The
                     edge is marked on the skeleton so the circulation
                     metrics (``access_graph``, ``escape_depth``) see it.
    ``same_region``  both keys sit in one region: no wall between them,
                     so there is nothing to put a door in.
    ``blocked``      the regions touch across a solid wall only — a real
                     gap, since door slots (per-edge openings with min
                     widths) are not built yet.
    ``separated``    the regions do not touch at all.
    ``unplaced``     one of the keys has no region.
    """
    out: List[Dict[str, Any]] = []
    for edge in program.edges:
        if edge.kind != "door":
            continue
        fa_list, fb_list = faces_by_key.get(edge.a, []), faces_by_key.get(edge.b, [])
        label = f"edge:{edge.a}-{edge.b}:door"
        entry: Dict[str, Any] = {
            "label": label,
            "a": edge.a,
            "b": edge.b,
            "required": edge.required,
            "status": "unplaced",
            "faces": [],
        }
        if not fa_list or not fb_list:
            out.append(entry)
            continue
        if set(fa_list) & set(fb_list):
            entry["status"] = "same_region"
            entry["faces"] = sorted(set(fa_list) & set(fb_list))
            out.append(entry)
            continue
        found = blocked = separated = False
        pairs: List[Tuple[int, int]] = []
        for fa in fa_list:
            for fb in fb_list:
                if fa == fb:
                    continue
                hes = shared_edges(sd, fa, fb)
                if not hes:
                    separated = True
                    continue
                pairs.append((fa, fb))
                for he in hes:
                    a = sd.vertices[sd.half_edges[he].origin]
                    b = sd.vertices[sd.half_edges[sd.half_edges[he].next].origin]
                    mid = ((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)
                    if _opening_at(openings, mid):
                        sd.half_edges[he].kind = "door"
                        sd.half_edges[sd.half_edges[he].twin].kind = "door"
                        found = True
                    else:
                        blocked = True
        entry["faces"] = [list(p) for p in pairs]
        if found:
            entry["status"] = "drawn"
        elif blocked:
            entry["status"] = "blocked"
        elif separated:
            entry["status"] = "separated"
        else:
            entry["status"] = "unplaced"
        out.append(entry)
    return out


def _demote(program: RoomProgram, keys: Sequence[str]) -> RoomProgram:
    """A program view where ``keys`` are preferred, not required.

    Ensemble faces cover those keys, but ``conform`` binds one label per
    face and would report them missing — the ensemble aggregate check
    judges them instead.
    """
    demoted = set(keys)
    nodes = {
        k: (dataclasses.replace(s, required=False) if k in demoted else s)
        for k, s in program.nodes.items()
    }
    return RoomProgram(nodes=nodes, edges=list(program.edges))


def project(
    draft: WallGraphDraft,
    program: RoomProgram,
    junctions: Any = None,
    tol: Optional[float] = None,
) -> Tuple[PlanarSubdivision, List[Dict[str, Any]]]:
    """Solved wall graph → labelled DCEL skeleton + per-face tag map.

    Faces are matched to tags through the *drawn* noding (tags follow the
    drawing, not vertex noise). A face covering one PvE key carries that
    key as ``Face.label``; an ensemble face stays unlabelled and is
    returned in the tag map for the aggregate check.
    """
    strokes = solved_strokes(draft, junctions)
    if not strokes:
        raise ValueError("wall gate: draft has no strokes")
    sd = PlanarSubdivision.from_centerlines(
        [((s["x0"], s["y0"]), (s["x1"], s["y1"])) for s in strokes]
    )
    drawn = draft.noded_faces()
    tol = FACE_MATCH_TOL if tol is None else tol
    face_tags: List[Dict[str, Any]] = []
    for fid in sd.bounded_faces():
        area = sd.face_area(fid)
        if area < EPS_AREA:
            continue
        cx, cy = sd.face_centroid(fid)
        tag = _nearest_tag(drawn, cx, cy, tol)
        keys = _resolve_keys(tag, program)
        label = keys[0] if len(keys) == 1 else None
        sd.faces[fid].label = label
        face_tags.append(
            {
                "index": fid,
                "area": round(area, 3),
                "centroid": [round(cx, 3), round(cy, 3)],
                "tag_key": (tag or {}).get("key"),
                "label": (tag or {}).get("label", ""),
                "keys": keys,
                "label_key": label,
                "ensemble": len(keys) > 1,
            }
        )
    doors(sd, faces_by_key(face_tags), program, open_strokes(draft, junctions))
    return sd, face_tags


def faces_by_key(face_tags: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """PvE key → the face ids of the regions that hold it (ensembles too)."""
    out: Dict[str, List[int]] = {}
    for f in face_tags:
        for k in f["keys"]:
            out.setdefault(k, []).append(f["index"])
    return {k: sorted(set(v)) for k, v in out.items()}


def ensemble_checks(
    face_tags: List[Dict[str, Any]], program: RoomProgram
) -> List[Dict[str, Any]]:
    """Aggregate area-band check per ensemble face (Σ key bands)."""
    out: List[Dict[str, Any]] = []
    for f in face_tags:
        if not f["ensemble"]:
            continue
        los = [program.nodes[k].area_min for k in f["keys"]]
        his = [program.nodes[k].area_max for k in f["keys"]]
        lo = sum(los) if all(v is not None for v in los) else None
        hi = sum(his) if all(v is not None for v in his) else None
        area = f["area"]
        ok = (lo is None or area >= lo - _TOL) and (hi is None or area <= hi + _TOL)
        out.append(
            {
                "tag": f["tag_key"],
                "keys": f["keys"],
                "area": area,
                "band": [lo, hi],
                "ok": ok,
            }
        )
    return out


def _access_root(
    face_tags: List[Dict[str, Any]], program: RoomProgram
) -> Optional[int]:
    """The face the circulation depth is measured from: core, then entrance."""
    for attr in ("core", "entrance"):
        for f in face_tags:
            key = f["label_key"]
            if key and getattr(program.nodes[key], attr, False):
                return f["index"]
    return None


def _component_count(g: Any, nodes: List[str]) -> int:
    from collections import deque

    left = set(nodes)
    count = 0
    while left:
        count += 1
        start = left.pop()
        queue: deque[str] = deque([start])
        while queue:
            cur = queue.popleft()
            for nbr in g.neighbors(cur):
                if nbr in left:
                    left.discard(nbr)
                    queue.append(nbr)
    return count


def access_components(sd: PlanarSubdivision, root: Optional[int]) -> Dict[str, Any]:
    """Connected components of the door graph, seen from ``root``.

    ``quality.circulation_depth`` measures depth from one root only, so a
    drawing whose rooms sit in a second component is *invisible* there.
    This is the honest complement: how many components exist, and which
    faces the root cannot reach.
    """
    from collections import deque

    g = quality.access_graph(sd)
    nodes = list(g.nodes())
    if not nodes:
        return {"components": 0, "root": None, "unreachable": []}
    root_key = str(root) if root is not None and str(root) in nodes else nodes[0]
    seen = {root_key}
    queue: deque[str] = deque([root_key])
    while queue:
        cur = queue.popleft()
        for nbr in g.neighbors(cur):
            if nbr not in seen:
                seen.add(nbr)
                queue.append(nbr)
    rest = [n for n in nodes if n not in seen]
    return {
        "components": 1 + _component_count(g, rest),
        "root": root_key,
        "unreachable": sorted(rest),
    }


def envelope_polygon(draft: WallGraphDraft) -> List[Tuple[float, float]]:
    """The draft envelope as a CCW polygon (the harness boundary)."""
    e = draft.envelope
    return [(e.x0, e.y0), (e.x1, e.y0), (e.x1, e.y1), (e.x0, e.y1)]


def gate(
    draft: WallGraphDraft,
    program: RoomProgram,
    junctions: Any = None,
    min_widths: Optional[Dict[str, float]] = None,
    boundary: Optional[List[Tuple[float, float]]] = None,
    tol: Optional[float] = None,
) -> Dict[str, Any]:
    """Score a (solved) wall-graph drawing against a PvE program.

    Returns a JSON-safe report: ``conform`` verdicts, per-face tag map,
    ensemble aggregate checks, the ``quality`` metrics and notes about
    what the projection cannot see (per-item ensembles, doors without a
    drawn passage). ``status`` is ``"ok"`` only when ``conform`` passes
    *and* every ensemble aggregate lands in its summed band.
    """
    notes: List[str] = []
    sd, face_tags = project(draft, program, junctions, tol=tol)
    ensembles = ensemble_checks(face_tags, program)
    exclusive = {f["label_key"] for f in face_tags if f["label_key"]}
    demoted = [
        k for f in face_tags if f["ensemble"] for k in f["keys"] if k not in exclusive
    ]
    report = conform(
        sd,
        _demote(program, demoted),
        boundary=envelope_polygon(draft) if boundary is None else boundary,
        min_widths=min_widths,
    )
    door_report = doors(
        sd, faces_by_key(face_tags), program, open_strokes(draft, junctions)
    )
    labels = {
        str(f["index"]): (f["label_key"] or f["tag_key"] or "?") for f in face_tags
    }
    root = _access_root(face_tags, program)
    root_key = str(root) if root is not None else None
    comps = access_components(sd, root)
    metrics: Dict[str, Any] = {
        "labels": labels,
        "facade_ratio": round(quality.facade_ratio(sd), 4),
        "is_enfilade": quality.is_enfilade(sd),
        "aspect_ratios": {
            labels.get(k, k): round(v, 3) if math.isfinite(v) else None
            for k, v in quality.aspect_ratios(sd).items()
        },
        "facade_lengths": {
            labels.get(k, k): round(v, 3) for k, v in quality.facade_lengths(sd).items()
        },
        "circulation_depth": {
            labels.get(k, k): v
            for k, v in quality.circulation_depth(sd, root_key).items()
        },
        "access_components": {
            "components": comps["components"],
            "root": labels.get(str(comps["root"]), comps["root"]),
            "unreachable": [labels.get(k, k) for k in comps["unreachable"]],
        },
        "escape_depth": {
            labels.get(k, k): v for k, v in quality.escape_depth(sd, program).items()
        },
    }
    try:
        metrics["fill_ratio"] = round(
            quality.fill_ratio(
                sd, envelope_polygon(draft) if boundary is None else boundary
            ),
            4,
        )
        metrics["adjacency_gaps"] = {
            f"{labels.get(a, a)}|{labels.get(b, b)}": round(v, 3)
            for (a, b), v in quality.adjacency_gaps(sd, program).items()
        }
    except ValueError as exc:  # boundary without area
        metrics["fill_ratio"] = None
        metrics["adjacency_gaps"] = {}
        notes.append(f"metrics: {exc}")

    untagged = [f for f in face_tags if not f["keys"]]
    if untagged:
        notes.append(
            "faces without a PvE tag: "
            + ", ".join(str(f["tag_key"] or f["index"]) for f in untagged)
        )
    if demoted:
        notes.append(
            "ensemble faces (one region, several PvE keys) are judged as an "
            "aggregate only — per-item split needs open-edge accounting: "
            + ", ".join(sorted(set(demoted)))
        )
    counts = {
        s: sum(1 for d in door_report if d["status"] == s)
        for s in ("drawn", "same_region", "blocked", "separated", "unplaced")
    }
    blocked_doors = [d for d in door_report if d["status"] == "blocked"]
    separated_doors = [d for d in door_report if d["status"] == "separated"]
    if blocked_doors:
        notes.append(
            f"{len(blocked_doors)} program door(s) between touching regions have "
            "no drawn open/access stroke — a shared wall is not a door until "
            "door slots exist: " + ", ".join(d["label"] for d in blocked_doors)
        )
    if separated_doors:
        notes.append(
            "program door(s) between regions that do not touch: "
            + ", ".join(d["label"] for d in separated_doors)
        )
    door_failures = [
        d
        for d in door_report
        if d["required"] and d["status"] in ("blocked", "separated")
    ]
    out = {
        "status": "ok"
        if report.ok and all(e["ok"] for e in ensembles) and not door_failures
        else "violated",
        "conform": {
            "ok": report.ok,
            "satisfied": sorted(report.satisfied),
            "violated": sorted(report.violated),
            "missing": sorted(report.missing),
            "unconstrained": sorted(report.unconstrained),
            "missing_adj": {k: v for k, v in sorted(report.missing_adj.items())},
        },
        "faces": face_tags,
        "ensembles": ensembles,
        "metrics": metrics,
        "doors": {**counts, "edges": door_report, "failed": len(door_failures)},
        "notes": notes,
    }
    return out
