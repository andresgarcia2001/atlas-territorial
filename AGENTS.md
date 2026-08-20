# Agent Harness: Atlas Territorial

Lean operating notes for Codex and other agents in this repo.

## Project

Atlas Territorial is a local MVP for exploring Argentine territorial indicators
on PostGIS geometries.

- Backend: FastAPI, psycopg, Alembic, PostgreSQL/PostGIS in `backend/`.
- Frontend: React, TypeScript, Vite, MapLibre in `frontend/`.
- Data: Python preparers/loaders in `scripts/`; source and generated datasets in
  `data/`.
- Local services: `docker-compose.yml`.

Use `README.md` and `data/README.md` for detailed workflows and data provenance;
keep this file focused on agent behavior.

## Rules

- Check `git status --short` before editing and preserve unrelated user changes.
- Keep changes scoped to the request; avoid opportunistic refactors.
- Use structured parsers/APIs for GeoJSON, JSON, CSV, SQL, and TypeScript.
- Do not download datasets, refresh data, or rewrite bulky generated files unless
  the task explicitly asks for it.
- Keep raw logs and large data previews out of chat. Put bulky artifacts in
  `C:/Users/Administrator/Documents/Codex/contexto-codex` and report a summary.

## Data Boundaries

Treat these as source/audit artifacts:

- `data/README.md`
- `data/municipios_ign_validation_report.json`
- `data/municipality_in1_overrides.json`
- `data/municipality_feature_exclusions.json`
- `data/municipality_duplicate_resolutions.json`
- `data/local_government_municipality_unmatched.csv`

Treat these as generated or local-heavy unless the task says otherwise:

- `data/municipios_ign.geojson`
- `data/colectivos_recorridos.geojson`
- `data/circuitos_electorales_*.geojson`
- `data/circuitos_electorales_*_validation_report.json`
- `.tmp/`, `.pytest_tmp/`, `.pytest_cache_local/`, `frontend/dist/`

## Validation

Use the narrowest check that covers the change.

- Fast repo check: `powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1`
- Backend fast tests: `.\.venv\Scripts\python.exe -m pytest -m "not postgis"`
- Backend with PostGIS: `powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1 -BackendOnly -PostGIS`
- Frontend unit tests: `cd frontend; npm run test:unit`
- Frontend build: `cd frontend; npm run build`
- CI-like local check: `powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1 -PostGIS -BuildFrontend`

PostGIS checks require a reachable PostgreSQL/PostGIS database. Default local
credentials are in `README.md`. CI uses Python 3.12, Node 22, PostGIS 16-3.4,
backend pytest, and frontend unit tests.

For frontend map/UI changes, prefer a browser or screenshot check when feasible.

## Done

Before finishing, report:

- Files changed.
- Validation command run and pass/fail result.
- Commands skipped or unable to run, with the concrete reason.
- Remaining risk, especially around PostGIS behavior, data joins, map rendering,
  or generated data artifacts.
