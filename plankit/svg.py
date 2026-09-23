# This file was generated with the assistance of an AI coding tool.
"""SVG-rendering en browser-scrub voor skeletten."""

from __future__ import annotations

import json

from plankit.planar import PlanarSubdivision

_PALETTE = ["#e8f0fe", "#fce8e6", "#e6f4ea", "#fef7e0", "#f3e8fd", "#e0f7fa", "#fff3e0", "#ede7f6"]

_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>plankit scrub</title>
<style>
body{{font-family:system-ui,sans-serif;margin:1rem}}
#frame{{border:1px solid #ccc;display:inline-block}}
#report{{font-family:monospace;white-space:pre;margin-top:.5rem}}
#bar{{width:100%}}
</style></head><body>
<h1>plankit — generatie-scrub</h1>
<input id="bar" type="range" min="0" max="{n}" value="0">
<div id="label"></div>
<div id="frame"></div>
<div id="report"></div>
<script>
const FRAMES = {frames};
function show(i){{
  const f = FRAMES[i];
  document.getElementById("label").textContent = f.step + " — " + f.label;
  document.getElementById("frame").innerHTML = f.svg;
  document.getElementById("report").textContent = JSON.stringify(f.report, null, 2);
}}
const bar = document.getElementById("bar");
bar.addEventListener("input", e => show(Number(e.target.value)));
show(0);
</script></body></html>"""


def _bounds(sd: PlanarSubdivision) -> tuple[float, float, float, float]:
    xs = [v.x for v in sd.vertices]
    ys = [v.y for v in sd.vertices]
    return min(xs), min(ys), max(xs), max(ys)


def to_svg(sd: PlanarSubdivision, width: int = 640, height: int = 480) -> str:
    """Render de faces (gekleurd), labels en door-edges (rood gestippeld)."""
    if not sd.vertices:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    x0, y0, x1, y1 = _bounds(sd)
    pad = 8.0
    scale = min(
        (width - 2 * pad) / max(x1 - x0, 1e-9),
        (height - 2 * pad) / max(y1 - y0, 1e-9),
    )

    def sx(x: float) -> float:
        return pad + (x - x0) * scale

    def sy(y: float) -> float:
        return height - pad - (y - y0) * scale

    parts = [f'<rect width="{width}" height="{height}" fill="white"/>']
    for fid in sd.bounded_faces():
        pts = sd.face_vertices(fid)
        poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
        parts.append(
            f'<polygon points="{poly}" fill="{_PALETTE[fid % len(_PALETTE)]}" stroke="#555" stroke-width="1"/>'
        )

    for he_id, he in enumerate(sd.half_edges):
        if he.kind != "door":
            continue
        if he_id > he.twin:
            continue  # elk twin-paar één keer
        a = sd.vertices[he.origin]
        b = sd.vertices[sd.half_edges[he.next].origin]
        parts.append(
            f'<line x1="{sx(a.x):.1f}" y1="{sy(a.y):.1f}" x2="{sx(b.x):.1f}" y2="{sy(b.y):.1f}" '
            f'stroke="red" stroke-width="3" stroke-dasharray="6,4"/>'
        )

    for fid in sd.bounded_faces():
        pts = sd.face_vertices(fid)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        label = sd.faces[fid].label or str(fid)
        parts.append(
            f'<text x="{sx(cx):.1f}" y="{sy(cy):.1f}" text-anchor="middle" '
            f'font-size="12" fill="#222">{label}</text>'
        )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">' + "".join(parts) + "</svg>"


def scrub_page(variants, width: int = 640, height: int = 480) -> str:
    """Bouw een zelfstandige HTML-scrubpagina uit een lijst van varianten."""
    frames = []
    for v in variants:
        sd = PlanarSubdivision.from_dict(v.state)
        frames.append(
            {
                "step": v.step,
                "label": v.label or v.id[:8],
                "svg": to_svg(sd, width, height),
                "report": v.report,
            }
        )
    max_i = max(len(frames) - 1, 0)
    return _HTML.replace("{n}", str(max_i)).replace("{frames}", json.dumps(frames))


def geometry_view(sd: PlanarSubdivision) -> dict:
    """Frontend-vriendelijke geometry: faces (polygonen + label) en deur-edges."""
    faces = []
    for fid in sd.bounded_faces():
        faces.append(
            {
                "id": str(fid),
                "label": sd.faces[fid].label or str(fid),
                "points": sd.face_vertices(fid),
            }
        )
    ext = sd.exterior_face()
    doors = []
    for he_id, he in enumerate(sd.half_edges):
        if he.kind != "door":
            continue
        twin = sd.half_edges[he.twin]
        if he.face == ext or twin.face == ext:
            continue
        if he_id > he.twin:
            continue  # elk twin-paar één keer (zelfde segment)
        a = sd.vertices[he.origin]
        b = sd.vertices[sd.half_edges[he.next].origin]
        doors.append({"x1": a.x, "y1": a.y, "x2": b.x, "y2": b.y})
    return {"faces": faces, "doors": doors}
