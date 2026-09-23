# This file was generated with the assistance of an AI coding tool.
"""FastAPI-API (frontend-agnostisch) over de plankit-library.

De API levert JSON (geometry + rapport); de frontend rendert. `GET
/variants/{id}/svg` is een convenience voor server-side rendering. Bewust niet
geïmporteerd door `plankit/__init__.py` — fastapi is een optionele `[api]`-extra.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from plankit.generate import generate
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram
from plankit.store import VariantStore, make_variant
from plankit.svg import geometry_view, to_svg


class GenerateRequest(BaseModel):
    program: dict
    label: str | None = None
    parent_id: str | None = None


class ReviseRequest(BaseModel):
    proposal: dict | None = None
    label: str | None = None


def create_app(store: VariantStore | None = None) -> FastAPI:
    """Bouw de FastAPI-app; ``store`` is injecteerbaar (default in-memory)."""
    store = store or VariantStore(":memory:")
    app = FastAPI(title="plankit", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
        d.update({"program": v.program, "report": v.report, "geometry": geometry_view(sd)})
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
            make_variant(sd, program, step=len(store.all()), label=req.label, parent_id=req.parent_id)
        )
        return _detail(v)

    @app.post("/variants/{vid}/revise")
    def revise_variant(vid: str, req: ReviseRequest):
        parent = store.get(vid)
        if parent is None:
            raise HTTPException(status_code=404, detail="ouder niet gevonden")
        program = RoomProgram.from_dict(parent.program)
        sd = generate(program, proposal=req.proposal) if req.proposal else generate(program)
        v = store.add(
            make_variant(
                sd, program, step=len(store.all()), label=req.label, parent_id=vid, proposal=req.proposal
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
        return {"a": {"id": va.id, "report": va.report}, "b": {"id": vb.id, "report": vb.report}}

    return app


app = create_app()
