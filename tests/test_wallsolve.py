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
