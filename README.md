# Territorio Argentino

MVP local, no productivo, para explorar indicadores territoriales de Argentina sobre
geometrias PostGIS. El objetivo actual es validar la arquitectura para provincias,
municipios y radios censales antes de crecer en datos y funcionalidades.

Visor territorial local con PostgreSQL/PostGIS, FastAPI, React y MapLibre.

<img width="1621" height="1020" alt="imagen" src="https://github.com/user-attachments/assets/2a381131-4f20-4508-a8aa-85673ae5d6a6" />

## Servicios

- `db`: PostgreSQL con PostGIS.
- `backend`: API FastAPI que aplica migraciones Alembic y publica niveles
  territoriales, territorios, indicadores y GeoJSON para el mapa.
- `frontend`: visor React + MapLibre con modos 2D y 3D.
- `loader`: tarea manual para cargar GeoJSON territoriales en PostGIS.

## Arquitectura

```mermaid
flowchart LR
  frontend[frontend<br/>React + MapLibre] --> backend[backend<br/>FastAPI]
  backend -->|API + Alembic| db[(db<br/>PostgreSQL + PostGIS)]
  loader[loader<br/>load_territories.py] --> db
  data[(data<br/>GeoJSON territoriales)] -.-> loader
```

El modelo central es `territories`: una unidad territorial puede ser una provincia,
un municipio o un radio censal. Cada territorio guarda:

- `level_id`: `province`, `municipality` o `census_radius`.
- `source`: fuente de la geometria, por ejemplo `IGN`.
- `external_id`: codigo original del dataset fuente.
- `parent_id`: relacion jerarquica opcional con otro territorio.
- `metadata`: propiedades originales del GeoJSON.
- `geom`: geometria PostGIS.

## Configuracion local

El proyecto trae valores por defecto para desarrollo. Para personalizarlos:

```powershell
Copy-Item .env.example .env
```

Luego editar `.env` segun sea necesario. El archivo `.env` no se versiona.

Los ejemplos usan `docker compose`. Si tu instalacion expone el binario clasico,
reemplazarlo por `docker-compose`.

## Levantar el proyecto

```powershell
docker compose up -d --build
```

Al arrancar, el backend ejecuta las migraciones Alembic antes de iniciar la API.
Ese flujo es comodo para desarrollo local con una sola instancia. En un entorno con
mas de una replica del backend, conviene separar migraciones y arranque en un job o
step unico previo.

Abrir:

```text
http://localhost:5173
```

## Migraciones

El esquema de base se versiona con Alembic en `backend/alembic/versions`.

Ver revision aplicada:

```powershell
docker compose exec backend alembic -c alembic.ini current
```

Aplicar migraciones manualmente:

```powershell
docker compose exec backend alembic -c alembic.ini upgrade head
```

## Tests

Backend:

```powershell
python -m pip install -r backend/requirements-dev.txt
python -m pytest
```

El test de migraciones crea una base temporal y requiere una PostGIS accesible. Usa
por defecto `localhost:5432` con usuario y password `territorio`; se puede ajustar
con `TEST_POSTGRES_HOST`, `TEST_POSTGRES_PORT`, `TEST_POSTGRES_USER`,
`TEST_POSTGRES_PASSWORD` y `TEST_POSTGRES_ADMIN_DB`.

Frontend:

```powershell
cd frontend
npm run test:unit
```

## Cargar territorios

El loader principal es:

```text
scripts/load_territories.py
```

Ejecutar:

```powershell
docker compose --profile tools run --rm loader
```

Dataset incluido por defecto:

```text
data/poblacion_provincias_indec_2022.geojson
```

Variables principales:

- `PROVINCES_GEOJSON`: GeoJSON de provincias con indicadores censales.
- `IGN_MUNICIPALITIES_GEOJSON`: GeoJSON de municipios/localidades censales IGN.
- `CENSUS_RADII_GEOJSON`: GeoJSON de radios censales.
- `CENSUS_RADII_SOURCE`: etiqueta de fuente para radios censales.

Si un dataset opcional no esta configurado o no existe, el loader lo omite. Si se
configura explicitamente una ruta y el archivo no existe, el loader falla.

Cuando un GeoJSON use nombres de columnas distintos, configurar:

- `PROVINCE_ID_PROPERTY`, `PROVINCE_NAME_PROPERTY`
- `IGN_MUNICIPALITY_ID_PROPERTY`, `IGN_MUNICIPALITY_NAME_PROPERTY`,
  `IGN_MUNICIPALITY_PARENT_PROPERTY`
- `CENSUS_RADIUS_ID_PROPERTY`, `CENSUS_RADIUS_NAME_PROPERTY`,
  `CENSUS_RADIUS_PARENT_PROPERTY`

Las propiedades pueden ser simples, como `nombre`, o anidadas, como `provincia.id`.

El loader solo guarda `parent_id` si el territorio padre ya existe. Si el codigo de
provincia/municipio del dataset fuente no coincide con los IDs cargados, carga la
geometria y deja esa relacion pendiente.

## API territorial

Endpoints principales:

- `GET /territory-levels`
- `GET /territory-options?level=province`
- `GET /territories?level=municipality`
- `GET /indicators`
- `GET /map-data?level=census_radius&indicator=poblacion_total&year=2022`
- `GET /indicator-values?level=census_radius&indicator=poblacion_total&year=2022`

`/map-data` acepta `territory_ids` para filtrar territorios. `province_ids` queda
soportado como alias temporal de compatibilidad.

Para escalar a radios censales, la direccion recomendada es cachear geometria desde
`/territories` y refrescar valores desde `/indicator-values`. `/map-data` queda como
endpoint de conveniencia para el estado actual del frontend.

## Indicadores

El dataset provincial incluido carga indicadores crudos:

- `poblacion_total` desde `tpvpsc`
- `mujeres` desde `mftvp`
- `varones` desde `vmtvp`
- `otro_x` desde `oxtvp`

Y calcula indicadores derivados por nivel territorial:

- `porcentaje_mujeres`
- `porcentaje_varones`
- `porcentaje_otro_x`
- `densidad_poblacional`

El modo 3D no usa elevacion real del terreno: la altura representa el valor del
indicador seleccionado.

## Pasos rapidos para levantarlo

1. Abrir VS Code.
2. Abrir la carpeta `atlas-territorial`.
3. Abrir una terminal en la raiz del proyecto.
4. Ejecutar:

```powershell
docker compose up -d --build
```

5. Abrir en el navegador:

```text
http://localhost:5173
```

6. Cargar datos:

```powershell
docker compose --profile tools run --rm loader
```

Para apagarlo:

```powershell
docker compose down
```
