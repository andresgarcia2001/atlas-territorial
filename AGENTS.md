# Agent Harness: Atlas Territorial

This file is the project-level harness for Codex and other coding agents working
in this repository.

## Project Shape

Atlas Territorial is a local MVP for exploring Argentine territorial indicators
on PostGIS geometries.

- Backend: FastAPI, psycopg, Alembic, PostgreSQL/PostGIS.
- Frontend: React, TypeScript, Vite, MapLibre.
- Data pipeline: Python scripts in `scripts/`, source and generated datasets in
  `data/`.
- Local orchestration: `docker-compose.yml`.

## Working Rules

- Keep changes scoped to the user's request.
- Preserve existing uncommitted user changes. If a file already has unrelated
  edits, work around them or explain the conflict.
- Do not rewrite generated or bulky data files unless the task is explicitly
  about data preparation or loading.
- Do not download external datasets unless the user asked for a data refresh or
  the existing documented workflow requires it.
- Prefer structured parsing for GeoJSON, CSV, JSON, SQL, and TypeScript instead
  of ad hoc string edits.
- Keep raw logs, command dumps, and large data previews out of chat. Store bulky
  artifacts in `C:/Users/Administrator/Documents/Codex/contexto-codex` and
  report only a short summary plus the file path.

## Important Data Boundaries

Treat these files as source/audit artifacts:

- `data/README.md`
- `data/municipios_ign_validation_report.json`
- `data/municipality_in1_overrides.json`
- `data/municipality_feature_exclusions.json`
- `data/municipality_duplicate_resolutions.json`
- `data/local_government_municipality_unmatched.csv`

Treat these as generated/local-heavy outputs unless the task says otherwise:

- `data/municipios_ign.geojson`
- `data/colectivos_recorridos.geojson`
- `data/circuitos_electorales_*.geojson`
- `data/circuitos_electorales_*_validation_report.json`
- `.tmp/`, `.pytest_tmp/`, `.pytest_cache_local/`, `frontend/dist/`

## Validation Commands

Use the narrowest validation that covers the change.

- Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- Frontend unit tests:

```powershell
cd frontend
npm run test:unit
```

- Frontend build:

```powershell
cd frontend
npm run build
```

- Combined harness check:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1
```

By default, the combined check skips tests marked `postgis` so feedback stays
fast. Run the complete backend validation when a task touches migrations,
PostGIS behavior, repositories, or data loading:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1 -BackendOnly -PostGIS
```

PostGIS validation requires a reachable PostgreSQL/PostGIS instance. The default
local credentials are documented in `README.md`.

## Done Contract

Before finishing a coding task, report:

- What changed.
- Which validation command ran, with pass/fail status.
- Any command that could not run and the concrete reason.
- Any remaining risk, especially around PostGIS runtime behavior, data joins,
  map rendering, or generated data artifacts.

For frontend map/UI changes, prefer a browser or screenshot check when possible,
not only unit tests.
