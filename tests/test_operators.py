# This file was generated with the assistance of an AI coding tool.
"""Tests for plankit.operators."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.geometry import Vec
from plankit.operators import (
    add_room,
    layout_row,
    mirror_footprint,
    move_room,
    move_toward,
    place_space,
    propose_magnet,
    remove_room,
    shape_for_area,
    split_footprint,
    squarify_rects,
    swap_rooms,
)


def _area(pts) -> float:
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i].x, pts[i].y
        x1, y1 = pts[(i + 1) % n].x, pts[(i + 1) % n].y
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _program() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8, area_max=15),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[],
    )


def test_place_space_exact_dims():
    pts = place_space(_program(), "k", 1.0, 2.0, w=3.0, d=4.0)
    assert [(p.x, p.y) for p in pts] == [(1.0, 2.0), (4.0, 2.0), (4.0, 6.0), (1.0, 6.0)]
    assert _area(pts) == pytest.approx(12.0)


def test_place_space_derives_missing_dim():
    assert _area(place_space(_program(), "k", 0, 0, w=4.0)) == pytest.approx(8.0)
    assert _area(place_space(_program(), "w", 0, 0, d=5.0)) == pytest.approx(20.0)
    assert _area(place_space(_program(), "k", 0, 0)) == pytest.approx(8.0)


def test_place_space_rejects_area_violation():
    with pytest.raises(ValueError):
        place_space(_program(), "k", 0, 0, w=1.0, d=1.0)  # 1 m² < 8
    with pytest.raises(ValueError):
        place_space(_program(), "k", 0, 0, w=10.0, d=10.0)  # 100 m² > 15


def test_place_space_rejects_bad_input():
    with pytest.raises(KeyError):
        place_space(_program(), "zzz", 0, 0)
    with pytest.raises(ValueError):
        place_space(_program(), "k", 0, 0, w=-1.0)
    prog = RoomProgram(nodes={"x": ProgramSpace(name="X")}, edges=[])
    with pytest.raises(ValueError):
        place_space(prog, "x", 0, 0)


def test_split_footprint_x():
    a, b = split_footprint([Vec(0, 0), Vec(6, 0), Vec(6, 4), Vec(0, 4)], "x", 2.0)
    assert _area(a) == pytest.approx(8.0)
    assert _area(b) == pytest.approx(16.0)


def test_split_footprint_y():
    a, b = split_footprint([Vec(0, 0), Vec(6, 0), Vec(6, 4), Vec(0, 4)], "y", 1.0)
    assert _area(a) == pytest.approx(6.0)
    assert _area(b) == pytest.approx(18.0)


def test_split_footprint_rejects():
    rect = [Vec(0, 0), Vec(6, 0), Vec(6, 4), Vec(0, 4)]
    with pytest.raises(ValueError):
        split_footprint(rect, "x", 99.0)
    with pytest.raises(ValueError):
        split_footprint(rect, "z", 1.0)
    with pytest.raises(ValueError):
        split_footprint([Vec(0, 0), Vec(1, 1), Vec(2, 0)], "x", 1.0)


def test_mirror_footprint():
    rect = [Vec(0, 0), Vec(6, 0), Vec(6, 4), Vec(0, 4)]
    m = mirror_footprint(rect, "x", 10.0)
    assert [(p.x, p.y) for p in m] == [(20.0, 4.0), (14.0, 4.0), (14.0, 0.0), (20.0, 0.0)]
    assert _area(m) == pytest.approx(_area(rect))  # winding behouden
    m2 = mirror_footprint(rect, "y", 5.0)
    assert [(p.x, p.y) for p in m2] == [(0.0, 6.0), (6.0, 6.0), (6.0, 10.0), (0.0, 10.0)]
    with pytest.raises(ValueError):
        mirror_footprint(rect, "z", 0.0)


def test_add_remove_room():
    prog = _program()
    add_room(prog, "b", ProgramSpace(name="1.03", area_min=5))
    assert "b" in prog.nodes
    with pytest.raises(KeyError):
        add_room(prog, "b", ProgramSpace(name="dup"))

    prog.edges.append(ProgramEdge("k", "b", kind="wall", required=False))
    remove_room(prog, "b")
    assert "b" not in prog.nodes
    assert all(e.a != "b" and e.b != "b" for e in prog.edges)
    with pytest.raises(KeyError):
        remove_room(prog, "b")


def test_layout_row():
    prog = _program()
    out = layout_row(prog, ["k", "w"], x0=1.0, y0=2.0, depth=4.0, gap=0.5)
    assert _area(out["k"]) == pytest.approx(8.0)
    assert _area(out["w"]) == pytest.approx(20.0)
    # aaneengesloten met gap: k[1,3], w[3.5,8.5]
    assert out["k"][0].x == pytest.approx(1.0)
    assert out["w"][0].x == pytest.approx(3.5)
    assert out["k"][0].y == out["w"][0].y == pytest.approx(2.0)
    with pytest.raises(KeyError):
        layout_row(prog, ["zzz"], 0, 0, 4.0)
    with pytest.raises(ValueError):
        layout_row(prog, ["k"], 0, 0, 0.0)


def test_shape_for_area_respects_cap_and_area():
    for area in [1.0, 2.0, 5.0, 8.0, 20.0, 100.0, 200.0]:
        w, d = shape_for_area(area, max_aspect=1.5)
        assert w * d == pytest.approx(area)
        assert max(w, d) / min(w, d) <= 1.5 + 1e-9


def test_shape_for_area_landscape():
    w, d = shape_for_area(20.0)
    assert w >= d
    w2, d2 = shape_for_area(20.0, landscape=False)
    assert d2 > w2
    assert (w, d) == (d2, w2)


def test_shape_for_area_deterministic():
    assert shape_for_area(13.0) == shape_for_area(13.0)


def test_shape_for_area_rejects_bad_input():
    with pytest.raises(ValueError):
        shape_for_area(0.0)
    with pytest.raises(ValueError):
        shape_for_area(-5.0)
    with pytest.raises(ValueError):
        shape_for_area(10.0, max_aspect=0.5)
    with pytest.raises(ValueError):
        shape_for_area(10.0, min_width=0.0)


def test_shape_for_area_min_width_caps_aspect():
    w, d = shape_for_area(5.0, min_width=2.0)
    assert w * d == pytest.approx(5.0)
    assert min(w, d) >= 2.0 - 1e-9
    assert max(w, d) / min(w, d) <= 1.25 + 1e-9


def test_shape_for_area_min_width_infeasible_grows():
    w, d = shape_for_area(4.0, min_width=2.1)
    assert (w, d) == (2.1, 2.1)


def test_propose_magnet_respects_min_widths():
    prog = RoomProgram(
        nodes={
            "k": ProgramSpace(name="Keuken", area_min=4.0),
            "w": ProgramSpace(name="Woonkamer", area_min=20.0),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )
    out = propose_magnet(prog, seed=0, min_widths={"k": 2.1, "w": 2.1})
    for key, pts in out.items():
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        assert min(max(xs) - min(xs), max(ys) - min(ys)) >= 2.1 - 1e-9


def test_place_space_fallback_uses_shape():
    pts = place_space(_program(), "k", 0, 0)
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    w, d = max(xs) - min(xs), max(ys) - min(ys)
    assert max(w, d) / min(w, d) <= 1.5 + 1e-9


def _bbox(pts) -> tuple:
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _magnet_program() -> RoomProgram:
    return RoomProgram(
        nodes={
            "h": ProgramSpace(name="Hal", area_min=6, entrance=True),
            "k": ProgramSpace(name="Keuken", area_min=8),
            "w": ProgramSpace(name="Woonkamer", area_min=20),
        },
        edges=[
            ProgramEdge("h", "k", kind="door"),
            ProgramEdge("k", "w", kind="door"),
        ],
    )


def test_propose_magnet_deterministic():
    prog = _magnet_program()
    a = propose_magnet(prog, seed=3)
    b = propose_magnet(prog, seed=3)
    assert {k: [(p.x, p.y) for p in v] for k, v in a.items()} == {
        k: [(p.x, p.y) for p in v] for k, v in b.items()
    }


def test_propose_magnet_places_all_without_overlap():
    prog = _magnet_program()
    out = propose_magnet(prog, seed=1)
    assert set(out) == {"h", "k", "w"}
    boxes = {k: _bbox(v) for k, v in out.items()}
    for key, box in boxes.items():
        assert (box[2] - box[0]) * (box[3] - box[1]) == pytest.approx(
            prog.nodes[key].area_min
        )
    keys = list(boxes)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = boxes[keys[i]], boxes[keys[j]]
            assert not (
                a[0] < b[2] - 1e-9
                and b[0] < a[2] - 1e-9
                and a[1] < b[3] - 1e-9
                and b[1] < a[3] - 1e-9
            )


def _shared_wall_len(a: tuple, b: tuple) -> float:
    total = 0.0
    if abs(a[2] - b[0]) <= 1e-9 or abs(b[2] - a[0]) <= 1e-9:
        total += max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    if abs(a[3] - b[1]) <= 1e-9 or abs(b[3] - a[1]) <= 1e-9:
        total += max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    return total


def test_propose_magnet_partners_share_wall():
    prog = _magnet_program()
    out = propose_magnet(prog, seed=1)
    boxes = {k: _bbox(v) for k, v in out.items()}
    assert _shared_wall_len(boxes["h"], boxes["k"]) > 0
    assert _shared_wall_len(boxes["k"], boxes["w"]) > 0


def test_propose_magnet_entrance_first_at_origin():
    out = propose_magnet(_magnet_program(), seed=1)
    assert _bbox(out["h"])[:2] == pytest.approx((0.0, 0.0))


def test_propose_magnet_requires_area():
    prog = RoomProgram(nodes={"x": ProgramSpace(name="X")}, edges=[])
    with pytest.raises(ValueError):
        propose_magnet(prog)


def test_propose_magnet_wet_rooms_cluster():
    prog = RoomProgram(
        nodes={
            "w": ProgramSpace(name="Woonkamer", area_min=20),
            "b": ProgramSpace(name="Badkamer", area_min=6, wet=True),
            "t": ProgramSpace(name="Toilet", area_min=4, wet=True),
        },
        edges=[ProgramEdge("w", "b", kind="door")],  # b-t: geen expliciete kant
    )
    out = propose_magnet(prog, seed=0)
    boxes = {k: _bbox(v) for k, v in out.items()}
    assert _shared_wall_len(boxes["b"], boxes["t"]) > 0


def test_propose_magnet_daylight_touches_edge():
    prog = RoomProgram(
        nodes={
            "w": ProgramSpace(name="Woonkamer", area_min=20, daylight=True),
            "b": ProgramSpace(name="Badkamer", area_min=6),
            "s": ProgramSpace(name="Slaapkamer", area_min=12),
        },
        edges=[
            ProgramEdge("w", "b", kind="door"),
            ProgramEdge("b", "s", kind="door"),
        ],
    )
    out = propose_magnet(prog, seed=0)
    boxes = {k: _bbox(v) for k, v in out.items()}
    gx0 = min(b[0] for b in boxes.values())
    gy0 = min(b[1] for b in boxes.values())
    gx1 = max(b[2] for b in boxes.values())
    gy1 = max(b[3] for b in boxes.values())
    w = boxes["w"]
    assert w[0] == gx0 or w[1] == gy0 or w[2] == gx1 or w[3] == gy1


def test_propose_magnet_flags_keep_determinism():
    prog = RoomProgram(
        nodes={"w": ProgramSpace(name="W", area_min=20, daylight=True, wet=True)},
        edges=[],
    )
    a = propose_magnet(prog, seed=2)
    b = propose_magnet(prog, seed=2)
    assert {k: [(p.x, p.y) for p in v] for k, v in a.items()} == {
        k: [(p.x, p.y) for p in v] for k, v in b.items()
    }


def test_propose_magnet_first_room_to_attractor_corner():
    prog = RoomProgram(nodes={"w": ProgramSpace(name="W", area_min=6)}, edges=[])
    out = propose_magnet(prog, seed=0, bounds=(0.0, 0.0, 10.0, 10.0), attractors={"w": (5.0, 10.0)})
    box = _bbox(out["w"])
    assert box[3] == pytest.approx(10.0)  # raakt de bovenrand bij de attractor


def _squarify_area(rect) -> float:
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def _squarify_aspect(rect) -> float:
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    return max(w, h) / min(w, h)


def test_squarify_rects_exact_areas_and_tiling():
    items = [(f"r{i}", a) for i, a in enumerate([6.0, 6.0, 4.0, 3.0, 2.0, 2.0, 1.0])]
    out = squarify_rects(items, (0.0, 0.0, 6.0, 4.0))
    assert set(out) == {f"r{i}" for i in range(7)}
    for (key, area), rect in zip(items, [out[k] for k, _ in items]):
        assert _squarify_area(rect) == pytest.approx(area)
    assert sum(_squarify_area(r) for r in out.values()) == pytest.approx(24.0)


def test_squarify_rects_aspect_bounded():
    items = [(f"r{i}", a) for i, a in enumerate([6.0, 6.0, 4.0, 3.0, 2.0, 2.0, 1.0])]
    out = squarify_rects(items, (0.0, 0.0, 6.0, 4.0))
    assert max(_squarify_aspect(r) for r in out.values()) <= 3.0


def test_squarify_rects_deterministic_and_rejects():
    items = [("a", 10.0), ("b", 5.0)]
    assert squarify_rects(items, (0.0, 0.0, 5.0, 3.0)) == squarify_rects(
        items, (0.0, 0.0, 5.0, 3.0)
    )
    with pytest.raises(ValueError):
        squarify_rects([("a", 0.0)], (0.0, 0.0, 5.0, 3.0))
    with pytest.raises(ValueError):
        squarify_rects([("a", -2.0)], (0.0, 0.0, 5.0, 3.0))


def _two_rects():
    return {
        "a": [Vec(0.0, 0.0), Vec(4.0, 0.0), Vec(4.0, 3.0), Vec(0.0, 3.0)],
        "b": [Vec(10.0, 0.0), Vec(14.0, 0.0), Vec(14.0, 3.0), Vec(10.0, 3.0)],
    }


def test_move_room_translates_and_keeps_input():
    prop = _two_rects()
    out = move_room(prop, "a", 2.0, -1.0)
    assert [(p.x, p.y) for p in out["a"]] == [(2.0, -1.0), (6.0, -1.0), (6.0, 2.0), (2.0, 2.0)]
    assert prop["a"][0].x == 0.0  # invoer ongewijzigd
    with pytest.raises(KeyError):
        move_room(prop, "zzz", 1.0, 0.0)


def test_swap_rooms_exchanges_origins():
    prop = _two_rects()
    out = swap_rooms(prop, "a", "b")
    assert [(p.x, p.y) for p in out["a"]] == [(10.0, 0.0), (14.0, 0.0), (14.0, 3.0), (10.0, 3.0)]
    assert [(p.x, p.y) for p in out["b"]] == [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
    with pytest.raises(KeyError):
        swap_rooms(prop, "a", "zzz")


def test_move_toward_touches():
    prop = _two_rects()
    out = move_toward(prop, "a", "b")
    xs = [p.x for p in out["a"]]
    assert max(xs) == pytest.approx(10.0)  # rechterrand tegen b
    again = move_toward(out, "a", "b")
    assert [(p.x, p.y) for p in again["a"]] == [(p.x, p.y) for p in out["a"]]
