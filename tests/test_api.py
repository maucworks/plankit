# This file was generated with the assistance of an AI coding tool.
"""Smoke-tests voor de FastAPI-API (plankit.api)."""

import pytest
from fastapi.testclient import TestClient

from plankit.api import create_app
from plankit.store import VariantStore


@pytest.fixture
def client(tmp_path):
    store = VariantStore(str(tmp_path / "v.db"))
    return TestClient(create_app(store))


def _program_dict():
    return {
        "nodes": {
            "k": {"name": "1.01", "area_min": 8},
            "w": {"name": "1.02", "area_min": 20},
        },
        "edges": [{"a": "k", "b": "w", "kind": "door"}],
    }


def test_generate_and_get(client):
    r = client.post("/generate", json={"program": _program_dict(), "label": "strip"})
    assert r.status_code == 200
    data = r.json()
    vid = data["id"]
    assert data["label"] == "strip"
    assert data["geometry"]["faces"]
    g = client.get(f"/variants/{vid}")
    assert g.status_code == 200
    assert g.json()["id"] == vid


def test_list_variants(client):
    client.post("/generate", json={"program": _program_dict(), "label": "a"})
    client.post("/generate", json={"program": _program_dict(), "label": "b"})
    assert len(client.get("/variants").json()) == 2


def test_revise_lineage(client):
    root_id = client.post("/generate", json={"program": _program_dict()}).json()["id"]
    r = client.post(f"/variants/{root_id}/revise", json={"label": "child"})
    assert r.status_code == 200
    assert r.json()["parent_id"] == root_id


def test_svg_endpoint(client):
    vid = client.post("/generate", json={"program": _program_dict()}).json()["id"]
    s = client.get(f"/variants/{vid}/svg")
    assert s.status_code == 200
    assert s.text.startswith("<svg")


def test_compare(client):
    a = client.post("/generate", json={"program": _program_dict()}).json()["id"]
    b = client.post("/generate", json={"program": _program_dict()}).json()["id"]
    r = client.get("/compare", params={"a": a, "b": b})
    assert r.status_code == 200
    assert set(r.json()) == {"a", "b"}


def test_get_missing_404(client):
    assert client.get("/variants/nonexistent").status_code == 404


def _wallgraph_draft():
    """A 20×10 storey with one divider and a drawn passage."""
    return {
        "kind": "wallgraph",
        "name": "gate-smoke",
        "envelope": {"x0": 0, "y0": 0, "x1": 20, "y1": 10},
        "grid": 3.3,
        "segments": [
            {"x0": 0, "y0": 0, "x1": 20, "y1": 0},
            {"x0": 20, "y0": 0, "x1": 20, "y1": 10},
            {"x0": 20, "y0": 10, "x1": 0, "y1": 10},
            {"x0": 0, "y0": 10, "x1": 0, "y1": 0},
            {"x0": 12, "y0": 0, "x1": 12, "y1": 10},
        ],
        "edges": {"0": "facade", "1": "facade", "2": "facade", "3": "facade"},
        "faces": [
            {
                "key": "woon",
                "label": "woon",
                "items": ["*-woon"],
                "area_min": 110,
                "area_max": 130,
                "centroid": [6, 5],
            },
            {
                "key": "bad",
                "label": "bad",
                "items": ["*-bad"],
                "area_min": 60,
                "area_max": 90,
                "centroid": [16, 5],
            },
        ],
    }


def test_gate_scores_a_drawing_against_a_program(client):
    program = {
        "nodes": {
            "A1-woon": {"area_min": 110, "area_max": 130},
            "A1-bad": {"area_min": 60, "area_max": 90},
        },
        "edges": [{"a": "A1-woon", "b": "A1-bad", "kind": "door"}],
    }
    r = client.post(
        "/templates/graph/gate",
        json={"draft": _wallgraph_draft(), "program": program},
    )
    assert r.status_code == 200
    data = r.json()
    assert [f["tag_key"] for f in data["faces"]] == ["woon", "bad"]
    # the divider is a plain wall: the program door is not realised
    assert data["doors"]["blocked"] == 1
    assert data["status"] == "violated"
    assert data["metrics"]["fill_ratio"] == 1.0


def test_gate_accepts_solved_junctions(client):
    program = {
        "nodes": {
            "A1-woon": {"area_min": 110, "area_max": 130},
            "A1-bad": {"area_min": 60, "area_max": 90},
        },
        "edges": [],
    }
    draft = _wallgraph_draft()
    solved = client.post("/templates/graph/solve", json={"draft": draft}).json()
    r = client.post(
        "/templates/graph/gate",
        json={
            "draft": draft,
            "program": program,
            "hints": solved["junctions"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert all(60 <= f["area"] <= 90 for f in data["faces"] if f["tag_key"] == "bad")
