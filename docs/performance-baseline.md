# Performance baseline

Fecha de apertura: 2026-08-08

## Estado

No hay una medicion de `EXPLAIN ANALYZE` versionada todavia. Este cambio agrega
una Materialized View porque el patron de `/map-data` es estable y repetido, pero
no registra un baseline numerico inventado.

La primera medicion util deberia hacerse con la base mas grande disponible, idealmente
con municipios o radios censales reales cargados.

## Casos a medir

- `/map-data?level=province&indicator=poblacion_total&year=2022`
- `/map-data?level=municipality&indicator=poblacion_total&year=2022`
- `/map-data?level=census_radius&indicator=poblacion_total&year=2022`

Para cada caso registrar:

- Fecha.
- Volumen de datos: cantidad de territorios por nivel y cantidad de filas en
  `indicators`.
- Tiempo de ejecucion de `EXPLAIN ANALYZE`.
- Si el plan usa `Seq Scan` sobre tablas o vistas grandes.
- Tamano aproximado del payload GeoJSON devuelto por la API.

## Trigger para evaluar partitioning

No implementar partitioning hasta que haya evidencia medible. Reabrir la decision
si aparece al menos una de estas condiciones:

- `indicators` supera el orden de 100k a 500k filas.
- `EXPLAIN ANALYZE` sobre `territory_indicator_map_data_mv` muestra `Seq Scan`
  costosos filtrando por `year`, `level_id` o `indicator_name`.
- Se agregan radios censales y las consultas por indicador/anio degradan de forma
  medible.

## Plan minimo si se justifica

- Evaluar primero particionar `indicators`, no `territories`.
- Preferir `RANGE (year)` si el corte temporal domina las consultas.
- Evaluar una combinacion por `territory_level` y `year` solo si el plan real lo
  justifica.
- Evitar particionar `territories`: la jerarquia `parent_id` autoreferenciada agrega
  complejidad en claves e integridad para un beneficio incierto.
- Antes de migrar, probar upgrade/downgrade, inserts del loader, FKs y planes de
  consulta esperados.
