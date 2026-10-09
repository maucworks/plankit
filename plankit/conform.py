# This file was generated with the assistance of an AI coding tool.
"""Conformance (laag 1): vergelijk een skelet met een PvE-graaf.

De tegenhanger van ``ifckit.spatial.conform``, maar IFC-vrij: de "gerealiseerde
graaf" is het skelet zelf. Ruimten worden op ``Face.label`` gekoppeld aan PvE-
sleutels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from plankit.derive import perimeter_spaces, space_adjacency
from plankit.graph import Graph
from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram

_TOL = 1e-6


@dataclass
class ConformanceReport:
    """Resultaat van :func:`conform`.

    Attributes:
        satisfied: Labels van voldane harde eisen.
        violated: Labels van geschonden harde eisen.
        missing: Labels van vereiste ruimten die ontbreken in het skelet.
        unconstrained: Labels die niet getoetst konden worden (zacht/onbekend).
        missing_adj: Per kamer-key de vereiste buren (`door` + vereiste
            `wall`) zonder gedeelde wand/deur (MFP-`!A`-lijst).
    """

    satisfied: list[str] = field(default_factory=list)
    violated: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unconstrained: list[str] = field(default_factory=list)
    missing_adj: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return whether no required constraint is violated or missing."""
        return not self.violated and not self.missing


def conform(sd: PlanarSubdivision, program: RoomProgram) -> ConformanceReport:
    """Vergelijk een skelet met een PvE-graaf.

    Koppelt programmaruimten aan faces op ``Face.label``, toetst oppervlakte-
    ranges en de getypeerde kanten (``door``/``forbidden``/``facade``/``wall``).
    Exterieure knopen zijn declaraties (``exterior=True``), geen te realiseren
    ruimten.
    """
    graph = space_adjacency(sd)
    perimeter = perimeter_spaces(sd)
    face_by_key = {f.label: i for i, f in enumerate(sd.faces) if not f.exterior and f.label}
    exterior_nodes = {key for key, space in program.nodes.items() if space.exterior}
    report = ConformanceReport()

    for key, space in program.nodes.items():
        if key in exterior_nodes:
            continue
        fid = face_by_key.get(key)
        if fid is None:
            (report.missing if space.required else report.unconstrained).append(f"space:{key}")
            continue
        area = sd.face_area(fid)
        if space.area_min is not None and area < space.area_min - _TOL:
            report.violated.append(f"space:{key}:area<{space.area_min}")
            continue
        if space.area_max is not None and area > space.area_max + _TOL:
            report.violated.append(f"space:{key}:area>{space.area_max}")
            continue
        report.satisfied.append(f"space:{key}")

    for edge in program.edges:
        label = f"edge:{edge.a}-{edge.b}:{edge.kind}"
        fa = face_by_key.get(edge.a)
        fb = face_by_key.get(edge.b)
        if edge.kind == "facade":
            if fa is None:
                report.unconstrained.append(label)
            elif str(fa) in perimeter:
                report.satisfied.append(label)
            else:
                report.violated.append(label)
            continue
        if edge.kind == "forbidden" and edge.b in exterior_nodes:
            if fa is None:
                report.unconstrained.append(label)
            elif str(fa) in perimeter:
                report.violated.append(label)
            else:
                report.satisfied.append(label)
            continue
        if fa is None or fb is None:
            report.unconstrained.append(label)
            continue
        if edge.kind == "forbidden":
            if graph.has_edge(str(fa), str(fb)):
                report.violated.append(label)
            else:
                report.satisfied.append(label)
        elif edge.kind == "door":
            attrs = graph.edge_attrs(str(fa), str(fb))
            if attrs is not None and attrs.get("kind") == "door":
                report.satisfied.append(label)
            else:
                report.violated.append(label)
                report.missing_adj.setdefault(edge.a, []).append(edge.b)
                report.missing_adj.setdefault(edge.b, []).append(edge.a)
        else:  # "wall", "visual" — zacht
            if graph.has_edge(str(fa), str(fb)):
                report.satisfied.append(label)
            elif edge.required:
                report.violated.append(label)
                report.missing_adj.setdefault(edge.a, []).append(edge.b)
                report.missing_adj.setdefault(edge.b, []).append(edge.a)
            else:
                report.unconstrained.append(label)
    for key in report.missing_adj:
        report.missing_adj[key] = sorted(set(report.missing_adj[key]))
    return report


def check_program(program: RoomProgram) -> list[str]:
    """Statische controles op een PvE-graaf: onbekende refs, geïsoleerde knopen
    en meerdere entrances per woninggroep (of per component zonder groep)."""
    issues: list[str] = []
    keys = set(program.nodes)
    for edge in program.edges:
        if edge.a not in keys:
            issues.append(f"kant verwijst naar onbekende knoop {edge.a!r}")
        if edge.b not in keys:
            issues.append(f"kant verwijst naar onbekende knoop {edge.b!r}")

    g = Graph()
    for key in keys:
        g.add_node(key)
    for edge in program.edges:
        if edge.kind != "forbidden" and edge.a in keys and edge.b in keys:
            g.add_edge(edge.a, edge.b)
    for key in keys:
        if g.degree(key) == 0:
            issues.append(f"geïsoleerde knoop {key!r}")
    for ci, comp in enumerate(g.connected_components()):
        buckets: dict[tuple[str, str], list[str]] = {}
        for key in comp:
            if not program.nodes[key].entrance:
                continue
            group = program.nodes[key].group
            bucket = ("woning", group) if group is not None else ("component", str(ci))
            buckets.setdefault(bucket, []).append(key)
        for (kind, name), entrances in buckets.items():
            if len(entrances) > 1:
                where = f"woning {name!r}" if kind == "woning" else "één component"
                issues.append(
                    f"meerdere entrances in {where}: {', '.join(sorted(entrances))}"
                )
    return issues


@dataclass
class CirculationReport:
    """Resultaat van :func:`validate_circulation` op de access-graaf."""

    root: str | None = None
    reachable: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    components: list[list[str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether every required space is reachable."""
        return not self.unreachable


def _default_root(program: RoomProgram) -> str | None:
    for key, space in program.nodes.items():
        if space.entrance:
            return key
    for key, space in program.nodes.items():
        if space.exterior:
            return key
    for key, space in program.nodes.items():
        if space.role == "verkeer":
            return key
    return next(iter(program.nodes), None)


def validate_circulation(program: RoomProgram, root: str | None = None) -> CirculationReport:
    """Toets de verkeersstructuur van een PvE op de access-graaf (``door``-kanten).

    Controleert dat elke vereiste, niet-exterieure ruimte bereikbaar is vanaf de
    wortel. Dit is de "gang verbindt alles"-toets.
    """
    from collections import deque

    access = program.access_graph()
    if root is None:
        root = _default_root(program)
    report = CirculationReport(root=root)
    for comp in access.connected_components():
        report.components.append(sorted(comp))

    if root is None or not access.has_node(root):
        report.unreachable = sorted(
            key for key, space in program.nodes.items() if space.required and not space.exterior
        )
        return report

    seen = {root}
    queue: deque[str] = deque([root])
    while queue:
        cur = queue.popleft()
        for nbr in access.neighbors(cur):
            if nbr not in seen:
                seen.add(nbr)
                queue.append(nbr)
    report.reachable = sorted(seen)
    report.unreachable = sorted(
        key
        for key, space in program.nodes.items()
        if space.required and not space.exterior and key not in seen
    )
    return report
