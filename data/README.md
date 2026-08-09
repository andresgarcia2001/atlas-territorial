# Data sources and territorial identifiers

Last reviewed: 2026-08-08.

This project keeps source GeoJSON files under `data/`, but database identifiers
must be stable across source refreshes. Do not use source row order or `gid` as a
canonical territorial id when a national code is available.

## Files

### `poblacion_provincias_indec_2022.geojson`

- Level loaded as: `province`.
- Current inspected fields: `gid`, `fna`, `gna`, `nam`, `tpvpsc`, `mftvp`,
  `vmtvp`, `oxtvp`, `categoria`.
- Indicators loaded from this file:
  - `poblacion_total` from `tpvpsc`
  - `mujeres` from `mftvp`
  - `varones` from `vmtvp`
  - `otro_x` from `oxtvp`
- Important caveat: this file does not expose the two-digit province code in
  the inspected properties. The current `gid` values are source row ids and must
  not be used as canonical province ids for child datasets.
- Source/date provenance for the original download still needs to be recovered
  if it is not available in the project history.

## IGN municipality layer inspection

Inspected on 2026-08-08 from the official IGN WFS listed under Capas
vectoriales:

- WFS capabilities:
  `https://wms.ign.gob.ar/geoserver/ows?service=wfs&version=1.1.0&request=GetCapabilities`
- Candidate polygon layer:
  `ign:municipio`
- Comparison point layer:
  `ign:gobiernoslocales_2022`

The IGN Capas SIG page states that the downloadable vector layers use WGS 84 /
POSGAR 07, EPSG:4326.

### `ign:municipio`

Use this layer for municipality polygons.

- Geometry observed in GeoJSON sample: `MultiPolygon`.
- `totalFeatures` observed via WFS sample: `2114`.
- CRS observed in GeoJSON response: `EPSG:4326`.
- Fields from `DescribeFeatureType`:
  - `gid` (`int`, required)
  - `geom`
  - `fna`
  - `gna`
  - `nam`
  - `in1`
  - `fdc`
  - `sag`

Field meaning for this project:

- `nam`: display name.
- `fna`: full display name including type, when available.
- `gna`: government/local unit type label, e.g. `Municipio`, `Comuna`,
  `Junta`, `Comision`.
- `in1`: preferred source code for canonical municipality identity.
- `fdc`: source/capture organization metadata.
- `sag`: source agency metadata.
- `gid`: source row id only. Keep in `metadata`, but do not use as canonical id.

Attribute-only inspection results:

- Rows inspected: `2114`.
- Valid six-digit `in1` rows: `2106`.
- Rows with missing/invalid `in1`: `8`.
- Duplicate non-empty `in1` values observed:
  - `220476`: two rows named `Municipio Machagai`.
  - `822784`: rows named `Comuna El Rabon` and `Comuna Hardy`.
- Valid `in1` province prefixes observed:
  `02`, `06`, `10`, `14`, `18`, `22`, `26`, `30`, `34`, `38`, `42`, `46`,
  `50`, `54`, `58`, `62`, `66`, `70`, `74`, `78`, `82`, `90`, `94`.
- Expected province prefix not observed in valid `in1` values: `86`
  (`Santiago del Estero`).

Rows with missing `in1` must be quarantined or resolved manually before loading.
Duplicate `in1` values must be resolved before upsert. Do not fall back to
`gid`, because that would create unstable IDs across IGN refreshes.

### `ign:gobiernoslocales_2022`

Do not use this as the map polygon layer: the sampled geometry is `MultiPoint`.
It is useful as a cross-check because it exposes province fields missing from
`ign:municipio`.

- `totalFeatures` observed via WFS sample: `2313`.
- Fields from `DescribeFeatureType`:
  - `gid`
  - `objeto`
  - `geom`
  - `fna`
  - `gna`
  - `nam`
  - `in1`
  - `tgl`
  - `cod_tgl`
  - `nam_prov`
  - `cod_prov`
  - `fdc`
  - `sag`

## Canonical identifiers

### Province IDs

Canonical database id:

```text
provincia_<cod_prov>
```

Where `cod_prov` is the two-digit national province code. This code is also the
first two digits of valid IGN/Georef six-digit government-local/municipality
codes.

Current province loading must be adjusted before loading municipalities. The
included province GeoJSON lacks `cod_prov`, so province IDs should be built by
normalizing `nam`/`fna` and mapping the name to the table below.

