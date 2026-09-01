import os
from contextlib import asynccontextmanager
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from db import close_pool, initialize_pool
from errors import DatabaseUnavailableError

from repositories import (
    DEFAULT_TERRITORY_LEVEL,
    fetch_indicator_names,
    fetch_indicator_scale,
    fetch_indicator_values,
    fetch_territory_tile,
    fetch_map_data,
    fetch_transport_route_lines,
    fetch_transport_routes,
    fetch_territory_levels,
    fetch_territories_with_geometry,
    fetch_territory_options,
)

TerritoryLevelId = Literal["province", "municipality", "census_radius", "electoral_circuit"]

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_pool()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="Territorio Argentino API", lifespan=lifespan)


@app.exception_handler(DatabaseUnavailableError)
def handle_database_unavailable(_request: Request, caught_error: DatabaseUnavailableError):
    return JSONResponse(status_code=503, content={"detail": str(caught_error)})


@app.exception_handler(psycopg.Error)
def handle_database_error(_request: Request, _caught_error: psycopg.Error):
    return JSONResponse(status_code=503, content={"detail": "Database operation unavailable."})


def get_cors_origins():
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/territory-levels")
def list_territory_levels():
    rows = fetch_territory_levels()

    return {
        "levels": [
            {
                "id": level_id,
                "label": label,
                "territory_count": territory_count,
            }
            for level_id, label, territory_count in rows
        ],
    }


@app.get("/territories")
def list_territories(
    level: TerritoryLevelId = DEFAULT_TERRITORY_LEVEL,
    parent_id: str | None = None,
    territory_ids: list[str] | None = Query(default=None),
):
    rows = fetch_territories_with_geometry(level, parent_id, territory_ids)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": territory_id,
                    "name": name,
                    "level": territory_level,
                    "source": source,
                    "external_id": external_id,
                    "parent_id": parent_territory_id,
                    "bar_center": bar_center,
                    "bar_geometry": bar_geometry,
                },
                "geometry": geometry,
            }
            for (
                territory_id,
                name,
                territory_level,
                source,
                external_id,
                parent_territory_id,
                geometry,
                bar_center,
                bar_geometry,
            ) in rows
        ],
    }


@app.get("/territory-options")
def list_territory_options(level: TerritoryLevelId = DEFAULT_TERRITORY_LEVEL, parent_id: str | None = None):
    rows = fetch_territory_options(level, parent_id)

    return {
        "territories": [
            {
                "id": territory_id,
                "name": name,
                "level": territory_level,
                "parent_id": parent_territory_id,
            }
            for territory_id, name, territory_level, parent_territory_id in rows
        ],
    }


@app.get("/indicators")
def list_indicators(level: TerritoryLevelId | None = None, year: int | None = None):
    rows = fetch_indicator_names(level, year)

    return {"indicators": [row[0] for row in rows]}


def get_selected_territory_ids(territory_ids, province_ids):
    return territory_ids if territory_ids is not None else province_ids


def validate_indicator(indicator: str, level: TerritoryLevelId, year: int):
    available_indicators = {row[0] for row in fetch_indicator_names(level, year)}

    if indicator in available_indicators:
        return

    known_indicators = {row[0] for row in fetch_indicator_names(None, year)}

    if indicator in known_indicators:
        return

    raise HTTPException(
        status_code=422,
        detail=f"Indicador no disponible para level={level!r} y year={year}: {indicator!r}.",
    )


