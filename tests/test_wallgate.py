"""plankit.wallgate — harness gate on solved wall graphs."""

from __future__ import annotations

from plankit.program import ProgramEdge, ProgramSpace, RoomProgram
from plankit.wallgate import ensemble_checks, gate, project, solved_strokes
from plankit.wallgraph import WallGraphDraft
from plankit.wallsolve import solve_areas


def _program() -> RoomProgram:
    """Six keys: a core, a corridor, an A1 ensemble (3 rooms), exterior."""
    return RoomProgram(
        nodes={
            "kern": ProgramSpace(area_min=110, area_max=125, core=True, role="verkeer"),
            "gang": ProgramSpace(
                area_min=180, area_max=200, role="verkeer", group=None
            ),
            "A1-slaap1": ProgramSpace(area_min=26, area_max=30, group="A1"),
            "A1-bad1": ProgramSpace(
                area_min=6, area_max=8, wet=True, group="A1", role="facilitair"
            ),
            "A1-keuken1": ProgramSpace(
                area_min=9, area_max=12, wet=True, group="A1", role="facilitair"
            ),
            "buiten": ProgramSpace(exterior=True),
        },
        edges=[
            ProgramEdge(a="A1-slaap1", b="gang", kind="door"),
            ProgramEdge(a="gang", b="buiten", kind="facade"),
            ProgramEdge(a="A1-slaap1", b="buiten", kind="facade"),
        ],
    )


def _draft(divider_y: float = 8.5, passage: str = "open") -> WallGraphDraft:
    """30×12 storey: core (left, big), A1 ensemble (left, top), gang (right).

    ``divider_y`` moves the core/ensemble wall off its solved position so
    the metric solve has work to do; ``passage`` decides the tag of the
    gang boundary stroke above the core: ``"open"`` (a passage, so the
    door is realised), ``"wall"`` (the regions touch across a solid
    wall) or ``None`` (no stroke at all — the regions merge).
    """
    data = {
        "kind": "wallgraph",
        "name": "gate-fixture",
        "envelope": {"x0": 0, "y0": 0, "x1": 30, "y1": 12},
        "grid": 3.3,
        "segments": [
            {"x0": 0, "y0": 0, "x1": 30, "y1": 0},
            {"x0": 30, "y0": 0, "x1": 30, "y1": 12},
            {"x0": 30, "y0": 12, "x1": 0, "y1": 12},
            {"x0": 0, "y0": 12, "x1": 0, "y1": 0},
            {"x0": 14, "y0": 0, "x1": 14, "y1": divider_y},
            {"x0": 0, "y0": divider_y, "x1": 14, "y1": divider_y},
        ],
        "edges": {"0": "facade", "1": "facade", "2": "facade", "3": "facade"},
        "faces": [
            {
                "key": "kern",
                "items": ["kern"],
                "label": "kern",
                "centroid": [7, divider_y / 2],
                "area_min": 110,
                "area_max": 125,
            },
            {
                "key": "A1",
                "items": ["A1-*"],
                "label": "A1",
                "centroid": [7, (divider_y + 12) / 2],
                "area_min": 41,
                "area_max": 50,
            },
            {
                "key": "gang",
                "items": ["gang"],
                "label": "gang",
                "centroid": [22, 6],
                "area_min": 180,
                "area_max": 200,
            },
        ],
    }
    if passage:
        data["segments"].append({"x0": 14, "y0": divider_y, "x1": 14, "y1": 12})
        data["edges"]["6"] = passage
    return WallGraphDraft.from_dict(data)


def test_gate_accepts_a_drawn_ensemble_plan():
    out = gate(_draft(), _program())
    assert out["status"] == "ok"
    c = out["conform"]
    assert c["ok"] and not c["violated"] and not c["missing"]
    assert "space:kern" in c["satisfied"] and "space:gang" in c["satisfied"]
    # the ensemble keys are judged in aggregate, never as "missing"
    assert not [m for m in c["missing"] if m.startswith("A1")]
    assert c["unconstrained"] == sorted(c["unconstrained"])
    ens = out["ensembles"]
    assert len(ens) == 1 and ens[0]["ok"] and ens[0]["band"] == [41, 50]
    assert ens[0]["keys"] == ["A1-bad1", "A1-keuken1", "A1-slaap1"]
    # the drawn access stroke is the realised door, resolved from the
    # ensemble region that holds A1-slaap1 to the gang region
    assert out["doors"]["drawn"] == 1 and out["doors"]["failed"] == 0
    drawn = [d for d in out["doors"]["edges"] if d["status"] == "drawn"]
    assert [d["label"] for d in drawn] == ["edge:A1-slaap1-gang:door"]
    assert not any("no drawn open/access" in n for n in out["notes"])


def test_gate_flags_a_door_without_a_drawn_passage():
    """Regions touching across a solid wall are a door the drawing lacks."""
    out = gate(_draft(passage="wall"), _program())
    assert out["doors"]["blocked"] == 1 and out["doors"]["failed"] == 1
    assert out["doors"]["edges"][0]["status"] == "blocked"
    assert out["status"] == "violated"
    assert any("no drawn open/access" in n for n in out["notes"])


def test_gate_reports_a_sketch_that_forgets_the_wall():
    """No boundary stroke at all: the regions merge and a space goes missing."""
    out = gate(_draft(passage=None), _program())
    assert out["doors"]["edges"][0]["status"] == "unplaced"
    assert "space:gang" in out["conform"]["missing"]
    assert out["status"] == "violated"
    assert any("without a PvE tag" in n for n in out["notes"])


