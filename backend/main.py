import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from repositories import (
    DEFAULT_TERRITORY_LEVEL,
    fetch_indicator_names,
    fetch_indicator_values,
    fetch_map_data,
    fetch_territory_levels,
    fetch_territories_with_geometry,
    fetch_territory_options,
)

TerritoryLevelId = Literal["province", "municipality", "census_radius"]

app = FastAPI(title="Territorio Argentino API")


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
                },
                "geometry": geometry,
            }
            for territory_id, name, territory_level, source, external_id, parent_territory_id, geometry in rows
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

    if indicator not in available_indicators:
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
        "values": [
            {
                "territory_id": territory_id,
                "value": value,
            }
            for territory_id, value in rows
        ],
    }
