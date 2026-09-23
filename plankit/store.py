# This file was generated with the assistance of an AI coding tool.
"""Variant-store op SQLite: bewaar generatie-varianten met lineage.

Een :class:`Variant` is één generatiestap: het skelet (``state``), het PvE
(``program``), het rapport (conformance + kwaliteit) en de lineage
(``parent_id``). De store is de bron van waarheid voor de inspectie-loop; de
platte JSONL-event-log is hierin gevouwen.

De store is thread-safe: FastAPI draait sync-endpoints in een threadpool, dus
de verbinding gebruikt ``check_same_thread=False`` plus een lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from plankit.planar import PlanarSubdivision
from plankit.program import RoomProgram


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Variant:
    """Eén generatie-variant met lineage."""

    id: str
    parent_id: str | None = None
    step: int = 0
    label: str | None = None
    program: dict = field(default_factory=dict)
    proposal: dict | None = None
    state: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    llm: dict | None = None
    created_at: str = ""


def make_variant(
    sd: PlanarSubdivision,
    program: RoomProgram,
    *,
    step: int = 0,
    label: str | None = None,
    parent_id: str | None = None,
    proposal: dict | None = None,
    llm: dict | None = None,
) -> Variant:
    """Bouw een :class:`Variant` uit een skelet + PvE (rapport via ``evaluate``)."""
    from plankit.events import evaluate

    return Variant(
        id=uuid.uuid4().hex,
        parent_id=parent_id,
        step=step,
        label=label,
        program=program.to_dict(),
        proposal=proposal,
        state=sd.to_dict(),
        report=evaluate(sd, program),
        llm=llm,
        created_at=_now(),
    )


class VariantStore:
    """SQLite-gebaseerde opslag van varianten (thread-safe)."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS variants (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                step INTEGER NOT NULL,
                label TEXT,
                program TEXT NOT NULL,
                proposal TEXT,
                state TEXT NOT NULL,
                report TEXT NOT NULL,
                llm TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def add(self, v: Variant) -> Variant:
        with self._lock:
            self._conn.execute(
                "INSERT INTO variants VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    v.id,
                    v.parent_id,
                    v.step,
                    v.label,
                    json.dumps(v.program),
                    json.dumps(v.proposal) if v.proposal is not None else None,
                    json.dumps(v.state),
                    json.dumps(v.report),
                    json.dumps(v.llm) if v.llm is not None else None,
                    v.created_at,
                ),
            )
            self._conn.commit()
        return v

    def get(self, vid: str) -> Variant | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM variants WHERE id=?", (vid,)).fetchone()
        return self._from_row(row) if row else None

    def children(self, parent_id: str) -> list[Variant]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM variants WHERE parent_id=? ORDER BY step, id", (parent_id,)
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def roots(self) -> list[Variant]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM variants WHERE parent_id IS NULL ORDER BY step, id"
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def all(self) -> list[Variant]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM variants ORDER BY step, id").fetchall()
        return [self._from_row(r) for r in rows]

    def filter(self, predicate) -> list[Variant]:
        return [v for v in self.all() if predicate(v)]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Variant:
        return Variant(
            id=row["id"],
            parent_id=row["parent_id"],
            step=row["step"],
            label=row["label"],
            program=json.loads(row["program"]),
            proposal=json.loads(row["proposal"]) if row["proposal"] else None,
            state=json.loads(row["state"]),
            report=json.loads(row["report"]),
            llm=json.loads(row["llm"]) if row["llm"] else None,
            created_at=row["created_at"],
        )
