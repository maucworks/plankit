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


# ── rooms with other than four edges ──────────────────────────────────


def _envelope():
    return [
        {"x0": 0, "y0": 0, "x1": 30, "y1": 0},
        {"x0": 30, "y0": 0, "x1": 30, "y1": 20},
        {"x0": 30, "y0": 20, "x1": 0, "y1": 20},
        {"x0": 0, "y0": 20, "x1": 0, "y1": 0},
    ]


def test_triangle_face_counts_as_a_room():
    """Envelope + one diagonal stroke: the leftover face is a TRIANGLE
    (3 corners) and noding still reports it as a room."""
    d = _draft()
    d["segments"] = _envelope() + [{"x0": 0, "y0": 20, "x1": 30, "y1": 0}]
    faces = WallGraphDraft.from_dict(d).noded_faces()
    assert any(len(f["verts"]) == 3 for f in faces), faces
    assert abs(sum(f["area"] for f in faces) - 30 * 20) < 0.01


def test_nested_room_gives_L_shaped_remainder():
    """Quad + nested room in a corner → small room + L-shaped remainder
    (6 edges); both are faces, areas tile exactly."""
    d = _draft()
    d["segments"] = _envelope() + [
        {"x0": 0, "y0": 12, "x1": 12, "y1": 12},
        {"x0": 12, "y0": 12, "x1": 12, "y1": 20},
    ]
    faces = WallGraphDraft.from_dict(d).noded_faces()
    assert len(faces) == 2
    assert any(len(f["verts"]) == 6 for f in faces)  # the L remainder
    assert abs(sum(f["area"] for f in faces) - 30 * 20) < 0.01


# ── helpers + bindings model ───────────────────────────────────────────


def test_helpers_and_bindings_roundtrip():
    d = _draft()
    d["helpers"] = {
        "master": {"axis": "horizontal", "pos": 0.0, "module": 3.3},
        "lines": [{"id": "L1", "axis": "horizontal", "offset": 9.5}],
    }
    d["bindings"] = [{"line": "L1", "junction": {"x": 0.0, "y": 10.0}}]
    draft = WallGraphDraft.from_dict(d)
    assert draft.to_dict()["helpers"] == d["helpers"]
    assert draft.to_dict()["bindings"] == d["bindings"]


def test_binding_on_unknown_line_flags():
    d = _draft()
    d["helpers"] = {
        "master": {"axis": "horizontal", "pos": 0.0, "module": 3.3},
        "lines": [],
    }
    d["bindings"] = [{"line": "LX", "junction": {"x": 3.0, "y": 3.0}}]
    errs = WallGraphDraft.from_dict(d).validate()
    assert any("unknown-line" in e for e in errs)


def test_grid_bound_divider_solves_on_the_line():
    """The divider is bound to a helper line at master + 9.5 m: the solve
    must place it there exactly, giving wet = 380 m2."""
    from plankit.wallsolve import solve_areas

    d = _draft()
    d["segments"] = [
        {"x0": 0, "y0": 0, "x1": 40, "y1": 0},
        {"x0": 40, "y0": 0, "x1": 40, "y1": 26},
        {"x0": 40, "y0": 26, "x1": 0, "y1": 26},
        {"x0": 0, "y0": 26, "x1": 0, "y1": 0},
        {"x0": 0, "y0": 10, "x1": 40, "y1": 10},
    ]
    d["edges"] = {"0": "facade", "1": "facade", "2": "facade", "3": "facade"}
    d["faces"] = [
        {
            "key": "living",
            "label": "living",
            "items": ["*-woon"],
            "area_min": 660,
            "area_max": 662,
            "centroid": [20, 18],
        },
        {
            "key": "wet",
            "label": "wet",
            "items": ["*-bad"],
            "area_min": 378,
            "area_max": 380,
            "centroid": [20, 5],
        },
    ]
    d["helpers"] = {
        "master": {"axis": "horizontal", "pos": 0.0, "module": 3.3},
        "lines": [{"id": "L1", "axis": "horizontal", "offset": 9.5}],
    }
    d["bindings"] = [
        {"line": "L1", "junction": {"x": 0.0, "y": 10.0}},
        {"line": "L1", "junction": {"x": 40.0, "y": 10.0}},
    ]
    out = solve_areas(WallGraphDraft.from_dict(d), 25.0)
    assert out["status"] == "solved"
    areas = {f["key"]: f["area"] for f in out["faces"]}
    assert areas["living"] == 660.0 and areas["wet"] == 380.0


def test_grid_conflict_names_the_binding():
    from plankit.wallsolve import solve_areas

    d = _draft()
    d["segments"] = [
        {"x0": 0, "y0": 0, "x1": 40, "y1": 0},
        {"x0": 40, "y0": 0, "x1": 40, "y1": 26},
        {"x0": 40, "y0": 26, "x1": 0, "y1": 26},
        {"x0": 0, "y0": 26, "x1": 0, "y1": 0},
        {"x0": 0, "y0": 10, "x1": 40, "y1": 10},
    ]
    d["faces"] = [
        {
            "key": "living",
            "label": "living",
            "items": ["*-woon"],
            "area_min": 704,
            "area_max": 706,
            "centroid": [20, 18],
        },
        {
            "key": "wet",
            "label": "wet",
            "items": ["*-bad"],
            "area_min": 326,
            "area_max": 328,
            "centroid": [20, 5],
        },
    ]
    d["helpers"] = {
        "master": {"axis": "horizontal", "pos": 0.0, "module": 3.3},
        "lines": [{"id": "L1", "axis": "horizontal", "offset": 9.5}],
    }
    d["bindings"] = [
        {"line": "L1", "junction": {"x": 0.0, "y": 10.0}},
        {"line": "L1", "junction": {"x": 40.0, "y": 10.0}},
    ]
    out = solve_areas(WallGraphDraft.from_dict(d), 25.0)
    assert out["status"] == "infeasible"
    assert any("on line 'L1'" in c for c in out["conflicts"])
