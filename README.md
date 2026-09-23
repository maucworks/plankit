# plankit

Skelet-generatie voor plattegronden: van een programma van eisen (PvE) naar een
half-edge/DCEL-skelet. IFC-vrij.

Het plan, de milestones en de migratie-evaluatie staan in de meta-repo:
`plans/plankit/PLAN-plankit.md`.

## Indeling

- `plankit/` — de Python-**library** (core + store; `api.py` is het enige
  FastAPI-raakvlak, als optionele `[api]`-extra).
- `tests/` — library-tests; `examples/` — Python-voorbeelden.
- `frontend/` — **demo-only** inspectie-UI (vanilla TS + SCSS, eigen
  `package.json`/`tsconfig.json`; wordt niet als onderdeel van de library
  geshipt).

## Draaien (dev)

1. API: `pip install -e ".[api]" && PYTHONPATH=. python3 -m uvicorn plankit.api:app --port 8000`
2. Frontend: `cd frontend && npm install && npm run build && npm run serve`
3. Open http://localhost:3000 (praat met de API op :8000).
