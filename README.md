# Territorio Argentino

Visor territorial local con PostgreSQL/PostGIS, FastAPI, React y MapLibre.

## Servicios

- `db`: PostgreSQL con PostGIS.
- `backend`: API FastAPI que publica territorios, indicadores y GeoJSON para el mapa.
- `frontend`: visor React + MapLibre con modos 2D y 3D.

## Levantar el proyecto

```powershell
docker compose up -d --build
```

Abrir:

```text
http://localhost:5173
```

## Cargar provincias reales

El archivo esperado es:

```text
data/poblacion_provincias_indec_2022.geojson
```

Ejecutar:

```powershell
docker run --rm `
  --network atlas-territorial_default `
  -v "${PWD}\scripts:/app" `
  -v "${PWD}\data:/data" `
  -w /app `
  -e POSTGRES_HOST=db `
  -e POSTGRES_DB=territorio_argentino `
  -e POSTGRES_USER=territorio `
  -e POSTGRES_PASSWORD=territorio `
  python:3.12-slim `
  sh -c "pip install --no-cache-dir psycopg[binary]==3.2.9 && python load_provinces.py"
```

## Indicadores

El script carga indicadores crudos:

- `poblacion_total`
- `mujeres`
- `varones`
- `otro_x`

Y calcula indicadores derivados:

- `porcentaje_mujeres`
- `porcentaje_varones`
- `porcentaje_otro_x`
- `densidad_poblacional`

## Pasos rápidos para levantarlo

1. Abrir VS Code.
2. Abrir la carpeta `atlas-territorial`.
3. Abrir una terminal en la raíz del proyecto.
4. Ejecutar:

```powershell
docker compose up -d --build
```

5. Abrir en el navegador:

```text
http://localhost:5173
```

Para apagarlo:

```powershell
docker compose down
```
