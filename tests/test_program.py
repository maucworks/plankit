# This file was generated with the assistance of an AI coding tool.
"""Tests for the PvE program dataclasses."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram, dwelling_budget


def test_program_edge_rejects_unknown_kind():
    with pytest.raises(ValueError):
        ProgramEdge("a", "b", kind="nonsense")


def test_program_edge_soft_wall_defaults_required_true():
    edge = ProgramEdge("a", "b", kind="wall")
    assert edge.required is True


def test_room_program_to_from_dict_roundtrip():
    program = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", long_name="Keuken", area_min=8),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[ProgramEdge("k", "buiten", kind="facade")],
    )
    data = program.to_dict()
    restored = RoomProgram.from_dict(data)
    assert restored.nodes["k"].name == "1.01"
    assert restored.nodes["k"].area_min == 8
    assert restored.edges[0].kind == "facade"


def test_room_program_defaults_empty():
    program = RoomProgram()
    assert program.nodes == {}
    assert program.edges == []


def test_program_space_rejects_unknown_role():
    with pytest.raises(ValueError):
        ProgramSpace(name="X", role="nonsense")


def test_program_space_role_roundtrip():
    program = RoomProgram(
        nodes={"g": ProgramSpace(name="Gang", role="verkeer")}, edges=[]
    )
    restored = RoomProgram.from_dict(program.to_dict())
    assert restored.nodes["g"].role == "verkeer"


def test_program_space_entrance_roundtrip():
    program = RoomProgram(
        nodes={"h": ProgramSpace(name="Hal", entrance=True)}, edges=[]
    )
    restored = RoomProgram.from_dict(program.to_dict())
    assert restored.nodes["h"].entrance is True


def test_program_space_entrance_defaults_false():
    assert ProgramSpace(name="X").entrance is False


def test_program_edge_max_distance_roundtrip():
    program = RoomProgram(
        nodes={"a": ProgramSpace(name="A"), "b": ProgramSpace(name="B")},
        edges=[ProgramEdge("a", "b", kind="wall", required=False, max_distance=3.0)],
    )
    restored = RoomProgram.from_dict(program.to_dict())
    assert restored.edges[0].max_distance == 3.0


def test_program_edge_max_distance_defaults_none():
    assert ProgramEdge("a", "b", kind="wall").max_distance is None


def test_program_space_daylight_wet_roundtrip():
    program = RoomProgram(
        nodes={"b": ProgramSpace(name="Bad", wet=True, daylight=False)},
        edges=[],
    )
    restored = RoomProgram.from_dict(program.to_dict())
    assert restored.nodes["b"].wet is True
    assert restored.nodes["b"].daylight is False


def test_program_space_daylight_wet_defaults_false():
    space = ProgramSpace(name="X")
    assert space.daylight is False
    assert space.wet is False


def test_program_space_group_core_roundtrip():
    program = RoomProgram(
        nodes={
            "w": ProgramSpace(name="Woonkamer", group="A1"),
            "kern": ProgramSpace(name="Kern", role="verkeer", core=True),
        },
        edges=[],
    )
    restored = RoomProgram.from_dict(program.to_dict())
    assert restored.nodes["w"].group == "A1"
    assert restored.nodes["kern"].core is True


def test_program_space_group_core_defaults():
    space = ProgramSpace(name="X")
    assert space.group is None
    assert space.core is False


def test_dwelling_budget_ranges():
    program = RoomProgram(
        nodes={
            "w": ProgramSpace(name="Woonkamer", area_min=15, group="A1"),
            "k": ProgramSpace(name="Keuken", area_min=4, area_max=4.8, group="A1"),
            "b": ProgramSpace(name="Badkamer", area_min=6, area_max=7.2, group="A1"),
            "x": ProgramSpace(name="Ander", area_min=100, group="B1"),
        },
        edges=[],
    )
    assert dwelling_budget(program, "A1") == (25.0, 27.0)
    assert dwelling_budget(program, "zzz") == (0.0, 0.0)


def test_access_graph_only_door_edges():
    program = RoomProgram(
        nodes={
            "a": ProgramSpace(name="A"),
            "b": ProgramSpace(name="B"),
            "c": ProgramSpace(name="C"),
        },
        edges=[
            ProgramEdge("a", "b", kind="door"),
            ProgramEdge("b", "c", kind="wall", required=False),
        ],
    )
    g = program.access_graph()
    assert g.has_edge("a", "b")
    assert not g.has_edge("b", "c")
    assert g.edge_attrs("a", "b")["kind"] == "door"
