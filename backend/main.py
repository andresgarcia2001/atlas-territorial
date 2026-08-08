import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from repositories import (
    fetch_indicator_names,
    fetch_map_data,
    fetch_territories_with_geometry,
    fetch_territory_options,
)

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


@app.get("/territories")
def list_territories():
    rows = fetch_territories_with_geometry()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": territory_id,
                    "name": name,
                },
                "geometry": geometry,
            }
            for territory_id, name, geometry in rows
        ],
    }


@app.get("/territory-options")
def list_territory_options():
    rows = fetch_territory_options()

    return {
        "territories": [
            {
                "id": territory_id,
                "name": name,
            }
            for territory_id, name in rows
        ],
    }


@app.get("/indicators")
def list_indicators():
    rows = fetch_indicator_names()

    return {"indicators": [row[0] for row in rows]}


@app.get("/map-data")
def get_map_data(
    indicator: str = "poblacion_total",
    year: int = 2022,
    province_ids: list[str] | None = Query(default=None),
):
    rows = fetch_map_data(indicator, year, province_ids)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": territory_id,
                    "name": name,
                    "indicator": indicator,
                    "value": value,
                    "year": year,
                },
                "geometry": geometry,
            }
            for territory_id, name, geometry, value in rows
        ],
    }