@app.get("/map-data")
def get_map_data(
    indicator: str = "poblacion_total",
    year: int = Query(default=2022, ge=1900),
    level: TerritoryLevelId = DEFAULT_TERRITORY_LEVEL,
    parent_id: str | None = None,
    territory_ids: list[str] | None = Query(default=None),
    province_ids: list[str] | None = Query(default=None),
):
    validate_indicator(indicator, level, year)
    selected_territory_ids = get_selected_territory_ids(territory_ids, province_ids)
    rows = fetch_map_data(indicator, year, level, selected_territory_ids, parent_id)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": territory_id,
                    "name": name,
                    "level": territory_level,
                    "source": source,
                    "external_id": external_id,
                    "parent_id": parent_territory_id,
                    "indicator": indicator,
                    "value": value,
                    "year": year,
                    "bar_center": bar_center,
                    "bar_geometry": bar_geometry,
                },
                "geometry": geometry,
            }
            for (
                territory_id,
                name,
                territory_level,
                source,
                external_id,
                parent_territory_id,
                geometry,
                bar_center,
                bar_geometry,
                value,
            ) in rows
        ],
    }


@app.get("/indicator-values")
def get_indicator_values(
    indicator: str = "poblacion_total",
    year: int = Query(default=2022, ge=1900),
    level: TerritoryLevelId = DEFAULT_TERRITORY_LEVEL,
    parent_id: str | None = None,
    territory_ids: list[str] | None = Query(default=None),
    province_ids: list[str] | None = Query(default=None),
):
    validate_indicator(indicator, level, year)
    selected_territory_ids = get_selected_territory_ids(territory_ids, province_ids)
    rows = fetch_indicator_values(indicator, year, level, selected_territory_ids, parent_id)

    return {
        "indicator": indicator,
        "year": year,
        "level": level,
        "scale": fetch_indicator_scale(indicator, year, level),
        "values": [
            {
                "territory_id": territory_id,
                "value": value,
            }
            for territory_id, value in rows
        ],
    }


@app.get("/indicator-scales")
def get_indicator_scale(
    indicator: str = "poblacion_total",
    year: int = Query(default=2022, ge=1900),
    level: TerritoryLevelId = DEFAULT_TERRITORY_LEVEL,
):
    validate_indicator(indicator, level, year)
    scale = fetch_indicator_scale(indicator, year, level)

    if scale is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay escala estadística para level={level!r}, year={year}, indicator={indicator!r}.",
        )

    return {"scale": scale}


@app.get("/tiles/territories/{z}/{x}/{y}.pbf")
def get_territory_tile(
    z: int,
    x: int,
    y: int,
    level: TerritoryLevelId = DEFAULT_TERRITORY_LEVEL,
    indicator: str | None = None,
    year: int | None = Query(default=None, ge=1900),
    parent_id: str | None = None,
    territory_ids: list[str] | None = Query(default=None),
):
    if z < 0 or z > 22 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
        raise HTTPException(status_code=422, detail="Invalid tile coordinates.")
    if indicator is not None and year is None:
        raise HTTPException(status_code=422, detail="year is required when indicator is provided.")
    if indicator is not None:
        validate_indicator(indicator, level, year)

    tile = fetch_territory_tile(
        z=z,
        x=x,
        y=y,
        level=level,
        indicator=indicator,
        year=year,
        parent_id=parent_id,
        territory_ids=territory_ids,
    )
    return Response(
        content=tile,
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": "public, max-age=60, stale-while-revalidate=300"},
    )


@app.get("/transport-routes")
def get_transport_routes(
    source: str | None = None,
    lines: list[str] | None = Query(default=None),
):
    rows = fetch_transport_routes(source, lines)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": route_id,
                    "source": source_name,
                    "route_id": external_route_id,
                    "line": line,
                    "branch": branch,
                    "direction": direction,
                    "service_type": service_type,
                    "jurisdiction": jurisdiction,
                    "from_name": from_name,
                    "to_name": to_name,
                },
                "geometry": geometry,
            }
            for (
                route_id,
                source_name,
                external_route_id,
                line,
                branch,
                direction,
                service_type,
                jurisdiction,
                from_name,
                to_name,
                geometry,
            ) in rows
        ],
    }


@app.get("/transport-route-lines")
def list_transport_route_lines(source: str | None = None):
    rows = fetch_transport_route_lines(source)

    return {
        "lines": [
            {
                "line": line,
                "route_count": route_count,
            }
            for line, route_count in rows
        ],
    }
