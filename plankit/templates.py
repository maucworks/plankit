# This file was generated with the assistance of an AI coding tool.
"""plankit.templates — authoring model for typology templates (dev feature).

A *template draft* captures the composition grammar of one housing
typology as data: an envelope, a structural grid, typed zones
(``room``/``block``/``open``/``access``/``core``) with item patterns,
demarcation modes and access door-slot spacing. Drafts are authored in
the sketch canvas (served by ``plankit.api``) and persist as JSON;
they are checked-in data once proven against the PvE suite.

Demarcation modes:

- ``room`` — normal bounded room: wall ring, PvE edges drive doors.
- ``block`` — rigid demarcated box (bathroom, berging): slot band with
  narrow tolerance, one defined door side.
- ``open`` — functional strip *inside* another zone's footprint
  (bleeding kitchen): no internal wall materialised; area counts into
  the owning zone's item. Must be contained in ``sub_zone_of``.
- ``access`` — circulation system: width band + door-slot spacing
  (``priors["door_every"]`` in metres); ensemble-area accounting.
- ``core`` — fixed vertical/wet block (kern, lift, stair): placed at the
  anchor rule of the typology, no area freedom.

This module owns: the draft dataclasses (JSON round-trip), band
validation, PvE item coverage (fnmatch patterns), and a preview SVG so
the canvas and tests render identically to a human eye.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

#: Known zone modes.
ZONE_MODES = ("room", "block", "open", "access", "core")

#: Modes that may own ``open`` strips.
STRIP_OWNERS = ("room", "access")

#: Fill colours per mode (preview SVG).
_MODE_FILL = {
    "room": "#9fc6e8",
    "block": "#f6c8a0",
    "open": "#e8e2c8",
    "access": "#cfcfcf",
    "core": "#5f5f5f",
}


@dataclass
class Band:
    """Axis-aligned rectangle in metres: ``x0 <= x1``, ``y0 <= y1``."""

    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}

    @classmethod
    def from_dict(cls, data: dict) -> "Band":
        return cls(data["x0"], data["y0"], data["x1"], data["y1"])

    def contains(self, other: "Band", tol: float = 1e-6) -> bool:
        """True when *other* lies fully inside this band."""
        return (
            other.x0 >= self.x0 - tol
            and other.y0 >= self.y0 - tol
            and other.x1 <= self.x1 + tol
            and other.y1 <= self.y1 + tol
        )


@dataclass
class Zone:
    """One typed zone of a template draft.

    ``items`` are fnmatch patterns over PvE node keys (``slaap.*`` matches
    ``A1-slaap1``). ``sub_zone_of`` names the owning zone for ``open``
    strips. ``priors`` carry mode-specific numbers, e.g.
    ``{"door_every": 3.3}`` on ``access`` zones.
    """

    key: str
    mode: str
    band: Band
    items: List[str] = field(default_factory=list)
    label: str = ""
    sub_zone_of: Optional[str] = None
    priors: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "key": self.key,
            "mode": self.mode,
            "band": self.band.to_dict(),
            "items": list(self.items),
            "label": self.label,
            "sub_zone_of": self.sub_zone_of,
            "priors": dict(self.priors),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        return cls(
            key=data["key"],
            mode=data["mode"],
            band=Band.from_dict(data["band"]),
            items=list(data.get("items", [])),
            label=data.get("label", ""),
            sub_zone_of=data.get("sub_zone_of"),
            priors=dict(data.get("priors", {})),
        )


@dataclass
class TemplateDraft:
    """Draft of one typology template (canvas output, JSON on disk)."""

    name: str
    envelope: Band
    grid: float
    zones: List[Zone] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "name": self.name,
            "description": self.description,
            "envelope": self.envelope.to_dict(),
            "grid": self.grid,
            "zones": [z.to_dict() for z in self.zones],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateDraft":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            envelope=Band.from_dict(data["envelope"]),
            grid=float(data.get("grid", 3.3)),
            zones=[Zone.from_dict(z) for z in data.get("zones", [])],
        )

    @property
    def zone_by_key(self) -> dict:
        return {z.key: z for z in self.zones}

    def validate(self) -> List[str]:
        """Draft consistency errors (empty = valid)."""
        errors: List[str] = []
        seen = set()
        for z in self.zones:
            if z.mode not in ZONE_MODES:
                errors.append(f"zone:{z.key}:mode<{z.mode}>")
            if not (z.band.x0 < z.band.x1 and z.band.y0 < z.band.y1):
                errors.append(f"zone:{z.key}:band-inverted")
            if not (z.band.x0 >= 0 - 1e-6 and z.band.x1 <= self.envelope.x1 + 1e-6):
                errors.append(f"zone:{z.key}:band-outside-envelope-x")
            if not (z.band.y0 >= 0 - 1e-6 and z.band.y1 <= self.envelope.y1 + 1e-6):
                errors.append(f"zone:{z.key}:band-outside-envelope-y")
            if not z.key:
                errors.append("zone:<empty>:key-empty")
            if z.key in seen:
                errors.append(f"zone:{z.key}:key-duplicate")
            seen.add(z.key)
        for z in self.zones:
            if z.sub_zone_of is not None:
                parent = self.zone_by_key.get(z.sub_zone_of)
                if parent is None:
                    errors.append(f"zone:{z.key}:sub-zone-of-unknown<{z.sub_zone_of}>")
                elif z.mode != "open":
                    errors.append(f"zone:{z.key}:strip-owner-mode-not-open")
                elif parent.mode not in STRIP_OWNERS:
                    errors.append(f"zone:{z.sub_zone_of}:strip-owner-mode-not-enabling")
                elif not parent.band.contains(z.band):
                    errors.append(f"zone:{z.key}:strip-not-contained")
        return errors

    def coverage(self, program: Any) -> Tuple[List[str], List[str]]:
        """PvE items covered / uncovered by the draft's zone item patterns.

        ``program`` is a ``plankit.program.RoomProgram``; exterior nodes
        are not required to be covered. Matching is ``fnmatch`` against
        the node key, so ``slaap.*`` covers ``A1-slaap1``.
        """
        covered, uncovered = [], []
        for key, space in program.nodes.items():
            if getattr(space, "exterior", False):
                continue
            hit = False
            for z in self.zones:
                for pattern in z.items:
                    hit = pattern_matches(key, pattern)
                    if hit:
                        break
                if hit:
                    break
            (covered if hit else uncovered).append(key)
        return covered, uncovered

    def preview_svg(self, width: float = 1000.0) -> str:
        """Zoning diagram as SVG (the canvas's in-page preview)."""
        ex, ey = (
            self.envelope.x1 - self.envelope.x0,
            self.envelope.y1 - self.envelope.y0,
        )
        pad = 20.0
        H = width * ey / ex + 2 * pad
        s = (width - 2 * pad) / ex

        def sx(x):
            """Metres → SVG x."""
            return pad + (x - self.envelope.x0) * s

        def sy(y):
            """Metres → SVG y (y-axis flip for drawing space)."""
            return H - pad - (y - self.envelope.y0) * s

        parts: List[str] = [
            f'<rect width="{width:.0f}" height="{H:.0f}" fill="#ffffff"/>'
        ]
        for z in self.zones:
            b = z.band
            x, y = sx(b.x0), sy(b.y1)
            w, h = (b.x1 - b.x0) * s, (b.y1 - b.y0) * s
            fill = _MODE_FILL.get(z.mode, "#eee")
            if z.mode == "core":
                text = "#ffffff"
            else:
                text = "#111827"
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'fill="{fill}" fill-opacity="0.65" stroke="#4b5563" stroke-width="1"/>'
            )
            if z.label or z.key:
                suffix = f"\u00b7 {z.mode}" if z.mode != "room" else ""
                parts.append(
                    f'<text x="{x + w / 2:.1f}" y="{y + h / 2:.1f}" text-anchor="middle" '
                    f'font-size="{max(10, w * 0.06):.0f}" fill="{text}">'
                    f"{(z.label or z.key)} {suffix}</text>"
                )
            if z.mode == "access":
                every = float(z.priors.get("door_every", 0)) or 3.3
                pos = b.x0 + every / 2.0
                while pos <= b.x1 - every / 2.0 + 1e-6:
                    parts.append(
                        f'<rect x="{sx(pos) - 3:.1f}" y="{sy(b.y1) + h / 2 - 3:.1f}" '
                        f'width="6" height="6" fill="#f97316"/>'
                    )
                    pos += every
        poly = " ".join(
            f"{sx(px):.1f},{sy(py):.1f}"
            for px, py in (
                (self.envelope.x0, self.envelope.y0),
                (self.envelope.x1, self.envelope.y0),
                (self.envelope.x1, self.envelope.y1),
                (self.envelope.x0, self.envelope.y1),
            )
        )
        parts.append(
            f'<polygon points="{poly}" fill="none" stroke="#9a3412" stroke-width="3"/>'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{H:.0f}">'
            + "".join(parts)
            + "</svg>"
        )


