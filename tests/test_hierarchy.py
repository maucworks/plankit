# This file was generated with the assistance of an AI coding tool.
"""Tests voor hiërarchische generatie (plankit.hierarchy)."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.conform import conform
from plankit.derive import door_pairs
from plankit.generate import generate
from plankit.hierarchy import (
    coarse_layout,
    dwelling_envelope,
    squarify_blocks,
    supernodes,
    two_step,
)


def _toy() -> RoomProgram:
    return RoomProgram(
        nodes={
            "w1": ProgramSpace(name="W1", area_min=15, group="A1"),
            "s1": ProgramSpace(name="S1", area_min=10, group="A1"),
            "w2": ProgramSpace(name="W2", area_min=12, group="A2"),
            "s2": ProgramSpace(name="S2", area_min=8, group="A2"),
            "gang": ProgramSpace(name="Gang", area_min=10, role="verkeer"),
            "kern": ProgramSpace(name="Kern", area_min=8, role="verkeer", core=True),
        },
        edges=[
            ProgramEdge("w1", "s1", kind="door"),
            ProgramEdge("w2", "s2", kind="door"),
            ProgramEdge("w1", "gang", kind="door"),
            ProgramEdge("w2", "gang", kind="door"),
            ProgramEdge("gang", "kern", kind="door"),
        ],
    )


def test_dwelling_envelope_fields():
    env = dwelling_envelope(_toy(), "A1")
    assert (env.area_lo, env.area_hi) == (25.0, 25.0)
    assert env.n_rooms == 2
    assert env.n_daylight == 0
    assert env.daylight_area == 0.0


def test_supernodes_groups_and_singles():
    assert supernodes(_toy()) == {
        "A1": ["w1", "s1"],
        "A2": ["w2", "s2"],
        "gang": ["gang"],
        "kern": ["kern"],
    }


def test_coarse_layout_unknown_topology():
    with pytest.raises(ValueError):
        coarse_layout(_toy(), topology="nonsense")


def test_coarse_layout_unimplemented_topologies():
    with pytest.raises(NotImplementedError):
        coarse_layout(_toy(), topology="portiek")
    with pytest.raises(NotImplementedError):
        coarse_layout(_toy(), topology="galerij")


def _overlaps(a, b) -> bool:
    return a[0] < b[2] - 1e-9 and b[0] < a[2] - 1e-9 and a[1] < b[3] - 1e-9 and b[1] < a[3] - 1e-9


def test_coarse_layout_no_overlap_and_centered_core():
    blocks = coarse_layout(_toy(), seed=0)
    assert set(blocks) == {"A1", "A2", "gang", "kern"}
    keys = list(blocks)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            assert not _overlaps(blocks[keys[i]], blocks[keys[j]])
    x0, y0, x1, y1 = blocks["kern"]
    assert x0 < 0 < x1 and y0 < 0 < y1  # kern centraal op de oorsprong


def test_coarse_layout_deterministic():
    assert coarse_layout(_toy(), seed=4) == coarse_layout(_toy(), seed=4)


def test_two_step_keys_and_no_overflow():
    proposal, issues = two_step(_toy(), seed=0)
    assert set(proposal) == {"w1", "s1", "w2", "s2", "gang", "kern"}
    assert not any("envelop te klein" in i for i in issues)
    # eerlijk signaal: A2-blok deelt geen rand met gang (grof-pakking),
    # dus het paar kan niet verankerd worden
    assert any("geen gedeelde rand voor w2-gang" in i for i in issues)


def test_two_step_deterministic():
    a, _ = two_step(_toy(), seed=2)
    b, _ = two_step(_toy(), seed=2)
    assert {k: [(p.x, p.y) for p in v] for k, v in a.items()} == {
        k: [(p.x, p.y) for p in v] for k, v in b.items()
    }


def test_two_step_intra_dwelling_doors_ok():
    proposal, _ = two_step(_toy(), seed=0)
    sd = generate(_toy(), proposal=proposal)
    ids = {f.label: str(i) for i, f in enumerate(sd.faces) if not f.exterior}
    pairs = door_pairs(sd)
    for a, b in [("w1", "s1"), ("w2", "s2")]:
        assert (ids[a], ids[b]) in pairs or (ids[b], ids[a]) in pairs
    r = conform(sd, _toy())
    assert "edge:w1-s1:door" in r.satisfied
    assert "edge:w2-s2:door" in r.satisfied


def test_two_step_cross_block_door_at_shared_segment():
    prog = RoomProgram(
        nodes={
            "w1": ProgramSpace(name="W1", area_min=15, group="A1"),
            "s1": ProgramSpace(name="S1", area_min=10, group="A1"),
            "gang": ProgramSpace(name="Gang", area_min=10, role="verkeer"),
            "kern": ProgramSpace(name="Kern", area_min=8, role="verkeer", core=True),
        },
        edges=[
            ProgramEdge("w1", "s1", kind="door"),
            ProgramEdge("w1", "gang", kind="door"),
            ProgramEdge("gang", "kern", kind="door"),
        ],
    )
    proposal, issues = two_step(prog, seed=0)
    assert issues == []
    r = conform(generate(prog, proposal=proposal), prog)
    assert "edge:w1-gang:door" in r.satisfied


def test_two_step_pair_shares_wall_in_proposal():
    from plankit.operators import _shared_wall

    prog = RoomProgram(
        nodes={
            "w1": ProgramSpace(name="W1", area_min=15, group="A1"),
            "s1": ProgramSpace(name="S1", area_min=10, group="A1"),
            "gang": ProgramSpace(name="Gang", area_min=10, role="verkeer"),
            "kern": ProgramSpace(name="Kern", area_min=8, role="verkeer", core=True),
        },
        edges=[
            ProgramEdge("w1", "s1", kind="door"),
            ProgramEdge("w1", "gang", kind="door"),
            ProgramEdge("gang", "kern", kind="door"),
        ],
    )
    proposal, _ = two_step(prog, seed=0)

    def box(key):
        pts = proposal[key]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    assert _shared_wall(box("w1"), box("gang")) > 0


def test_two_step_short_segment_reports_issue():
    prog = RoomProgram(
        nodes={
            "a": ProgramSpace(name="A", area_min=20, group="G1"),
            "b": ProgramSpace(name="B", area_min=20, group="G2"),
        },
        edges=[ProgramEdge("a", "b", kind="door")],
    )
    blocks = {"G1": (0.0, 0.0, 10.0, 2.0), "G2": (10.0, 0.0, 12.0, 10.0)}
    proposal, issues = two_step(prog, seed=0, blocks=blocks)
    assert set(proposal) == {"a", "b"}  # graceful: wel geplaatst
    assert any("a-b" in i for i in issues)


def test_propose_magnet_placed_rooms_not_moved():
    from plankit.operators import propose_magnet

    prog = RoomProgram(
        nodes={
            "a": ProgramSpace(name="A", area_min=12),
            "b": ProgramSpace(name="B", area_min=8),
        },
        edges=[ProgramEdge("a", "b", kind="door")],
    )
    fixed = (0.0, 0.0, 4.0, 3.0)
    out = propose_magnet(prog, seed=0, placed={"a": fixed})
    got = out["a"]
    assert [(p.x, p.y) for p in got] == [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
    assert set(out) == {"a", "b"}


def test_squarify_blocks_scale_to_boundary():
    prog = _toy()
    boundary = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
    blocks = squarify_blocks(prog, boundary)
    assert set(blocks) == {"A1", "A2", "gang", "kern"}
    total = sum((r[2] - r[0]) * (r[3] - r[1]) for r in blocks.values())
    assert total == pytest.approx(200.0)
    for rect in blocks.values():
        assert 0.0 - 1e-9 <= rect[0] and rect[2] <= 20.0 + 1e-9
        assert 0.0 - 1e-9 <= rect[1] and rect[3] <= 10.0 + 1e-9


def test_squarify_blocks_rejects_empty():
    prog = RoomProgram(nodes={}, edges=[])
    with pytest.raises(ValueError):
        squarify_blocks(prog, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


def test_two_step_with_squarify_blocks():
    prog = _toy()
    boundary = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
    proposal, issues = two_step(prog, seed=0, blocks=squarify_blocks(prog, boundary))
    assert set(proposal) == {"w1", "s1", "w2", "s2", "gang", "kern"}
    assert isinstance(issues, list)
