# This file was generated with the assistance of an AI coding tool.
"""Tests for the metric solver on wall-graph templates (rubber-band m²)."""

from plankit.wallgraph import WallGraphDraft
from plankit.wallsolve import solve_areas


def _draft(bands=(("wet", 305.0, 315.0), ("living", 700.0, 740.0))) -> dict:
    tags = []
    for key, lo, hi in bands:
        label = {"wet": "wet", "living": "living"}[key]
        items = ["*-bad", "keuken.*"] if key == "wet" else ["*-woon"]
        centroid = [20.0, 5.0] if key == "wet" else [20.0, 18.0]
        tags.append(
            {
                "key": key,
                "label": label,
                "items": items,
                "area_min": lo,
                "area_max": hi,
                "centroid": centroid,
            }
        )
    return {
        "kind": "wallgraph",
        "name": "open-kern-wall",
        "envelope": {"x0": 0, "y0": 0, "x1": 40, "y1": 26},
        "grid": 3.3,
        "segments": [
            {"x0": 0, "y0": 0, "x1": 40, "y1": 0},  # facade
            {"x0": 40, "y0": 0, "x1": 40, "y1": 26},  # facade
            {"x0": 40, "y0": 26, "x1": 0, "y1": 26},  # facade
            {"x0": 0, "y0": 26, "x1": 0, "y1": 0},  # facade
            {"x0": 0, "y0": 10, "x1": 40, "y1": 10},  # divider (horizontal)
        ],
        "edges": {"0": "facade", "1": "facade", "2": "facade", "3": "facade"},
        "faces": tags,
    }


def _solve(draft, seconds=25.0):
    return (
        solve_areas(
            WallGraphDraft.from_dict(
                _draft() if isinstance(draft, tuple) or draft is None else draft
            ),
            seconds,
        )
        if False
        else solve_areas(WallGraphDraft.from_dict(draft), seconds)
    )


def test_least_movement_solve_hits_both_bands():
    out = _solve(_draft())
    assert out["status"] == "solved", out
    areas = {f["key"]: f["area"] for f in out["faces"]}
    assert 305.0 - 1e-6 <= areas["wet"] <= 315.0 + 1e-6
    assert 700.0 - 1e-6 <= areas["living"] <= 740.0 + 1e-6
    assert all(f["ok"] for f in out["faces"])
    # least movement: the divider drops to the nearest dm-feasible line
    # inside BOTH bands (the dm lattice makes the exact 7.75 corner
    # unreachable; the point is: one divider line, both bands, in-band)
    moved = {tuple(j["orig"]): j["solved"] for j in out["junctions"]}
    d1 = moved[(0.0, 10.0)][1]
    assert moved[(40.0, 10.0)][1] == d1
    assert 7.0 <= d1 <= 10.0


def test_solve_is_deterministic():
    a = _solve(_draft())
    b = _solve(_draft())
    assert a["junctions"] == b["junctions"]
    assert a["faces"] == b["faces"]


def test_infeasible_bands_reported():
    out = _solve(_draft(bands=(("wet", 305.0, 315.0), ("living", 600.0, 610.0))))
    assert out["status"] == "infeasible"


def test_all_faces_exact_on_nearest_feasible():
    out = _solve(_draft())
    wetdivider = sorted(
        (j["solved"][1] for j in out["junctions"] if j["orig"][1] == 10.0)
    )
    assert wetdivider and wetdivider[0] == wetdivider[-1]  # divider stays one line


def test_non_orthogonal_stroke_rejected():
    d = _draft()
    d["segments"].append({"x0": 5, "y0": 5, "x1": 15, "y1": 20})
    out = _solve(d)
    assert out["status"] == "rejected" and any(
        "non-orthogonal" in e for e in out["errors"]
    )


def test_unsplit_crossing_rejected():
    d = _draft()
    d["segments"].append(
        {"x0": 15, "y0": 5, "x1": 15, "y1": 15}
    )  # orthogonal; crosses the divider at (15,10)
    out = _solve(d)
    assert out["status"] == "rejected" and any(
        "split the stroke" in e for e in out["errors"]
    )


def test_untagged_face_only_needs_floor():
    d = _draft()
    d["faces"] = [t for t in d["faces"] if t["key"] == "wet"]  # living untagged
    out = _solve(d)
    assert out["status"] == "solved"
    living = next(f for f in out["faces"] if f["band"] != [305.0, 315.0])
    assert living["ok"] is True and living["area"] >= 0.5