def pattern_matches(key: str, pattern: str) -> bool:
    """fnmatch with suffix/stem variants for designer-style patterns.

    Direct: ``B*-woon`` matches by prefix. Suffix: ``slaap.*`` matches
    "A1-slaap1" (dropped dwelling prefix, trailing ``.*`` = stem).
    """
    if fnmatch.fnmatchcase(key, pattern):
        return True
    if fnmatch.fnmatchcase(key, "*" + pattern):
        return True
    if pattern.endswith(".*") and fnmatch.fnmatchcase(key, "*" + pattern[:-2] + "*"):
        return True
    return False


_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class TemplateStore:
    """JSON-file draft store (dev canvas). Directory from env override."""

    def __init__(self, directory: Optional[str] = None):
        base = directory or os.environ.get(
            "PLANKIT_TPL_DIR", str(Path(__file__).parent / "templates_drafts")
        )
        self.dir = Path(base)
        self.dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> List[str]:
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def _path(self, name: str) -> Path:
        if not _NAME_RE.match(name or ""):
            raise ValueError(f"invalid draft name {name!r}")
        return self.dir / (name + ".json")

    def save(self, name: str, draft: TemplateDraft) -> Path:
        self._path(name).write_text(
            json.dumps(draft.to_dict(), indent=2), encoding="utf-8"
        )
        return self._path(name)

    def load(self, name: str) -> TemplateDraft:
        return TemplateDraft.from_dict(
            json.loads(self._path(name).read_text(encoding="utf-8"))
        )

    def delete(self, name: str) -> bool:
        p = self._path(name)
        if p.exists():
            p.unlink()
            return True
        return False


def ascii_fold(name: str) -> str:
    """Canvas-side key normalisation (accents → ascii, spaces → -)."""
    folded = unicodedata.normalize("NFKD", name or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.strip().lower().replace(" ", "-")
    folded = re.sub(r"[^a-z0-9_-]", "-", folded)
    return re.sub(r"-+", "-", folded).strip("-") or "zone"
