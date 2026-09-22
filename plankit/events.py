# This file was generated with the assistance of an AI coding tool.
"""Event-log (append-only JSONL) en evaluatie voor de generatie-loop.

Elke stap legt een :class:`Event` vast: de operatie, de skelet-toestand en een
rapport (conformance + kwaliteit). De log is replayable: de geschiedenis ís de
log, en de browser-scrub leest hem terug.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram


@dataclass
class Event:
    step: int
    op: str
    state: dict
    report: dict = field(default_factory=dict)


def append_event(log_path: str, event: Event) -> None:
    """Append één event als JSON-regel (append-only)."""
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(event), sort_keys=True) + "\n")


def read_events(log_path: str) -> list[Event]:
    """Lees een JSONL-log terug als lijst van events."""
    events: list[Event] = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(Event(**json.loads(line)))
    return events


def evaluate(sd: PlanarSubdivision, program: RoomProgram) -> dict:
    """Bereken laag 1 (conformance) + laag 2 (kwaliteit) als één rapport."""
    from plankit.conform import conform
    from plankit.quality import aspect_ratios, circulation_depth, facade_lengths, is_enfilade

    cr = conform(sd, program)
    return {
        "conformance": asdict(cr),
        "quality": {
            "aspect_ratio": aspect_ratios(sd),
            "facade_length": facade_lengths(sd),
            "circulation_depth": circulation_depth(sd),
            "enfilade": is_enfilade(sd),
        },
    }


def record(log_path: str, step: int, op: str, sd: PlanarSubdivision, program: RoomProgram) -> Event:
    """Evalueer het skelet en append het als event; return het event."""
    event = Event(step=step, op=op, state=sd.to_dict(), report=evaluate(sd, program))
    append_event(log_path, event)
    return event
