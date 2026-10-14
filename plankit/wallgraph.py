# This file was generated with the assistance of an AI coding tool.
"""plankit.wallgraph — authoring model for wall-graph templates (dev feature).

Rethinky model: a *template is a drawing*. The author sketches wall
centerlines on a canvas; the sketch is stored as a segment list. Rooms
are not placed anywhere — they *are* the closed faces of the drawn
graph: ``PlanarSubdivision.from_centerlines`` nodes the segments at
crossings and T-junctions, and every closed region falls out as a face
("put a point on a line and it splits" is the noder's native act, same
as on the canvas).

Draft layers:

- ``segments`` — wall centerline strokes (metres).
- ``edges``   — per-segment tag: ``wall`` (materialised), ``open``
  (drawn for the Demarcation but not walled: the bleeding kitchen
  boundary, access spine bands), ``facade`` (envelope). Kinds are
  vocabulary shared with the face/zone model (``templates.ZONE_MODES``).
- ``faces``   — designations of drawn regions: item patterns (fnmatch),
  area band (min/max in m²) and the centroid of the face at tag time.
  Faces re-identified after edits by nearest centroid (tolerance
  ``FACE_MATCH_TOL``) — tags follow the drawing, not vertex noise.

Rooms are guaranteed non-overlapping by planarity, so the solver's
remaining job on a fixed topology is metric: face areas (shoelace),
edge lengths for door slots, facade contact — see PLAN-generator-v2's
metric-solve note.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from plankit.planar import PlanarSubdivision
from plankit.templates import Band, TemplateStore

EPS_AREA = 0.05  # m²; sub-sliver faces of the noder are not rooms
FACE_MATCH_TOL = 2.5  # m; nearest-centroid matching for face tags
EDGE_KINDS = ("wall", "open", "access", "facade")


@dataclass
class WallGraphDraft:
    """Draft of one wall-graph template (canvas output, JSON on disk)."""

    name: str
    description: str = ""
    envelope: Band = field(default_factory=lambda: Band(0, 0, 40, 26))
    grid: float = 3.3
    segments: List[Dict[str, float]] = field(default_factory=list)
    edges: Dict[int, str] = field(default_factory=dict)
    faces: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a plain JSON-safe dict."""
        return {
            "kind": "wallgraph",
            "name": self.name,
            "description": self.description,
            "envelope": self.envelope.to_dict(),
            "grid": self.grid,
            "segments": [dict(s) for s in self.segments],
            "edges": {str(k): v for k, v in self.edges.items()},
            "faces": [dict(f) for f in self.faces],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WallGraphDraft":
        return cls(
            name=data.get("name", "wallgraph"),
            description=data.get("description", ""),
            envelope=Band.from_dict(data["envelope"]),
            grid=float(data.get("grid", 3.3)),
            segments=[
                {
                    "x0": float(s["x0"]),
                    "y0": float(s["y0"]),
                    "x1": float(s["x1"]),
                    "y1": float(s["y1"]),
                }
                for s in data.get("segments", [])
            ],
            edges={int(k): str(v) for k, v in data.get("edges", {}).items()},
            faces=[dict(f) for f in data.get("faces", [])],
        )

    def validate(self) -> List[str]:
        """Draft consistency errors (empty = valid)."""
        errors: List[str] = []
        ex, ey = self.envelope.x1, self.envelope.y1
        for i, s in enumerate(self.segments):
            for k in ("x0", "y0", "x1", "y1"):
                if k not in s:
                    errors.append(f"segment:{i}:missing-{k}")
            if not (
                0 <= s.get("x0", 0) <= ex
                and 0 <= s.get("x1", 0) <= ex
                and 0 <= s.get("y0", 0) <= ey
                and 0 <= s.get("y1", 0) <= ey
            ):
                errors.append(f"segment:{i}:envelope-outer-region")
            if (
                abs(s.get("x0", 0) - s.get("x1", 0)) < 1e-9
                and abs(s.get("y0", 0) - s.get("y1", 0)) < 1e-9
            ):
                errors.append(f"segment:{i}:zero-length")
        for i, kind in self.edges.items():
            if kind not in EDGE_KINDS and i < len(self.segments):
                errors.append(f"edge:{i}:unknown-kind<{kind}>")
        for f in self.faces:
            if not f.get("key"):
                errors.append("face::missing-key")
            if (
                f.get("area_min") is not None
                and f.get("area_max") is not None
                and f["area_min"] > f["area_max"]
            ):
                errors.append(f"face:{f.get('key')}:band-inverted")
        return errors

    def noded_faces(self) -> List[Dict[str, Any]]:
        """Noding of the drawn segments → bounded faces + tag match.

        Each face dict: ``index`` (bounded-face id), ``area`` (m²),
        ``centroid``, ``verts`` (ccw point list), ``tag`` (the matched
        face designation or ``None``), ``matched`` (bool). Sub-slivers
        of the noder (area < EPS_AREA) are skipped — they are drafting
        artifacts, not rooms.
        """
        if not self.segments:
            return []
        seg = [((s["x0"], s["y0"]), (s["x1"], s["y1"])) for s in self.segments]
        sd = PlanarSubdivision.from_centerlines(seg)
        out: List[Dict[str, Any]] = []
        for fid in sd.bounded_faces():
            area = sd.face_area(fid)
            if area < EPS_AREA:
                continue
            verts = sd.face_vertices(fid)
            cx = sum(p[0] for p in verts) / len(verts)
            cy = sum(p[1] for p in verts) / len(verts)
            tag, matched = self._match_face(cx, cy)
            out.append(
                {
                    "index": fid,
                    "area": round(area, 3),
                    "centroid": [round(cx, 3), round(cy, 3)],
                    "verts": [[round(v[0], 3), round(v[1], 3)] for v in verts],
                    "key": (tag or {}).get("key"),
                    "label": (tag or {}).get("label", ""),
                    "items": (tag or {}).get("items", []),
                    "area_min": (tag or {}).get("area_min"),
                    "area_max": (tag or {}).get("area_max"),
                    "matched": matched,
                }
            )
        return out

    def _match_face(self, cx: float, cy: float) -> tuple[Optional[dict], bool]:
        best: Optional[dict] = None
        best_d = FACE_MATCH_TOL
        for f in self.faces:
            c = f.get("centroid", [0.0, 0.0])
            d = math.hypot(c[0] - cx, c[1] - cy)
            if d < best_d:
                best, best_d = f, d
        return best, best is not None


def node_faces(draft: WallGraphDraft) -> List[Dict[str, Any]]:
    """Free function form of ``noded_faces`` (endpoint helper)."""
    return draft.noded_faces()


def draft_preview_svg(draft: WallGraphDraft, faces: Optional[List[dict]] = None) -> str:
    """Wall-graph drawing as SVG: drawn strokes, face shading, edge tags."""
    if faces is None:
        faces = draft.noded_faces()
    bx, by = draft.envelope.x1, draft.envelope.y1
    width, pad = 1000.0, 24.0
    H = width * by / bx + 2 * pad
    s = (width - 2 * pad) / bx
    x0, y0 = draft.envelope.x0, draft.envelope.y0

    def sx(x):
        return pad + (x - x0) * s

    def sy(y):
        return H - pad - (y - y0) * s

    parts: List[str] = [f'<rect width="{width:.0f}" height="{H:.0f}" fill="#ffffff"/>']
    fills = ["#bcd7ee", "#cfe3d4", "#ead9c2", "#e7d5e4", "#d9d9e8", "#e8e2c8"]
    for i, f in enumerate(faces):
        poly = " ".join(f"{sx(v[0]):.1f},{sy(v[1]):.1f}" for v in f["verts"])
        fill = fills[i % len(fills)]
        tag = f.get("label") or ""
        parts.append(
            f'<polygon points="{poly}" fill="{fill}" fill-opacity="0.55" '
            f'stroke="none"/>'
        )
        cx = sum(v[0] for v in f["verts"]) / len(f["verts"])
        cy = sum(v[1] for v in f["verts"]) / len(f["verts"])
        placement = f"{tag} · {f['area']:.1f} m²" if tag else f"{f['area']:.1f} m²"
        parts.append(
            f'<text x="{sx(cx):.1f}" y="{sy(cy):.1f}" text-anchor="middle" '
            f'font-size="12" fill="#111827">{placement}</text>'
        )
    for i, seg in enumerate(draft.segments):
        kind = draft.edges.get(i, "wall")
        style = {
            "wall": 'stroke="#374151" stroke-width="2.5"',
            "open": 'stroke="#059669" stroke-width="2" stroke-dasharray="6 4"',
            "access": 'stroke="#f97316" stroke-width="2.5"',
            "facade": 'stroke="#9a3412" stroke-width="3"',
        }[kind]
        parts.append(
            f'<line x1="{sx(seg["x0"]):.1f}" y1="{sy(seg["y0"]):.1f}" '
            f'x2="{sx(seg["x1"]):.1f}" y2="{sy(seg["y1"]):.1f}" {style}/>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{H:.0f}">'
        + "".join(parts)
        + "</svg>"
    )


class WallGraphStore(TemplateStore):
    """Same JSON dir as zone-band drafts; wallgraph drafts gated by kind:—

    ``list()`` only names drafts whose JSON carries ``"kind": "wallgraph"``.
    """

    def save(self, name: str, draft: WallGraphDraft) -> None:  # type: ignore[override]
        self._path(name).write_text(
            json.dumps(draft.to_dict(), indent=2), encoding="utf-8"
        )

    def load_wallgraph(self, name: str) -> WallGraphDraft:
        d = json.loads(self._path(name).read_text(encoding="utf-8"))
        if d.get("kind") != "wallgraph":
            raise ValueError(f"{name} is not a wallgraph draft")
        return WallGraphDraft.from_dict(d)

    def list(self) -> List[str]:
        out: List[str] = []
        for name in super().list():
            try:
                self.load_wallgraph(name)
            except Exception:
                continue
            out.append(name)
        return out
