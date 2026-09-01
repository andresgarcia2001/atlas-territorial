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

La ruta interactiva preferida es el tile vectorial, porque limita el trabajo al
viewport y evita enviar el nivel completo al navegador:

- `/tiles/territories/4/4/6.pbf?level=province&indicator=poblacion_total&year=2022`
- `/tiles/territories/8/71/99.pbf?level=municipality&indicator=poblacion_total&year=2022`
- `/tiles/territories/12/1200/1800.pbf?level=census_radius&indicator=poblacion_total&year=2022`

Las tolerancias de simplificacion se aplican en metros sobre la geometria
transformada: zoom 0--5 `10000`, 6--8 `1000`, 9--11 `200`, 12--14 `50` y
15--22 `5`. La geometria canonica no se modifica.

Para una medicion reproducible, ejecutar contra un backend y una base cargada:

```powershell
python scripts/measure_map_performance.py --url "http://localhost:8000/tiles/territories/8/71/99.pbf?level=municipality&indicator=poblacion_total&year=2022" --requests 100 --concurrency 100
```

Guardar fuera del repositorio el JSON resultante y registrar fecha, volumen de
territorios/indicadores, estado de cache (frio o caliente), disponibilidad de
PostGIS, concurrencia, p50/p95/p99, conteo de estados HTTP, errores de transporte
y tamanos min/max/promedio. No guardar cuerpos de respuesta.

Los objetivos iniciales son p95 menor a 500 ms para tiles cacheables, p95 menor a
1 s sin cache y cero agotamientos del pool en 100 requests concurrentes.

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
