# This file was generated with the assistance of an AI coding tool.
"""Tests for the wall-graph draft model and its canvas endpoints.

The wall graph is the "template = a drawing" model: drawn segments are
noded by ``PlanarSubdivision.from_centerlines``, closed regions fall out
as faces, face tags match by centroid, edge tags style strokes.
"""

import pytest
from fastapi.testclient import TestClient

from plankit.api import create_app
from plankit.store import VariantStore
from plankit.templates import TemplateDraft, TemplateStore
from plankit.wallgraph import WallGraphDraft, WallGraphStore


def _draft() -> dict:
    return {
        "kind": "wallgraph",
        "name": "open-kern-wall",
        "description": "test",
        "envelope": {"x0": 0, "y0": 0, "x1": 40, "y1": 26},
        "grid": 3.3,
        "segments": [
            {"x0": 0, "y0": 0, "x1": 40, "y1": 0},
            {"x0": 40, "y0": 0, "x1": 40, "y1": 26},
            {"x0": 40, "y0": 26, "x1": 0, "y1": 26},
            {"x0": 0, "y0": 26, "x1": 0, "y1": 0},
            {"x0": 0, "y0": 10, "x1": 40, "y1": 10},
        ],
        "edges": {"0": "facade", "1": "facade", "2": "facade", "3": "facade"},
        "faces": [
            {
                "key": "living",
                "label": "living",
                "items": ["*-woon"],
                "area_min": 20,
                "area_max": 30,
                "centroid": [20, 18],
            },
            {
                "key": "wet",
                "label": "wet",
                "items": ["*-bad", "keuken.*"],
                "area_min": 10,
                "area_max": 14,
                "centroid": [20, 5],
            },
        ],
    }


@pytest.fixture
def client(tmp_path):
    store = VariantStore(str(tmp_path / "v.db"))
    tstore = TemplateStore(str(tmp_path / "tpl"))
    return TestClient(create_app(store, template_store=tstore))


# ── model: noding + matching + validation ──────────────────────────────


def test_noding_faces_match_tags():
    d = WallGraphDraft.from_dict(_draft())
    faces = d.noded_faces()
    areas = sorted(f["area"] for f in faces)
    assert len(faces) == 2 and abs(sum(areas) - 40 * 26) < 0.01
    by_label = {f["label"]: f for f in faces if f["matched"]}
    assert set(by_label) == {"living", "wet"}
    assert by_label["living"]["area_min"] == 20 and by_label["wet"]["items"] == [
        "*-bad",
        "keuken.*",
    ]


def test_noding_skips_slivers():
    draft = _draft()
    draft["segments"].append(
        {"x0": 0, "y0": 0, "x1": 0.001, "y1": 0}
    )  # zero-effect stroke
    d = WallGraphDraft.from_dict(draft)
    assert all(f["area"] > 1.0 for f in d.noded_faces())


def test_t_junction_regions():
    """A line ending on another line (T) → the touched line splits on noding."""
    draft = _draft()
    draft["segments"] = [
        {"x0": 0, "y0": 0, "x1": 40, "y1": 0},
        {"x0": 40, "y0": 0, "x1": 40, "y1": 26},
        {"x0": 40, "y0": 26, "x1": 0, "y1": 26},
        {"x0": 0, "y0": 26, "x1": 0, "y1": 0},
        {"x0": 20, "y0": 26, "x1": 20, "y1": 13},
    ]
    d = WallGraphDraft.from_dict(draft)
    faces = d.noded_faces()
    assert len(faces) == 1 and abs(faces[0]["area"] - 40 * 26) < 0.01


def test_validate_reports_envelope_and_kinds():
    draft = _draft()
    draft["segments"][4]["y0"] = 10
    draft["segments"].append(
        {"x0": 45, "y0": 0, "x1": 45, "y1": 26}
    )  # outside the envelope
    draft["edges"]["5"] = "irgendwas"
    d = WallGraphDraft.from_dict(draft)
    errs = d.validate()
    assert any("envelope-outer-region" in e for e in errs)
    assert any("unknown-kind" in e for e in errs)


# ── store ──────────────────────────────────────────────────────────────


def test_store_kind_gate(tmp_path):
    st = TemplateStore(str(tmp_path))
    wg = WallGraphStore(str(tmp_path))
    wg.save("open-kern-wall", WallGraphDraft.from_dict(_draft()))
    assert wg.list() == ["open-kern-wall"]  # wallgraphs are the only kind saved here
    st.save(
        "zonedraft",
        TemplateDraft.from_dict(
            {
                "name": "zonedraft",
                "envelope": {"x0": 0, "y0": 0, "x1": 10, "y1": 10},
                "grid": 3.0,
                "zones": [],
            }
        ),
    )
    assert wg.list() == [
        "open-kern-wall"
    ]  # the zone draft does not present as a wallgraph
    with pytest.raises(ValueError):
        wg.load_wallgraph("zonedraft")


def test_store_rejects_path_traversal(tmp_path):
    st = WallGraphStore(str(tmp_path))
    with pytest.raises(Exception):
        st.save("../evil-wall", WallGraphDraft.from_dict(_draft()))


# ── endpoints ──────────────────────────────────────────────────────────


def test_canvas_served(client):
    r = client.get("/templates/graph/canvas")
    assert r.status_code == 200 and "wall graph canvas" in r.text


def test_noding_endpoint(client):
    r = client.post("/templates/graph/noding", json={"draft": _draft()})
    assert r.status_code == 200
    out = r.json()
    assert len(out["faces"]) == 2 and out["errors"] == []
    assert all(f["matched"] for f in out["faces"])


def test_preview_endpoint(client):
    r = client.post("/templates/graph/preview", json={"draft": _draft()})
    assert r.status_code == 200 and "image/svg+xml" in r.headers["content-type"]
    assert "<svg" in r.text and "living · 640.0 m" in r.text  # tag+area labels land


def test_saved_draft_roundtrip_and_list(client):
    body = _draft()
    r = client.post("/templates/graph/drafts/open-kern-wall", json={"draft": body})
    assert r.status_code == 200 and r.json() == {
        "saved": "open-kern-wall",
        "errors": [],
    }
    assert client.get("/templates/graph/drafts").json() == ["open-kern-wall"]
    got = client.get("/templates/graph/drafts/open-kern-wall").json()
    assert got["segments"] == body["segments"] and got["kind"] == "wallgraph"
    assert (
        client.post(
            "/templates/graph/drafts/open-kern-wall", json={"draft": body}
        ).json()["saved"]
        == "open-kern-wall"
    )


def test_zone_draft_not_visible_as_wallgraph(client):
    client.post(
        "/templates/drafts/zonedraft",
        json={
            "draft": {
                "name": "zonedraft",
                "envelope": {"x0": 0, "y0": 0, "x1": 10, "y1": 10},
                "grid": 3.0,
                "zones": [],
            }
        },
    )
    assert client.get("/templates/graph/drafts").json() == []
    assert client.get("/templates/graph/drafts/zonedraft").status_code == 404
