INSERT INTO territory_levels (id, label, display_order)
VALUES
  ('province', 'Provincias', 10),
  ('municipality', 'Municipios', 20),
  ('census_radius', 'Radios censales', 30)
ON CONFLICT (id) DO NOTHING;

INSERT INTO territories (id, name, level_id, source, external_id, metadata, geom)
VALUES
  (
    'zona_norte',
    'Zona Norte',
    'province',
    'demo',
    'zona_norte',
    '{}'::jsonb,
    ST_GeomFromText(
      'MULTIPOLYGON(((-58.50 -34.50, -58.42 -34.50, -58.42 -34.58, -58.50 -34.58, -58.50 -34.50)))',
      4326
    )
  ),
  (
    'zona_centro',
    'Zona Centro',
    'province',
    'demo',
    'zona_centro',
    '{}'::jsonb,
    ST_GeomFromText(
      'MULTIPOLYGON(((-58.42 -34.50, -58.34 -34.50, -58.34 -34.58, -58.42 -34.58, -58.42 -34.50)))',
      4326
    )
  ),
  (
    'zona_sur',
    'Zona Sur',
    'province',
    'demo',
    'zona_sur',
    '{}'::jsonb,
    ST_GeomFromText(
      'MULTIPOLYGON(((-58.50 -34.58, -58.34 -34.58, -58.34 -34.66, -58.50 -34.66, -58.50 -34.58)))',
      4326
    )
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
VALUES
  ('zona_norte', 'poblacion', 12000, 'demo', 2022),
  ('zona_centro', 'poblacion', 28000, 'demo', 2022),
  ('zona_sur', 'poblacion', 18000, 'demo', 2022),
  ('zona_norte', 'vulnerabilidad', 22.5, 'demo', 2022),
  ('zona_centro', 'vulnerabilidad', 41.8, 'demo', 2022),
  ('zona_sur', 'vulnerabilidad', 63.2, 'demo', 2022)
ON CONFLICT (territory_id, indicator_name, year) DO NOTHING;
