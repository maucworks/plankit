# This file was generated with the assistance of an AI coding tool.
"""Demo: laat plankit end-to-end werken (PvE → skelet → rapport → SVG).

Draait twee voorbeelden en schrijft per voorbeeld een SVG-plattegrond, een
conformance/kwaliteit-rapport en een scrubpagina.

Gebruik:  PYTHONPATH=. python3 examples/demo.py [uitvoermap]
"""

from __future__ import annotations

import json
import sys

from plankit import (
    ProgramEdge,
    ProgramSpace,
    RoomProgram,
    evaluate,
    generate,
    scrub_page,
    to_svg,
)


def strip_demo() -> tuple[RoomProgram, str]:
    """Automatische strip-layout: drie ruimten op een rij, deuren aaneengesloten."""
    program = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", long_name="Keuken", area_min=8),
            "w": ProgramSpace(name="1.02", long_name="Woonkamer", area_min=20),
            "s": ProgramSpace(name="2.01", long_name="Slaapkamer", area_min=12),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[
            ProgramEdge("k", "w", kind="door"),
            ProgramEdge("w", "s", kind="door"),
            ProgramEdge("k", "buiten", kind="facade"),
            ProgramEdge("w", "buiten", kind="facade"),
            ProgramEdge("s", "buiten", kind="facade"),
        ],
    )
    sd = generate(program)
    return program, sd


def grid_demo() -> tuple[RoomProgram, str]:
    """Handmatig 2x2-voorstel: vier ruimten met deuren op de gedeelde wanden."""
    program = RoomProgram(
        nodes={
            "w": ProgramSpace(name="1.01", long_name="Woonkamer", area_min=20),
            "k": ProgramSpace(name="1.02", long_name="Keuken", area_min=8),
            "s": ProgramSpace(name="2.01", long_name="Slaapkamer", area_min=12),
            "b": ProgramSpace(name="2.02", long_name="Badkamer", area_min=5),
        },
        edges=[
            ProgramEdge("w", "k", kind="door"),
            ProgramEdge("w", "s", kind="door"),
            ProgramEdge("k", "b", kind="door"),
            ProgramEdge("s", "b", kind="door"),
        ],
    )
    proposal = {
        "w": [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)],
        "k": [(6.0, 0.0), (9.0, 0.0), (9.0, 4.0), (6.0, 4.0)],
        "s": [(0.0, 4.0), (6.0, 4.0), (6.0, 8.0), (0.0, 8.0)],
        "b": [(6.0, 4.0), (9.0, 4.0), (9.0, 8.0), (6.0, 8.0)],
    }
    sd = generate(program, proposal=proposal)
    return program, sd


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/plankit-demo"
    import os

    from plankit import VariantStore, make_variant

    os.makedirs(out_dir, exist_ok=True)
    store = VariantStore(os.path.join(out_dir, "variants.db"))

    for i, (name, (program, sd)) in enumerate(
        {"strip": strip_demo(), "grid": grid_demo()}.items()
    ):
        report = evaluate(sd, program)
        print(f"=== {name} ===")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        with open(os.path.join(out_dir, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(to_svg(sd))
        store.add(make_variant(sd, program, step=i, label=name))
        print(f"SVG -> {out_dir}/{name}.svg")
        print()

    variants = store.all()
    store.close()
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(scrub_page(variants))
    print(f"scrubpagina -> {out_dir}/index.html ({len(variants)} frames)")


if __name__ == "__main__":
    main()
