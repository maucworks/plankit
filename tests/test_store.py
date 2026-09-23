# This file was generated with the assistance of an AI coding tool.
"""Tests voor de variant-store (plankit.store)."""

import pytest

from plankit import ProgramEdge, ProgramSpace, RoomProgram
from plankit.generate import generate
from plankit.planar import PlanarSubdivision
from plankit.store import VariantStore, make_variant


def _two_room() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )


def test_make_variant_has_report_and_state():
    sd = generate(_two_room())
    v = make_variant(sd, _two_room(), step=1, label="strip")
    assert v.label == "strip"
    assert "conformance" in v.report
    assert "quality" in v.report
    assert v.state


def test_store_add_get(tmp_path):
    store = VariantStore(str(tmp_path / "v.db"))
    sd = generate(_two_room())
    v = make_variant(sd, _two_room(), step=0, label="root")
    store.add(v)
    got = store.get(v.id)
    assert got.label == "root"
    assert got.report == v.report
    store.close()


def test_store_lineage(tmp_path):
    store = VariantStore(str(tmp_path / "v.db"))
    sd = generate(_two_room())
    root = store.add(make_variant(sd, _two_room(), step=0, label="root"))
    store.add(make_variant(sd, _two_room(), step=1, label="revise", parent_id=root.id))
    assert [v.label for v in store.roots()] == ["root"]
    assert [v.label for v in store.children(root.id)] == ["revise"]
    assert len(store.all()) == 2
    store.close()


def test_store_roundtrip_state():
    sd = generate(_two_room())
    v = make_variant(sd, _two_room(), step=0)
    sd2 = PlanarSubdivision.from_dict(v.state)
    assert len(sd2.bounded_faces()) == 2


def test_store_filter():
    store = VariantStore()
    sd = generate(_two_room())
    store.add(make_variant(sd, _two_room(), step=0, label="a"))
    store.add(make_variant(sd, _two_room(), step=1, label="b"))
    assert [v.label for v in store.filter(lambda v: v.step == 1)] == ["b"]
    store.close()