| cod_prov | Canonical province name | Common source aliases |
| --- | --- | --- |
| `02` | Ciudad Autonoma de Buenos Aires | CABA, Ciudad Autonoma de Buenos Aires |
| `06` | Buenos Aires | Provincia de Buenos Aires |
| `10` | Catamarca | Provincia de Catamarca |
| `14` | Cordoba | Provincia de Cordoba |
| `18` | Corrientes | Provincia de Corrientes |
| `22` | Chaco | Provincia del Chaco |
| `26` | Chubut | Provincia del Chubut |
| `30` | Entre Rios | Provincia de Entre Rios |
| `34` | Formosa | Provincia de Formosa |
| `38` | Jujuy | Provincia de Jujuy |
| `42` | La Pampa | Provincia de La Pampa |
| `46` | La Rioja | Provincia de La Rioja |
| `50` | Mendoza | Provincia de Mendoza |
| `54` | Misiones | Provincia de Misiones |
| `58` | Neuquen | Provincia del Neuquen |
| `62` | Rio Negro | Provincia de Rio Negro |
| `66` | Salta | Provincia de Salta |
| `70` | San Juan | Provincia de San Juan |
| `74` | San Luis | Provincia de San Luis |
| `78` | Santa Cruz | Provincia de Santa Cruz |
| `82` | Santa Fe | Provincia de Santa Fe |
| `86` | Santiago del Estero | Provincia de Santiago del Estero |
| `90` | Tucuman | Provincia de Tucuman |
| `94` | Tierra del Fuego, Antartida e Islas del Atlantico Sur | Provincia de Tierra del Fuego, Antartida e Islas del Atlantico Sur |

Name matching must strip accents, fold case, collapse spaces, and remove common
prefixes such as `Provincia de`, `Provincia del`, and `Ciudad Autonoma de` only
through an explicit alias map.

### Municipality IDs

Canonical database id for valid IGN municipality polygons:

```text
municipio_<in1>
```

Parent id:

```text
provincia_<first_two_digits_of_in1>
```

Store:

- `level_id = 'municipality'`
- `source = 'IGN WFS ign:municipio'`
- `external_id = <in1>`
- `parent_id = provincia_<first_two_digits_of_in1>`
- original properties in `metadata`

The raw `ign:municipio` layer does not include `cod_prov`. The loader supports
deriving `parent_id` from `in1`, but a preprocessing step is still preferred
before loading the full source file because the current inspection found missing
and duplicate `in1` values.

1. A preprocessing step that adds `cod_prov = in1[0:2]` to every valid row and
   emits a validation report for missing/duplicate `in1` values.
2. Loader support for deriving `parent_id` from the first two digits of `in1`.

The first option is preferred because it leaves a normalized, inspectable
GeoJSON artifact in `data/` before database writes.

## Special cases and validation policy

- Buenos Aires partidos: load as `level_id = 'municipality'` for the current
  product view, with `gna`/`fna` preserved in `metadata`.
- CABA comunas: load as `level_id = 'municipality'` for the current product
  view unless a future UI explicitly separates `commune`.
- Other local government forms (`Comuna`, `Junta`, `Comision`, etc.): load as
  `level_id = 'municipality'` for map-level comparison, preserving the original
  `gna` value in `metadata`.
- Missing `in1`: validation failure.
- Duplicate `in1`: validation failure unless a documented exception decides to
  merge geometries or introduces a stable composite id.
- Missing parent province after deriving `cod_prov`: validation failure. Do not
  silently load child territories with `parent_id = NULL`.

## Loader status and next implementation steps

Implemented in `scripts/load_territories.py`:

- Province loading uses canonical `provincia_<cod_prov>` ids. For the included
  province GeoJSON, `cod_prov` is derived from the explicit name-code map above.
- IGN municipality loading uses `municipio_<in1>`.
- Municipality `parent_id` is derived from the first two digits of `in1`.
- Missing/invalid/duplicate municipality `in1` values are validation failures.
- Missing required municipality parent provinces are validation failures.

Implemented in `scripts/prepare_ign_municipalities.py`:

- Downloads or reads the `ign:municipio` GeoJSON.
- Adds `cod_prov = in1[0:2]` to valid rows.
- Writes `data/municipios_ign_validation_report.json`.
- Writes `data/municipios_ign.geojson` only when `has_blockers` is `false`.
- Treats missing/invalid/duplicate `in1` and unknown province codes as blocking
  issues.
- Reports missing expected province prefixes as warnings.

Remaining before loading the full IGN municipality polygons:

1. Resolve the inspected `ign:municipio` source issues: eight rows with missing
   `in1` and duplicate codes `220476` and `822784`.
2. Download or normalize the full `ign:municipio` GeoJSON into
   `data/municipios_ign_<YYYY-MM-DD>.geojson`.
3. When the report has no blockers, either keep the generated default
   `data/municipios_ign.geojson` for the loader or copy it to a dated filename
   and set `IGN_MUNICIPALITIES_GEOJSON`.
