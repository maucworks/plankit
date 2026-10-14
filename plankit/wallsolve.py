# This file was generated with the assistance of an AI coding tool.
"""plankit.wallsolve — metric solver for drawn wall-graph templates.

The template is a *drawing* (fixed topology): rooms are the faces of
the wall graph, so rooms cannot overlap by construction and the only
question left is **metrics**: do the closed faces satisfy their area
bands. This module makes the drawing "breathe" to the bands:

- every distinct junction of the drawn strokes becomes two CP-SAT
  integer variables (X, Y in decimetres), free within ±2.5 m of the
  drawn coordinate (clamped to the envelope);
- each stroke keeps its drawn orientation class (horizontal strokes
  stay horizontal, verticals stay vertical), so an orthogonal drawing
  stays orthogonal;
- per drawn stroke the new length is held within [25%, 300%] of the
  drawn length (anti-sliver);
- per face the shoelace area — ``½|Σ x_i·y_{i+1} − x_{i+1}·y_i|`` in
  dm² — is constrained to the face tag's band in m² (×100). Faces
  without a tag only need ≥ 0.5 m² (non-degenerate);
- objective: least total junction displacement (L1) — the solved
  drawing is the *smallest nudge* of the author's sketch;
- deterministic: 1 worker, fixed seed.

After the solve the areas are **recomputed exactly in Python**
(shoelace on the solved coordinates) — the certificates are the
recomputed numbers, the model only steers the search. Crossings that
the noder creates where strokes cross without a drawn joint are
rejected: the sketch must split strokes explicitly at every crossing
(the ✂/vertex tools exist for that).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from plankit.wallgraph import WallGraphDraft

DISP_M = 2.5  # m; junction freedom around the drawn coordinate
SOLVE_SECONDS = 15.0  # s; budget (deterministic, single worker)
JEPS = 1e-6  # junction coordinate tolerance


def _dm(v: float) -> int:
    """Metres → decimetres (round-half-even at the drawn coordinates)."""
    return int(round(v * 10))


def _validate_orthogonal(draft: WallGraphDraft) -> List[str]:
    errs: List[str] = []
    for i, s in enumerate(draft.segments):
        dx, dy = abs(s["x1"] - s["x0"]), abs(s["y1"] - s["y0"])
        if dx > 1e-6 and dy > 1e-6:
            errs.append(f"segment:{i}:non-orthogonal")
    return errs


def _junction_map(draft: WallGraphDraft) -> Dict[Tuple[int, int], Tuple[float, float]]:
    """Distinct junction keys (dm tuples) → drawn metres coordinates."""
    j: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for s in draft.segments:
        for p in ((s["x0"], s["y0"]), (s["x1"], s["y1"])):
            key = (_dm(p[0]), _dm(p[1]))
            if key not in j:
                j[key] = (key[0] / 10.0, key[1] / 10.0)
    return j


def _face_loops(
    draft: WallGraphDraft,
    jmap: Dict[Tuple[int, int], Tuple[float, float]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Face loops of the noding as ordered junction-id lists.

    A noder vertex that is not a drawn junction means a stroke crossing
    without an explicit split — reported back to the sketch, not solved.
    """
    errors: List[str] = []
    faces: List[Dict[str, Any]] = []
    for face in draft.noded_faces():
        loop: List[Tuple[int, int]] = []
        ok = True
        for v in face["verts"]:
            key = (_dm(v[0]), _dm(v[1]))
            if key not in jmap:
                errors.append(
                    f"face:{face['index']}:unsplit-crossing at [{v[0]:.2f},{v[1]:.2f}]"
                    " — split the stroke there (✂/vertex tool)"
                )
                ok = False
                break
            loop.append(key)
        if ok and len(loop) >= 3:
            faces.append(
                {
                    "index": face["index"],
                    "loop": loop,
                    "tag": face if face.get("matched") else None,
                }
            )
    return faces, errors


