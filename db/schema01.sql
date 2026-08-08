CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS territories (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  geom GEOMETRY(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS territories_geom_idx
ON territories
USING GIST (geom);

-----

CREATE TABLE IF NOT EXISTS indicators (
  territory_id TEXT REFERENCES territories(id),
  indicator_name TEXT NOT NULL,
  indicator_value DOUBLE PRECISION NOT NULL,
  source TEXT,
  year INTEGER,
  PRIMARY KEY (territory_id, indicator_name, year)
);

CREATE INDEX IF NOT EXISTS indicators_name_year_idx
ON indicators (indicator_name, year);