# This file was generated with the assistance of an AI coding tool.
"""Half-edge/DCEL (doubly-connected edge list) voor planaire subdivisies.

Het skelet van een plattegrond: faces zijn ruimten, half-edges zijn wand-
centerlines met een twin (de andere kant) en een next (de volgende edge langs
de face). De exterior face is de onbegrensde ruimte; grens-edges daarnaartoe
zijn facades.
"""

from __future__ import annotations

from dataclasses import dataclass

_EDGE_KINDS = ("wall", "door", "facade")


def _xy(p) -> tuple[float, float]:
    """Geef (x, y) terug voor een tupel of een object met ``.x``/``.y``."""
    if hasattr(p, "x"):
        return (p.x, p.y)
    return (p[0], p[1])


@dataclass
class Vertex:
    x: float
    y: float


@dataclass
class HalfEdge:
    origin: int  # vertex index
    twin: int  # half-edge index
    next: int  # half-edge index (CCW around face)
    face: int  # face index
    kind: str = "wall"  # "wall" | "door" | "facade"


@dataclass
class Face:
    half_edge: int  # one incident half-edge index
    exterior: bool = False
    label: str = ""  # ruimte-sleutel (PvE) of "" bij exterior/onbekend


class PlanarSubdivision:
    """Een planaire subdivisie als half-edge/DCEL.

    ``faces[0..n-1]`` zijn de begrensde faces (ruimten); de laatste face is de
    exterior (onbegrensde ruimte). Elke edge kent zijn twin (de andere kant) en
    zijn next (de volgende edge langs de face, CCW).
    """

    def __init__(self) -> None:
        self.vertices: list[Vertex] = []
        self.half_edges: list[HalfEdge] = []
        self.faces: list[Face] = []

    # ----- constructie -----

    @classmethod
    def from_faces(
        cls, polygons: list[list[tuple[float, float]]]
    ) -> "PlanarSubdivision":
        """Bouw een subdivisie uit begrensde faces (CCW-polygonen).

        De exterior face wordt automatisch toegevoegd; grens-edges (niet gedeeld
        door twee faces) krijgen ``kind="facade"``.
        """
        sd = cls()
        vertex_index: dict[tuple[float, float], int] = {}

        def vid(x: float, y: float) -> int:
            key = (round(x, 9), round(y, 9))
            if key not in vertex_index:
                vertex_index[key] = len(sd.vertices)
                sd.vertices.append(Vertex(x, y))
            return vertex_index[key]

        # Pass 1: begrensde faces — half-edges in CCW-cyclus.
        edge_map: dict[tuple[int, int], int] = {}
        for poly in polygons:
            n = len(poly)
            face_id = len(sd.faces)
            sd.faces.append(Face(half_edge=len(sd.half_edges)))
            he_ids: list[int] = []
            for i in range(n):
                u = vid(*_xy(poly[i]))
                v = vid(*_xy(poly[(i + 1) % n]))
                he_id = len(sd.half_edges)
                sd.half_edges.append(HalfEdge(origin=u, twin=-1, next=-1, face=face_id))
                edge_map[(u, v)] = he_id
                he_ids.append(he_id)
            for i in range(n):
                sd.half_edges[he_ids[i]].next = he_ids[(i + 1) % n]

        # Pass 2: twin-koppeling + exterior half-edges.
        exterior_id = len(sd.faces)
        sd.faces.append(Face(half_edge=-1, exterior=True))
        ext_by_origin: dict[int, int] = {}
        for he_id in list(range(len(sd.half_edges))):
            he = sd.half_edges[he_id]
            dest = sd.half_edges[he.next].origin
            rev = edge_map.get((dest, he.origin))
            if rev is not None:
                he.twin = rev
            else:
                ext = HalfEdge(
                    origin=dest, twin=he_id, next=-1, face=exterior_id, kind="facade"
                )
                ext_id = len(sd.half_edges)
                sd.half_edges.append(ext)
                he.twin = ext_id
                ext_by_origin[dest] = ext_id
                if sd.faces[exterior_id].half_edge == -1:
                    sd.faces[exterior_id].half_edge = ext_id

        # Pass 3: exterior next-cyclus (ext(v->u).next = ext met origin u).
        for he in sd.half_edges:
            if he.face == exterior_id:
                u = sd.half_edges[he.twin].origin
                he.next = ext_by_origin[u]

        # Pass 4: facade-markering op de begrensde twin van grens-edges.
        for he in sd.half_edges:
            if he.face == exterior_id:
                sd.half_edges[he.twin].kind = "facade"
        return sd

    @classmethod
    def from_centerlines(cls, segments) -> "PlanarSubdivision":
        """Bouw een subdivisie uit centerline-segmenten (vereist shapely).

        ``segments`` is een iterabele van ``(a, b)``, met ``a``/``b`` als
        ``(x, y)``-tupels of objecten met ``.x``/``.y``.
        """
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        lines = [LineString([_xy(a), _xy(b)]) for a, b in segments]
        noded = unary_union(lines)
        polys = list(polygonize(noded))
        rings = [list(p.exterior.coords)[:-1] for p in polys]
        return cls.from_faces(rings)

    # ----- queries -----

    def exterior_face(self) -> int:
        for i, f in enumerate(self.faces):
            if f.exterior:
                return i
        raise ValueError("geen exterior face")

    def bounded_faces(self) -> list[int]:
        return [i for i, f in enumerate(self.faces) if not f.exterior]

    def face_half_edges(self, face_id: int) -> list[int]:
        start = self.faces[face_id].half_edge
        out: list[int] = []
        he = start
        while True:
            out.append(he)
            he = self.half_edges[he].next
            if he == start:
                break
        return out

    def face_vertices(self, face_id: int) -> list[tuple[float, float]]:
        return [
            (
                self.vertices[self.half_edges[he].origin].x,
                self.vertices[self.half_edges[he].origin].y,
            )
            for he in self.face_half_edges(face_id)
        ]

    def face_area(self, face_id: int) -> float:
        pts = self.face_vertices(face_id)
        s = 0.0
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            s += x0 * y1 - x1 * y0
        return abs(s) / 2.0

    def perimeter_faces(self) -> set[int]:
        ext = self.exterior_face()
        out: set[int] = set()
        for he in self.half_edges:
            if he.face == ext:
                out.add(self.half_edges[he.twin].face)
        return out

    def shared_edge(self, face_a: int, face_b: int) -> int | None:
        for he in self.face_half_edges(face_a):
            twin = self.half_edges[he].twin
            if twin >= 0 and self.half_edges[twin].face == face_b:
                return he
        return None

    def adjacent_faces(self, face_id: int) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for he in self.face_half_edges(face_id):
            nbr = self.half_edges[self.half_edges[he].twin].face
            out.append((nbr, self.half_edges[he].kind))
        return out

    def mark_edge(self, face_a: int, face_b: int, kind: str) -> None:
        """Typeer de gedeelde edge tussen twee faces (beide twins)."""
        if kind not in _EDGE_KINDS:
            raise ValueError(f"onbekend edge-kind {kind!r}")
        he = self.shared_edge(face_a, face_b)
        if he is None:
            raise ValueError(f"geen gedeelde edge tussen face {face_a} en {face_b}")
        twin = self.half_edges[he].twin
        self.half_edges[he].kind = kind
        self.half_edges[twin].kind = kind

    # ----- serialisatie -----

    def to_dict(self) -> dict:
        """Return een JSON-serialiseerbare representatie (lossless round-trip)."""
        return {
            "vertices": [{"x": v.x, "y": v.y} for v in self.vertices],
            "faces": [
                {"half_edge": f.half_edge, "exterior": f.exterior, "label": f.label}
                for f in self.faces
            ],
            "half_edges": [
                {
                    "origin": he.origin,
                    "twin": he.twin,
                    "next": he.next,
                    "face": he.face,
                    "kind": he.kind,
                }
                for he in self.half_edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanarSubdivision":
        """Herbouw een subdivisie uit :meth:`to_dict`."""
        sd = cls()
        sd.vertices = [Vertex(v["x"], v["y"]) for v in data["vertices"]]
        sd.faces = [
            Face(
                half_edge=f["half_edge"],
                exterior=f["exterior"],
                label=f.get("label", ""),
            )
            for f in data["faces"]
        ]
        sd.half_edges = [
            HalfEdge(
                origin=he["origin"],
                twin=he["twin"],
                next=he["next"],
                face=he["face"],
                kind=he.get("kind", "wall"),
            )
            for he in data["half_edges"]
        ]
        return sd