def solve_areas(
    draft: WallGraphDraft,
    seconds: float = SOLVE_SECONDS,
    hints: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Rubber-band the drawing so every face area lands in its band.

    ``hints`` (interactive mode) warm-start the search: a list of
    ``{"orig": [x, y], "solved": [x, y]}`` from the previous solution —
    the next solve starts from the last feasible sketch instead of
    reset search, which is what makes solve-per-drag affordable. Note
    the certificate semantics stay with the exact post-check; a small
    ``seconds`` budget makes the *interactive* result advisory
    (best-found), while the full-budget button solve is the certified
    one.

    Returns a report dict: status (``solved``/``infeasible``/``budget``/
    ``rejected``), recomputed faces (exact shoelace areas per solved
    coordinates), junction moves, wall time. Deterministic for a fixed
    budget.
    """
    t0 = time.time()
    ortho_errors = _validate_orthogonal(draft)
    if ortho_errors:
        return {
            "status": "rejected",
            "errors": ortho_errors
            + ["solve requires orthogonal strokes (90° drawing)"],
        }

    jmap = _junction_map(draft)
    faces, face_errors = _face_loops(draft, jmap)
    if face_errors or not faces:
        return {
            "status": "rejected",
            "errors": face_errors or ["no bounded faces to solve"],
        }

    ex, ey = draft.envelope.x1, draft.envelope.y1

    # -- helper grid lines: parallel-with-offset to the master (hard). --
    # master = axis + drawn position (fixed constant); each derived line
    # = parallel-with-offset: line coordinate = master pos + offset.
    # Bindings tie drawn junctions (by drawn dm-coordinate) onto a line:
    # the junction's line-axis coordinate equals the line position.
    helpers = draft.helpers or {}
    master = helpers.get("master")
    line_pos: Dict[str, int] = {}
    helper_errors: List[str] = []
    if master:
        mpos = master.get("pos", 0.0)
        for ln in helpers.get("lines", []):
            off = ln.get("offset")
            if not isinstance(off, (int, float)) or not isinstance(mpos, (int, float)):
                helper_errors.append(f"helper:{ln.get('id', '?')}:missing-offset")
                continue
            pos_dm = _dm(mpos + float(off))
            inside = (
                0 <= pos_dm <= _dm(ex)
                if master.get("axis") == "vertical"
                else 0 <= pos_dm <= _dm(ey)
            )
            if not inside:
                helper_errors.append(f"helper:{ln.get('id', '?')}:outside-envelope")
                continue
            line_pos[str(ln.get("id"))] = pos_dm
    if helper_errors:
        return {"status": "rejected", "errors": helper_errors}

    # anchored junctions: every incident *drawn* stroke is facade-tagged
    # (building-outline corners) — those may not move. A junction that a
    # facade stroke merely *passes through* is not drawn on that stroke,
    # so interior divider/facade crossings stay free to move along it.
    incident_kinds: Dict[Tuple[int, int], List[str]] = {}
    for i, stroke in enumerate(draft.segments):
        kind = draft.edges.get(i, "wall")
        for p in ((stroke["x0"], stroke["y0"]), (stroke["x1"], stroke["y1"])):
            incident_kinds.setdefault((_dm(p[0]), _dm(p[1])), []).append(kind)
    anchored = {
        key
        for key, kinds in incident_kinds.items()
        if kinds and all(k == "facade" for k in kinds)
    }
    # Sealed feet: an interior stroke that *ends* on the envelope seals a
    # room against it. Its foot junction may slide along the outline but
    # may not leave it — otherwise the stroke lifts off the facade, the two
    # rooms merge around the gap, and the model reports a face the architect
    # never drew. Outline corners are already pinned by `anchored`.
    ex0, ey0, ex1, ey1 = (
        draft.envelope.x0,
        draft.envelope.y0,
        draft.envelope.x1,
        draft.envelope.y1,
    )
    sealed: Dict[Tuple[int, int], set] = {}
    for i, stroke in enumerate(draft.segments):
        if draft.edges.get(i, "wall") == "facade":
            continue
        for px, py in ((stroke["x0"], stroke["y0"]), (stroke["x1"], stroke["y1"])):
            axes = sealed.setdefault((_dm(px), _dm(py)), set())
            if abs(px - ex0) < JEPS or abs(px - ex1) < JEPS:
                axes.add("x")
            if abs(py - ey0) < JEPS or abs(py - ey1) < JEPS:
                axes.add("y")

    m = cp_model.CpModel()
    X: Dict[Tuple[int, int], Any] = {}
    Y: Dict[Tuple[int, int], Any] = {}
    absx: Dict[Tuple[int, int], Any] = {}
    absy: Dict[Tuple[int, int], Any] = {}
    move_terms: List[Any] = []
    bindings = list(draft.bindings or [])
    assumption_lits: List[Tuple[Any, str]] = []  # (literal, human-readable)
    for key in sorted(jmap):
        ox, oy = jmap[key]
        binding = next(
            (
                b
                for b in bindings
                if b.get("line") in line_pos
                and (_dm(b["junction"]["x"]), _dm(b["junction"]["y"])) == key
            ),
            None,
        )
        if key in anchored:
            X[key] = m.NewIntVar(_dm(ox), _dm(ox), f"x{key}")
            Y[key] = m.NewIntVar(_dm(oy), _dm(oy), f"y{key}")
            continue
        X[key] = m.NewIntVar(
            max(0, _dm(max(0.0, ox - DISP_M))),
            min(_dm(ex), _dm(min(ex, ox + DISP_M))),
            f"x{key}",
        )
        Y[key] = m.NewIntVar(
            max(0, _dm(max(0.0, oy - DISP_M))),
            min(_dm(ey), _dm(min(ey, oy + DISP_M))),
            f"y{key}",
        )
        absx[key] = m.NewIntVar(0, int(DISP_M * 10), f"dx{key}")
        absy[key] = m.NewIntVar(0, int(DISP_M * 10), f"dy{key}")
        m.AddAbsEquality(absx[key], X[key] - _dm(ox))
        m.AddAbsEquality(absy[key], Y[key] - _dm(oy))
        # least-L1 objective: every movable junction pays for its
        # displacement, so the solve settles as close to the drawn
        # sketch as the area bands allow
        move_terms.extend([absx[key], absy[key]])
        for axis in sealed.get(key, ()):  # a stroke foot stays on the outline
            if axis == "x":
                m.Add(X[key] == _dm(ex0 if abs(ox - ex0) < JEPS else ex1))
            else:
                m.Add(Y[key] == _dm(ey0 if abs(oy - ey0) < JEPS else ey1))
        if binding:
            # helper-grid binding: the junction's line-axis coordinate
            # equals the line position (vertical line pins X, horizontal
            # pins Y); wrapped in an assumption literal so the UNSAT
            # core can name the conflicting binding.
            lv = line_pos[str(binding.get("line"))]
            axis = (master or {}).get("axis")
            lit = m.NewBoolVar(f"bind{key[1]}x{key[0]}_{binding.get('line')}")
            assumption_lits.append(
                (
                    lit,
                    f"junction ({jmap[key][0]:.1f},{jmap[key][1]:.1f}) on line '{binding.get('line')}'",
                )
            )
            if axis == "vertical":
                m.Add(X[key] == lv).OnlyEnforceIf(lit)
            else:
                m.Add(Y[key] == lv).OnlyEnforceIf(lit)

    # strokes keep their orientation class and their length window
    for i, s in enumerate(draft.segments):
        a = (_dm(s["x0"]), _dm(s["y0"]))
        b = (_dm(s["x1"]), _dm(s["y1"]))
        horiz = abs(s["y1"] - s["y0"]) < 1e-6
        if horiz:
            m.Add(Y[a] == Y[b])
            len0 = int(round(abs(s["x1"] - s["x0"]) * 10))
        else:
            m.Add(X[a] == X[b])
            len0 = int(round(abs(s["y1"] - s["y0"]) * 10))
        lv = m.NewIntVar(
            max(2, int(round(len0 * 0.25))), int(round(len0 * 3.0)), f"len{i}"
        )
        m.AddAbsEquality(lv, X[a] - X[b] if horiz else Y[a] - Y[b])

    # face areas: shoelace in dm² via per-corner products
    PROD = ex * ey * 100  # dm² of the largest dx·dy term (x ≤ ex dm, y ≤ ey dm)
    for fi, f in enumerate(faces):
        terms: List[Any] = []
        n = len(f["loop"])
        for ci in range(n):
            j1, j2 = f["loop"][ci], f["loop"][(ci + 1) % n]
            t1 = m.NewIntVar(-PROD, PROD, f"det{fi}a{ci}")
            m.AddMultiplicationEquality(t1, [X[j1], Y[j2]])
            t2 = m.NewIntVar(-PROD, PROD, f"det{fi}b{ci}")
            m.AddMultiplicationEquality(t2, [X[j2], Y[j1]])
            terms.append(t1 - t2)
        ssum = m.NewIntVar(-PROD * n, PROD * n, f"sum{fi}")
        m.Add(sum(terms) == ssum)
        # a2 = |shoelace| = 2 × (face area in dm²), so its ceiling is 2×
        # the envelope's dm² (a face can span the whole storey) — capping
        # it at PROD silently made faces larger than half the storey
        # unsatisfiable.
        a2 = m.NewIntVar(0, 2 * int(round(ex * ey * 100)), f"area{fi}")
        m.AddAbsEquality(a2, ssum)
        tag = f["tag"] or {}
        lo = tag.get("area_min")
        hi = tag.get("area_max")
        m.Add(a2 >= 2 * int(round((lo if lo is not None else 0.5) * 100)))
        if hi is not None:
            m.Add(a2 <= 2 * int(round(hi * 100)))

    # objective: least total junction displacement
    if move_terms:
        m.Minimize(sum(move_terms))

    if assumption_lits:
        m.AddAssumptions([lit for lit, _ in assumption_lits])

    # interactive warm start: previous solved coordinates as hints
    hint_pairs: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for h in hints or []:
        try:
            hint_pairs[(_dm(h["orig"][0]), _dm(h["orig"][1]))] = (
                float(h["solved"][0]),
                float(h["solved"][1]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    for key, (sx_, sy_) in sorted(hint_pairs.items()):
        if key in X:
            m.AddHint(X[key], _dm(sx_))
        if key in Y:
            m.AddHint(Y[key], _dm(sy_))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 1
    solver.parameters.max_time_in_seconds = seconds
    status = solver.Solve(m)
    if status == cp_model.INFEASIBLE and assumption_lits:
        core = solver.SufficientAssumptionsForInfeasibility()
        core = {v for v in solver.SufficientAssumptionsForInfeasibility()}
        conflicts = [
            label
            for lit, label in assumption_lits
            if lit.index in core  # lit.index is an int attribute in 9.15
        ]
        return {
            "status": "infeasible",
            "conflicts": conflicts,
            "errors": [
                "no coordinate assignment satisfies every tagged band/binding —"
                " the minimal conflicting set follows"
            ]
            + conflicts,
            "time": solver.WallTime(),
        }
    if status == cp_model.INFEASIBLE:
        return {
            "status": "infeasible",
            "errors": [
                "no coordinate assignment satisfies the bands — widen a band "
                "or make the sketch less tight"
            ],
            "time": solver.WallTime(),
        }
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        return {
            "status": "budget",
            "errors": [
                "no solved layout inside the time budget — "
                "retry, widen the bands, or split the drawing"
            ],
            "time": solver.WallTime(),
        }

    junctions = []
    for key in sorted(jmap):
        ox, oy = jmap[key]
        junctions.append(
            {
                "orig": [ox, oy],
                "solved": [solver.Value(X[key]) / 10.0, solver.Value(Y[key]) / 10.0],
            }
        )
    solved_xy = {(j["orig"][0], j["orig"][1]): j["solved"] for j in junctions}

    # exact recomputation (this is the certificate, the model only steers)
    out_faces = []
    misses = 0
    for f in faces:
        pts = []
        for key in f["loop"]:
            pts.append(solved_xy[(key[0] / 10.0, key[1] / 10.0)])
        area = (
            abs(
                sum(
                    pts[i][0] * pts[(i + 1) % len(pts)][1]
                    - pts[(i + 1) % len(pts)][0] * pts[i][1]
                    for i in range(len(pts))
                )
            )
            / 2.0
        )
        tag = f["tag"] or {}
        lo, hi = tag.get("area_min"), tag.get("area_max")
        ok = (lo is None or area >= lo - 1e-6) and (hi is None or area <= hi + 1e-6)
        if tag and not ok:
            misses += 1
        cx = round(sum(pt[0] for pt in pts) / len(pts), 2)
        cy = round(sum(pt[1] for pt in pts) / len(pts), 2)
        out_faces.append(
            {
                "index": f["index"],
                "key": tag.get("key"),
                "label": tag.get("label", ""),
                "area": round(area, 2),
                "band": [lo, hi],
                "ok": not (tag and not ok),
                "centroid_solved": [cx, cy],
            }
        )
    status_word = (
        "solved"
        if misses == 0
        else "solved-with-misses"
        if misses < len(faces)
        else "solved-but-faces-miss"
    )
    return {
        "status": status_word,
        "faces": out_faces,
        "junctions": junctions,
        "in_band": misses == 0,
        "time": round(time.time() - t0, 2) + solver.WallTime(),
        "errors": [],
    }