def test_gate_reports_an_ensemble_that_overshoots_its_summed_band():
    program = _program()
    program.nodes["A1-slaap1"].area_min = 26
    program.nodes["A1-slaap1"].area_max = 30
    program.nodes["A1-bad1"].area_max = 8
    program.nodes["A1-keuken1"].area_max = 4  # Σmax = 42 < the drawn 49 m²
    out = gate(_draft(), program)
    assert out["status"] == "violated"
    assert out["ensembles"][0]["ok"] is False
    # the aggregate failure is reported once, and the keys stay covered
    assert out["ensembles"][0]["band"] == [41, 42]
    assert out["doors"]["failed"] == 0
    assert not [m for m in out["conform"]["missing"] if m.startswith("A1")]


def test_gate_on_solved_junctions_reports_the_solved_areas():
    """The gate scores the *solved* drawing, which differs from the drawn one."""
    draft = _draft(divider_y=9.0)
    drawn = gate(draft, _program())
    assert "space:kern:area>125" in drawn["conform"]["violated"]

    solved = solve_areas(draft, 15.0)
    assert solved["status"] == "solved", solved.get("errors")
    out = gate(draft, _program(), junctions=solved["junctions"])
    areas = {f["tag_key"]: f["area"] for f in out["faces"]}
    assert 110 <= areas["kern"] <= 125  # rubber-banded from the drawn 126
    assert out["conform"]["violated"] == []
    assert out["status"] == "ok"
    assert out["metrics"]["fill_ratio"] == 1.0
    assert out["metrics"]["escape_depth"]  # the core anchors the escape graph


def test_gate_is_deterministic_and_ignores_unknown_junctions():
    draft, program = _draft(), _program()
    first = gate(draft, program)
    second = gate(draft, program)
    assert first == second
    noisy = gate(draft, program, junctions=[{"orig": [99, 99], "solved": [1, 1]}])
    assert noisy["faces"] == first["faces"]


def test_solved_strokes_substitutes_only_known_junctions():
    draft = _draft(divider_y=9.0)
    raw = solved_strokes(draft)
    assert [s["y1"] for s in raw] == [0.0, 12.0, 12.0, 0.0, 9.0, 9.0, 12.0]
    moved = solved_strokes(
        draft,
        [
            {"orig": [14, 9.0], "solved": [14.0, 8.5]},
            {"orig": [0, 9.0], "solved": [0.0, 8.5]},
        ],
    )
    assert moved[4]["y1"] == 8.5 and moved[5]["y1"] == 8.5 and moved[6]["y0"] == 8.5
    assert moved[6]["y1"] == 12.0  # its other end was not in the hint set
    assert moved[0] == raw[0]  # untouched strokes stay put


def test_exclusive_face_is_gated_exactly_by_conform():
    """One face = one key: conform judges it directly, no ensemble detour."""
    draft = _draft()
    draft.faces = [f for f in draft.faces if f["key"] != "kern"] + [
        {
            "key": "kern",
            "items": ["kern"],
            "label": "kern",
            "centroid": [7, 4.25],
            "area_min": 110,
            "area_max": 125,
        }
    ]
    program = _program()
    program.nodes["kern"].area_max = 100  # the drawn 119 m² overshoots
    out = gate(draft, program)
    assert "space:kern:area>100" in out["conform"]["violated"]
    assert out["status"] == "violated"
    assert [e["tag"] for e in out["ensembles"]] == ["A1"]
    assert out["doors"]["failed"] == 0


def test_project_labels_faces_and_keeps_ensembles_unlabelled():
    sd, face_tags = project(_draft(), _program())
    assert sd.face_area(next(iter(sd.bounded_faces()))) > 0
    labelled = {f["tag_key"]: f["label_key"] for f in face_tags}
    assert labelled["kern"] == "kern" and labelled["gang"] == "gang"
    assert labelled["A1"] is None  # ensemble: no single program key


def test_ensemble_checks_need_a_full_band():
    program = _program()
    program.nodes["A1-bad1"].area_max = None
    face_tags = [
        {
            "ensemble": True,
            "tag_key": "A1",
            "keys": ["A1-bad1", "A1-slaap1"],
            "area": 49.0,
        }
    ]
    out = ensemble_checks(face_tags, program)
    assert out[0]["band"] == [32, None] and out[0]["ok"] is True


def test_door_is_found_in_a_wall_with_a_passage():
    """Two rooms separated by wall + passage + wall share three noded edges.

    Only the middle one is an opening, so a first-match lookup reports the
    door as blocked and the circulation metrics lose their door edge.
    """
    draft = _draft(passage=None)
    # the ensemble|gang boundary as wall + passage + wall
    draft.segments.append({"x0": 14, "y0": 10, "x1": 14, "y1": 11})
    draft.segments.append({"x0": 14, "y0": 11, "x1": 14, "y1": 12})
    draft.segments.append({"x0": 14, "y0": 8.5, "x1": 14, "y1": 10})
    draft.edges[6] = "access"
    draft.edges[7] = "wall"
    draft.edges[8] = "wall"
    out = gate(draft, _program())
    assert out["doors"]["drawn"] == 1 and out["doors"]["blocked"] == 0
    assert out["status"] == "ok"
    # the door edge reaches the circulation metrics: the ensemble and the
    # corridor are one step apart (the core has no program door, so it
    # stays isolated — an honest reachability finding, not a bug)
    comps = out["metrics"]["access_components"]
    assert comps["root"] == "kern"  # the core is the access root
    assert comps["components"] == 2  # the core stands alone: no program door
    assert set(comps["unreachable"]) == {"gang", "A1"}
