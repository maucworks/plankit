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
