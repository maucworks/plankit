# This file was generated with the assistance of an AI coding tool.
"""Tests for the template authoring model, store and canvas endpoints."""

import pytest
from fastapi.testclient import TestClient

from plankit.api import create_app
from plankit.program import ProgramEdge, ProgramSpace
from plankit.program import RoomProgram
from plankit.store import VariantStore
from plankit.templates import (
    Band,
    TemplateDraft,
    TemplateStore,
    Zone,
)


def _draft() -> TemplateDraft:
    return TemplateDraft(
        name="open-kern",
        description="test",
        envelope=Band(0, 0, 40, 26),
        grid=3.3,
        zones=[
            Zone(
                key="access",
                mode="access",
                band=Band(0, 11, 40, 13.5),
                items=["*-woon", "gang"],
                priors={"door_every": 3.3},
            ),
            Zone(
                key="living",
                mode="room",
                band=Band(0, 13.5, 20, 26),
                items=["*-woon", "keuken"],
                priors={"aspect": "[1.0,1.8]"},
            ),
            Zone(
                key="wet",
                mode="block",
                band=Band(0, 0, 20, 11),
                items=["*-bad", "*-berg"],
            ),
            Zone(
                key="sleep", mode="room", band=Band(20, 13.5, 40, 26), items=["slaap.*"]
            ),
            Zone(key="kern", mode="core", band=Band(17, 0, 22, 6), items=["kern"]),
            Zone(
                key="keuken-strip",
                mode="open",
                band=Band(0.5, 14, 6, 18),
                items=["*-keuken"],
                sub_zone_of="living",
            ),
        ],
    )


def _program() -> RoomProgram:
    nodes = {
        "A1-woon": ProgramSpace(name="A1-woon", area_min=15, entrance=True),
        "A1-slaap1": ProgramSpace(name="A1-slaap1", area_min=10),
        "A1-keuken": ProgramSpace(name="A1-keuken", area_min=4),
        "A1-bad": ProgramSpace(name="A1-bad", area_min=6),
        "A1-berg": ProgramSpace(name="A1-berg", area_min=5),
        "gang": ProgramSpace(name="gang", area_min=30),
        "kern": ProgramSpace(name="kern", area_min=25),
        "buiten": ProgramSpace(name="buiten", exterior=True),
    }
    edges = [
        ProgramEdge("A1-woon", "gang", kind="door"),
        ProgramEdge("A1-woon", "A1-keuken", kind="door"),
        ProgramEdge("gang", "kern", kind="door"),
        ProgramEdge("A1-woon", "buiten", kind="facade"),
    ]
    return RoomProgram(nodes=nodes, edges=edges)


# ── model ───────────────────────────────────────────────────────────────


def test_round_trip():
    d = _draft()
    d2 = TemplateDraft.from_dict(d.to_dict())
    assert d2.to_dict() == d.to_dict()


def test_validate_clean():
    assert _draft().validate() == []


def test_validate_band_outside_envelope():
    d = _draft()
    d.zones[1].band = Band(0, 13.5, 45, 26)  # beyond the 40 m envelope
    errs = d.validate()
    assert any("band-outside-envelope" in e for e in errs)


def test_validate_zone_inverted_band():
    d = _draft()
    d.zones[0].band = Band(10, 11, 2, 13.5)
    errs = d.validate()
    assert any("band-inverted" in e for e in errs)


def test_validate_duplicate_key():
    d = _draft()
    d.zones.append(Zone(key="living", mode="room", band=Band(0, 0, 5, 5)))
    errs = d.validate()
    assert any("key-duplicate" in e for e in errs)


def test_validate_strip_not_contained():
    d = _draft()
    d.zones[5].band = Band(19, 14, 25, 18)  # pokes out of living (0..20)
    errs = d.validate()
    assert any("strip-not-contained" in e for e in errs)


def test_validate_sub_zone_of_unknown():
    d = _draft()
    d.zones[5].sub_zone_of = "nope"
    errs = d.validate()
    assert any("sub-zone-of-unknown" in e for e in errs)


def test_validate_strip_owner_not_enabling():
    d = _draft()
    d.zones[5].sub_zone_of = "kern"  # core cannot hold open strips
    errs = d.validate()
    assert any("strip-owner-mode-not-enabling" in e for e in errs)


def test_validate_unknown_mode():
    d = _draft()
    d.zones[0].mode = "sheet"
    errs = d.validate()
    assert any("mode<" in e for e in errs)


def test_coverage_fnmatch_wildcards_and_ensemble():
    d = _draft()
    covered, uncovered = d.coverage(_program())
    assert "A1-woon" in covered  # access items `*-woon` and living
    assert "A1-slaap1" in covered  # `slaap.*` stem-matches A1-slaap1
    assert "A1-keuken" in covered  # open strip
    assert "kern" in covered  # core zone
    assert uncovered == []


def test_previews_svg_reaction():
    svg = _draft().preview_svg()
    assert "<svg" in svg and "access · access" in svg and 'stroke="#9a3412"' in svg


# ── store ───────────────────────────────────────────────────────────────


def test_store_save_list_load_delete(tmp_path):
    st = TemplateStore(str(tmp_path))
    assert st.list() == []
    st.save("open-kern", _draft())
    assert st.list() == ["open-kern"]
    st.load("open-kern").to_dict() == _draft().to_dict()
    assert st.delete("open-kern") is True and st.list() == []


def test_store_rejects_path_traversal(tmp_path):
    st = TemplateStore(str(tmp_path))
    with pytest.raises(Exception):
        st.save("../evil", _draft())


# ── canvas endpoints ───────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path):
    store = VariantStore(str(tmp_path / "v.db"))
    tstore = TemplateStore(str(tmp_path / "tpl"))
    return TestClient(create_app(store, template_store=tstore))


def test_canvas_served(client):
    r = client.get("/templates/canvas")
    assert r.status_code == 200
    assert "template sketch canvas" in r.text and "<svg" in r.text


def test_draft_save_list_load_validate_roundtrip(client):
    body = _draft().to_dict()
    r = client.post("/templates/drafts/open-kern", json={"draft": body})
    assert r.status_code == 200 and r.json() == {"saved": "open-kern", "errors": []}
    assert client.get("/templates/drafts").json() == ["open-kern"]
    r = client.get("/templates/drafts/open-kern")
    assert r.status_code == 200 and r.json() == body
    r = client.post("/templates/drafts/open-kern/validate", json={"draft": body})
    assert r.status_code == 200 and r.json()["errors"] == []


def test_validate_with_coverage(client):
    prog = _program().to_dict()
    body = _draft().to_dict()
    r = client.post(
        "/templates/drafts/open-kern/validate", json={"draft": body, "program": prog}
    )
    out = r.json()
    assert (
        out["errors"] == [] and out["uncovered"] == [] and "A1-woon" in out["covered"]
    )


def test_validate_reports_draft_errors(client):
    body = _draft().to_dict()
    body["zones"][0]["band"]["x1"] = 45  # outside the 40 m envelope
    r = client.post("/templates/drafts/open-kern/validate", json={"draft": body})
    assert any("band-outside-envelope" in e for e in r.json()["errors"])


def test_preview_svg_endpoint(client):
    r = client.post("/templates/drafts/render", json={"draft": _draft().to_dict()})
    assert r.status_code == 200 and "image/svg+xml" in r.headers["content-type"]
    assert "<svg" in r.text


def test_draft_name_traversal_rejected(client):
    r = client.post("/templates/drafts/..%2Fevil", json=_draft().to_dict())
    assert r.status_code >= 400
