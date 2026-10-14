# This file was generated with the assistance of an AI coding tool.
"""FastAPI-API (frontend-agnostisch) over de plankit-library.

De API levert JSON (geometry + rapport); de frontend rendert. `GET
/variants/{id}/svg` is een convenience voor server-side rendering. Bewust niet
geïmporteerd door `plankit/__init__.py` — fastapi is een optionele `[api]`-extra.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from plankit.generate import generate
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram
from plankit.store import VariantStore, make_variant
from plankit.svg import geometry_view, to_svg
from plankit.templates import TemplateDraft, TemplateStore
from plankit.wallsolve import solve_areas
from plankit.wallgraph import WallGraphDraft, WallGraphStore, draft_preview_svg


class GenerateRequest(BaseModel):
    program: dict
    label: str | None = None
    parent_id: str | None = None


class DraftRequest(BaseModel):
    draft: dict


class ValidateRequest(DraftRequest):
    program: dict | None = None


class SolveRequest(DraftRequest):
    hints: list[dict] | None = None
    budget: float | None = None


class ReviseRequest(BaseModel):
    proposal: dict | None = None
    label: str | None = None


def create_app(
    store: VariantStore | None = None, template_store: TemplateStore | None = None
) -> FastAPI:
    """Bouw de FastAPI-app; ``store`` is injecteerbaar (default in-memory)."""
    store = store or VariantStore(":memory:")
    app = FastAPI(title="plankit", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    def _summary(v):
        return {
            "id": v.id,
            "parent_id": v.parent_id,
            "step": v.step,
            "label": v.label,
            "created_at": v.created_at,
        }

    def _detail(v):
        sd = PlanarSubdivision.from_dict(v.state)
        d = _summary(v)
        d.update(
            {"program": v.program, "report": v.report, "geometry": geometry_view(sd)}
        )
        return d

    @app.get("/variants")
    def list_variants():
        return [_summary(v) for v in store.all()]

    @app.get("/variants/{vid}")
    def get_variant(vid: str):
        v = store.get(vid)
        if v is None:
            raise HTTPException(status_code=404, detail="variant niet gevonden")
        return _detail(v)

    @app.post("/generate")
    def generate_variant(req: GenerateRequest):
        program = RoomProgram.from_dict(req.program)
        sd = generate(program)
        v = store.add(
            make_variant(
                sd,
                program,
                step=len(store.all()),
                label=req.label,
                parent_id=req.parent_id,
            )
        )
        return _detail(v)

    @app.post("/variants/{vid}/revise")
    def revise_variant(vid: str, req: ReviseRequest):
        parent = store.get(vid)
        if parent is None:
            raise HTTPException(status_code=404, detail="ouder niet gevonden")
        program = RoomProgram.from_dict(parent.program)
        sd = (
            generate(program, proposal=req.proposal)
            if req.proposal
            else generate(program)
        )
        v = store.add(
            make_variant(
                sd,
                program,
                step=len(store.all()),
                label=req.label,
                parent_id=vid,
                proposal=req.proposal,
            )
        )
        return _detail(v)

    @app.get("/variants/{vid}/svg")
    def variant_svg(vid: str):
        v = store.get(vid)
        if v is None:
            raise HTTPException(status_code=404, detail="variant niet gevonden")
        sd = PlanarSubdivision.from_dict(v.state)
        return Response(to_svg(sd), media_type="image/svg+xml")

    @app.get("/compare")
    def compare(a: str, b: str):
        va, vb = store.get(a), store.get(b)
        if va is None or vb is None:
            raise HTTPException(status_code=404, detail="variant niet gevonden")
        return {
            "a": {"id": va.id, "report": va.report},
            "b": {"id": vb.id, "report": vb.report},
        }

    # ── template canvas (dev feature) ─────────────────────────────

    tstore = template_store or TemplateStore()

    @app.get("/templates/canvas")
    def template_canvas():
        """Serve the sketch-canvas authoring page (self-contained HTML)."""
        page = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "canvas"
            / "template_canvas.html"
        )
        return FileResponse(str(page), media_type="text/html")

    @app.get("/templates/drafts")
    def list_drafts():
        return tstore.list()

    @app.post("/templates/drafts/render")
    def preview_draft(req: DraftRequest):
        """SVG zoning diagram from a raw draft body (canvas in-page preview)."""
        d = TemplateDraft.from_dict(req.draft)
        return Response(d.preview_svg(), media_type="image/svg+xml")

    @app.get("/templates/drafts/{name}")
    def get_draft(name: str):
        draft = tstore.load(name)
        return draft.to_dict()

    @app.post("/templates/drafts/{name}")
    def save_draft(name: str, req: DraftRequest):
        d = TemplateDraft.from_dict(req.draft)
        errors = d.validate()
        tstore.save(name, d)
        return {"saved": name, "errors": errors}

    @app.post("/templates/drafts/{name}/validate")
    def validate_draft(name: str, req: ValidateRequest):
        """Dry-run: draft errors, plus PvE coverage when a program is given."""
        d = TemplateDraft.from_dict(req.draft)
        out = {"errors": d.validate()}
        if req.program is not None:
            prog = RoomProgram.from_dict(req.program)
            covered, uncovered = d.coverage(prog)
            out["covered"] = covered
            out["uncovered"] = uncovered
        return out

    # ── wall-graph canvas (dev feature: template = a drawing) ─────

    wstore = WallGraphStore(str(tstore.dir))

    @app.get("/templates/graph/canvas")
    def wallgraph_canvas():
        """Serve the wall-graph sketch page (polyline drawing front-end)."""
        page = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "canvas"
            / "wall_canvas.html"
        )
        return FileResponse(str(page), media_type="text/html")

    @app.post("/templates/graph/noding")
    def wallgraph_noding(req: DraftRequest):
        """Node the drawn segments (shapely) → bounded faces + tag match."""
        d = WallGraphDraft.from_dict(req.draft)
        try:
            faces = d.noded_faces()
        except Exception as exc:  # shapely missing or degenerate strokes
            raise HTTPException(
                status_code=503, detail=f"noding failed: {exc}"
            ) from exc
        return {"faces": faces, "errors": d.validate()}

    @app.post("/templates/graph/preview")
    def wallgraph_preview(req: DraftRequest):
        """SVG render of the drawing (strokes, face shading, edge tags)."""
        d = WallGraphDraft.from_dict(req.draft)
        return Response(draft_preview_svg(d), media_type="image/svg+xml")

    @app.post("/templates/graph/solve")
    def wallgraph_solve(req: SolveRequest):
        """Rubber-band solve: junction coordinates so face areas hit their bands.

        Optional ``hints`` (previous solution) + ``budget`` (seconds) power
        the interactive drag re-solve; budget-less calls keep the full
        certified budget.
        """
        d = WallGraphDraft.from_dict(req.draft)
        budget = req.budget if req.budget and req.budget > 0 else None
        try:
            return solve_areas(d, seconds=budget or 15.0, hints=req.hints or None)
        except Exception as exc:  # malformed draft, ortools hiccup
            raise HTTPException(status_code=503, detail=f"solve failed: {exc}") from exc

    @app.post("/templates/graph/drafts/{name}")
    def wallgraph_save(name: str, req: DraftRequest):
        d = WallGraphDraft.from_dict(req.draft)
        errors = d.validate()
        wstore.save(name, d)
        return {"saved": name, "errors": errors}

    @app.get("/templates/graph/drafts/{name}")
    def wallgraph_get(name: str):
        try:
            return wstore.load_wallgraph(name).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/templates/graph/drafts")
    def wallgraph_list():
        """Names of the wallgraph drafts (other canvas keeps its own)."""
        return wstore.list()

    return app


app = create_app()