def test_hints_warm_start_without_changing_the_certificate():
    """Interactive mode: the previous solution arrives as CP-SAT hints.

    A warm start changes only where the search begins, never the answer:
    a hinted solve must return exactly the unhinted optimum, and repeat
    identically (the canvas fires one of these per drag frame).
    """
    draft = WallGraphDraft.from_dict(_draft())
    unhinted = solve_areas(draft, 10.0)
    # a plausible previous solution: the divider 20 cm below the optimum
    hints = [
        {"orig": [0.0, 10.0], "solved": [0.0, 9.7]},
        {"orig": [40.0, 10.0], "solved": [40.0, 9.7]},
    ]
    first = solve_areas(draft, 10.0, hints=hints)
    second = solve_areas(draft, 10.0, hints=hints)
    assert first["status"] == "solved"
    assert first["junctions"] == unhinted["junctions"] == second["junctions"]
    assert first["faces"] == unhinted["faces"]


def test_hints_ignored_for_unknown_junctions():
    """A stale hint (a junction that no longer exists) must not crash."""
    draft = WallGraphDraft.from_dict(_draft())
    out = solve_areas(
        draft,
        10.0,
        hints=[{"orig": [99.0, 99.0], "solved": [1.0, 1.0]}, {"bogus": 1}],
    )
    assert out["status"] == "solved"


def _sealed_draft() -> dict:
    """A divider that *lands* on the facade stroke (not on a drawn joint).

    The divider foot at (14, 0) is a stroke end on the envelope: sealing
    the core against the corridor. Left free, the least-L1 search lifts
    the foot off the outline, the two regions merge around the gap and
    the model reports a face nobody drew.
    """
    return {
        "kind": "wallgraph",
        "name": "sealed-foot",
        "envelope": {"x0": 0, "y0": 0, "x1": 30, "y1": 12},
        "grid": 3.3,
        "segments": [
            {"x0": 0, "y0": 0, "x1": 30, "y1": 0},  # facade
            {"x0": 30, "y0": 0, "x1": 30, "y1": 12},  # facade
            {"x0": 30, "y0": 12, "x1": 0, "y1": 12},  # facade
            {"x0": 0, "y0": 12, "x1": 0, "y1": 0},  # facade
            {"x0": 14, "y0": 0, "x1": 14, "y1": 9},  # divider foot ON the facade
            {"x0": 0, "y0": 9, "x1": 14, "y1": 9},
            {"x0": 14, "y0": 9, "x1": 14, "y1": 12},  # ensemble | gang wall
        ],
        "edges": {
            "0": "facade",
            "1": "facade",
            "2": "facade",
            "3": "facade",
            "6": "wall",
        },
        "faces": [
            {
                "key": "kern",
                "label": "kern",
                "items": ["kern"],
                "area_min": 110,
                "area_max": 125,
                "centroid": [7, 4.5],
            },
            {
                "key": "A1",
                "label": "A1",
                "items": ["A1-*"],
                "area_min": 41,
                "area_max": 50,
                "centroid": [7, 10.5],
            },
            {
                "key": "gang",
                "label": "gang",
                "items": ["gang"],
                "area_min": 180,
                "area_max": 200,
                "centroid": [22, 6],
            },
        ],
    }


def test_a_stroke_foot_stays_sealed_on_the_envelope():
    draft = WallGraphDraft.from_dict(_sealed_draft())
    out = solve_areas(draft, 15.0)
    assert out["status"] == "solved", out.get("errors")
    solved = {(j["orig"][0], j["orig"][1]): j["solved"] for j in out["junctions"]}
    # the foot (14, 0) sits on the envelope: it may slide along x, never off y
    assert solved[(14.0, 0.0)][1] == 0.0
    assert solved[(0.0, 0.0)] == [0.0, 0.0]
    # the core instead shrinks by sliding its top line down inside the plan
    assert out["faces"][0]["area"] <= 125.0
    areas = {f["key"]: f["area"] for f in out["faces"]}
    assert 110 <= areas["kern"] <= 125 and areas["gang"] <= 200


def test_sealed_foot_keeps_the_two_regions_apart():
    """After the solve the drawing must still node into three rooms."""
    from plankit.program import ProgramSpace, RoomProgram
    from plankit.wallgate import gate

    draft = WallGraphDraft.from_dict(_sealed_draft())
    out = solve_areas(draft, 15.0)
    program = RoomProgram(
        nodes={
            "kern": ProgramSpace(area_min=110, area_max=125),
            "A1-slaap1": ProgramSpace(area_min=41, area_max=50),
            "gang": ProgramSpace(area_min=180, area_max=200),
        }
    )
    report = gate(draft, program, junctions=out["junctions"])
    assert len(report["faces"]) == 3
    assert report["conform"]["missing"] == []
