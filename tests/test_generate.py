# This file was generated with the assistance of an AI coding tool.
"""Tests voor generatie (plankit.generate) en de constraint-laag."""

import pytest

from plankit import Graph, ProgramEdge, ProgramSpace, RoomProgram
from plankit.constraints import program_constraints
from plankit.derive import door_pairs, space_adjacency
from plankit.generate import generate, propose_layout


def _two_room_program() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", long_name="Keuken", area_min=8, area_max=15),
            "w": ProgramSpace(name="1.02", long_name="Woonkamer", area_min=20),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[
            ProgramEdge("k", "buiten", kind="facade"),
            ProgramEdge("k", "w", kind="door"),
        ],
    )


def test_generate_faces_and_areas():
    sd = generate(_two_room_program())
    assert len(sd.bounded_faces()) == 2
    assert sum(sd.face_area(f) for f in sd.bounded_faces()) == pytest.approx(28.0)


def test_generate_door_marked():
    sd = generate(_two_room_program())
    assert door_pairs(sd) == [("0", "1")]


def test_generate_adjacency_door():
    sd = generate(_two_room_program())
    g = space_adjacency(sd)
    assert g.has_edge("0", "1")
    assert g.edge_attrs("0", "1")["kind"] == "door"


def test_access_reachability():
    sd = generate(_two_room_program())
    access = Graph()
    for a, b in door_pairs(sd):
        access.add_edge(a, b)
    assert access.is_connected()


def test_propose_layout_deterministic():
    prog = _two_room_program()
    assert propose_layout(prog) == propose_layout(prog)


def test_generate_magnet_strategy():
    sd = generate(_two_room_program(), strategy="magnet")
    ids = {f.label: str(i) for i, f in enumerate(sd.faces) if not f.exterior}
    assert {"k", "w"} <= set(ids)
    pairs = door_pairs(sd)
    assert (ids["k"], ids["w"]) in pairs or (ids["w"], ids["k"]) in pairs


def test_generate_default_strategy_still_row():
    sd = generate(_two_room_program())
    assert door_pairs(sd) == [("0", "1")]


def test_generate_unknown_strategy():
    with pytest.raises(ValueError):
        generate(_two_room_program(), strategy="nonsense")


def test_generate_skips_door_without_shared_edge():
    from plankit.conform import conform

    proposal = {
        "k": [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)],
        "w": [(10.0, 0.0), (15.0, 0.0), (15.0, 4.0), (10.0, 4.0)],
    }
    sd = generate(_two_room_program(), proposal=proposal)  # geen crash
    r = conform(sd, _two_room_program())
    assert not r.ok
    assert "edge:k-w:door" in r.violated
    assert r.missing_adj == {"k": ["w"], "w": ["k"]}


def test_generate_magnet_labels_match_areas():
    # keten-5/seed-0 legde r2 op een 0 m²-splinter (noding-artefact); labels
    # moeten naar de grootste face binnen de proposal-bbox.
    from plankit.operators import propose_magnet

    prog = RoomProgram(
        nodes={f"r{i}": ProgramSpace(name=f"R{i}", area_min=a) for i, a in enumerate([6.0, 10.0, 14.0, 20.0, 28.0])},
        edges=[ProgramEdge(f"r{i}", f"r{i + 1}", kind="door") for i in range(4)],
    )
    sd = generate(prog, proposal=propose_magnet(prog, seed=0))
    got = {f.label: sd.face_area(i) for i, f in enumerate(sd.faces) if not f.exterior and f.label}
    assert set(got) == {"r0", "r1", "r2", "r3", "r4"}
    for key, space in prog.nodes.items():
        assert got[key] == pytest.approx(space.area_min)


def test_program_constraints():
    cs = program_constraints(_two_room_program())
    kinds = sorted(c.kind for c in cs)
    assert "area" in kinds
    assert "edge" in kinds
    area_cs = [c for c in cs if c.kind == "area"]
    assert any(c.a == "k" and c.area_min == 8 for c in area_cs)
    edge_kinds = sorted(c.edge_kind for c in cs if c.kind == "edge")
    assert "door" in edge_kinds
    assert "facade" in edge_kinds
