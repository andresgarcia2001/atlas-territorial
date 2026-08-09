import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { fetchIndicatorValues, fetchTerritories } from "../api";
import { getIndicatorLabel } from "../indicatorCatalog";
import type {
  ColorMode,
  IndicatorValue,
  LayerSettings,
  MapData,
  MapFeature,
  TerritoryData,
  ViewMode,
} from "../types";

type MapViewProps = LayerSettings & {
  onDataError?: (message: string | null) => void;
  year: number;
};

type StyleExpression = unknown[];

type LoadedTerritoryData = {
  data: TerritoryData;
  territoryKey: string;
  territoryLevel: string;
};

type LoadedIndicatorValues = {
  valueByTerritoryId: Map<string, number | null>;
  indicator: string;
  territoryKey: string;
  territoryLevel: string;
  year: number;
};

type LoadedMapData = LoadedIndicatorValues & {
  data: MapData;
};

type LegendState =
  | {
      colorMode: "indicator";
      label: string;
      minLabel: string;
      maxLabel: string;
    }
  | {
      colorMode: "territory";
      label: string;
    };

const MIN_LATITUDE = -90;
const MAX_LATITUDE = 90;

const TERRITORY_COLORS = [
  "#22c55e",
  "#f97316",
  "#3b82f6",
  "#eab308",
  "#ec4899",
  "#14b8a6",
  "#8b5cf6",
  "#ef4444",
  "#84cc16",
  "#06b6d4",
  "#f59e0b",
  "#a855f7",
  "#10b981",
  "#f43f5e",
  "#6366f1",
  "#65a30d",
  "#0ea5e9",
  "#d946ef",
  "#fb7185",
  "#2dd4bf",
  "#c084fc",
  "#facc15",
  "#38bdf8",
  "#fb923c",
];

function getTerritoryFilterKey(territoryIds: string[]) {
  return territoryIds.length === 0 ? "all" : territoryIds.join("|");
}

function formatIndicatorName(indicator: string) {
  return getIndicatorLabel(indicator);
}

function formatValue(value: number | null) {
  if (value === null) {
    return "sin dato";
  }

  return new Intl.NumberFormat("es-AR", {
    maximumFractionDigits: value >= 100 ? 0 : 2,
  }).format(value);
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };

    return entities[character];
  });
}

function getValueRange(data: MapData) {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let count = 0;

  for (const feature of data.features) {
    const value = feature.properties.value;

    if (value === null) {
      continue;
    }

    min = Math.min(min, value);
    max = Math.max(max, value);
    count += 1;
  }

  if (count === 0) {
    return { min: 0, max: 1 };
  }

  return {
    min,
    max: min === max ? min + 1 : max,
  };
}

function getTerritoryColor(territoryId: string) {
  let hash = 0;

  for (let index = 0; index < territoryId.length; index += 1) {
    hash = (hash * 31 + territoryId.charCodeAt(index)) >>> 0;
  }

  return TERRITORY_COLORS[hash % TERRITORY_COLORS.length];
}

function getValueByTerritoryId(values: IndicatorValue[]) {
  return new Map(values.map((indicatorValue) => [indicatorValue.territory_id, indicatorValue.value]));
}

function composeMapData(
  territoryData: TerritoryData,
  valueByTerritoryId: Map<string, number | null>,
  indicator: string,
  year: number,
): MapData {
  return {
    ...territoryData,
    features: territoryData.features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        indicator,
        value: valueByTerritoryId.get(feature.properties.id) ?? null,
        year,
        territory_color: getTerritoryColor(feature.properties.id),
      },
    })),
  };
}

function getTerritoryColorExpression(): StyleExpression {
  return ["coalesce", ["get", "territory_color"], "#94a3b8"];
}

function getColorExpression(colorMode: ColorMode, min: number, max: number): StyleExpression {
  if (colorMode === "territory") {
    return getTerritoryColorExpression();
  }

  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "value"], min],
    min,
    "#38bdf8",
    max,
    "#ef4444",
  ];
}

function getHeightExpression(indicator: string, min: number, max: number): StyleExpression {
  const maxHeight = indicator.startsWith("porcentaje_") ? 320 : 1400;

  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "value"], 0],
    min,
    20,
    max,
    maxHeight,
  ];
}

function getFillOpacity(colorMode: ColorMode) {
  return colorMode === "territory" ? 0.58 : 0.5;
}

function getLegend(data: MapData, layerSettings: LayerSettings): LegendState {
  if (layerSettings.colorMode === "territory") {
    return {
      colorMode: "territory",
      label: "Territorio",
    };
  }

  const { min, max } = getValueRange(data);

  return {
    colorMode: "indicator",
    label: formatIndicatorName(layerSettings.indicator),
    minLabel: formatValue(min),
    maxLabel: formatValue(max),
  };
}

function clampLatitude(latitude: number) {
  return Math.max(MIN_LATITUDE, Math.min(MAX_LATITUDE, latitude));
}

function fitMapToData(map: maplibregl.Map, data: MapData) {
  if (data.features.length === 0) {
    return;
  }

  const bounds = new maplibregl.LngLatBounds();

  for (const feature of data.features) {
    for (const polygon of feature.geometry.coordinates) {
      for (const ring of polygon) {
        for (const position of ring) {
          bounds.extend([position[0], clampLatitude(position[1])]);
        }
      }
    }
  }

  if (!bounds.isEmpty()) {
    map.fitBounds(bounds, { padding: 48, duration: 350 });
  }
}

function updateTerritoryPaint(
  map: maplibregl.Map,
  data: MapData,
  layerSettings: LayerSettings,
  min: number,
  max: number,
) {
  const { colorMode, indicator } = layerSettings;

  map.setPaintProperty("territories-fill", "fill-color", getColorExpression(colorMode, min, max));
  map.setPaintProperty("territories-fill", "fill-opacity", getFillOpacity(colorMode));
  map.setPaintProperty(
    "territories-extrusion",
    "fill-extrusion-color",
    getColorExpression(colorMode, min, max),
  );
  map.setPaintProperty("territories-extrusion", "fill-extrusion-height", getHeightExpression(indicator, min, max));
}

function applyViewMode(map: maplibregl.Map, viewMode: ViewMode) {
  if (!map.getLayer("territories-fill") || !map.getLayer("territories-extrusion")) {
    return;
  }

  map.setLayoutProperty("territories-fill", "visibility", viewMode === "flat" ? "visible" : "none");
  map.setLayoutProperty("territories-extrusion", "visibility", viewMode === "extruded" ? "visible" : "none");
  map.easeTo({
    pitch: viewMode === "extruded" ? 45 : 0,
    bearing: viewMode === "extruded" ? -18 : 0,
    duration: 350,
  });
}

function addTerritoryLayers(
  map: maplibregl.Map,
  data: MapData,
  colorMode: ColorMode,
  indicator: string,
) {
  const { min, max } = getValueRange(data);

  map.addSource("territories", {
    type: "geojson",
    data,
  });

  map.addLayer({
    id: "territories-fill",
    type: "fill",
    source: "territories",
    paint: {
      "fill-color": getColorExpression(colorMode, min, max) as never,
      "fill-opacity": getFillOpacity(colorMode),
    },
  });

  map.addLayer({
    id: "territories-extrusion",
    type: "fill-extrusion",
    source: "territories",
    layout: {
      visibility: "none",
    },
    paint: {
      "fill-extrusion-color": getColorExpression(colorMode, min, max) as never,
      "fill-extrusion-height": getHeightExpression(indicator, min, max) as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.58,
    },
  });

  map.addLayer({
    id: "territories-outline",
    type: "line",
    source: "territories",
    paint: {
      "line-color": "#f9fafb",
      "line-width": 1.2,
    },
  });

  for (const layerId of ["territories-fill", "territories-extrusion"]) {
    map.on("click", layerId, (event) => {
      const feature = event.features?.[0] as unknown as MapFeature | undefined;

      if (!feature || !event.lngLat) {
        return;
      }

      new maplibregl.Popup()
        .setLngLat(event.lngLat)
        .setHTML(`
          <strong>${escapeHtml(feature.properties.name)}</strong><br />
          ${escapeHtml(formatIndicatorName(feature.properties.indicator))}: ${formatValue(feature.properties.value)}<br />
          Año: ${feature.properties.year}
        `)
        .addTo(map);
    });

    map.on("mouseenter", layerId, () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", layerId, () => {
      map.getCanvas().style.cursor = "";
    });
  }
}

function renderTerritoryData(
  map: maplibregl.Map,
  loadedData: MapData,
  layerSettings: LayerSettings,
  shouldFitMap: boolean,
) {
  const source = map.getSource("territories") as maplibregl.GeoJSONSource | undefined;
  const { min, max } = getValueRange(loadedData);

  if (source) {
    source.setData(loadedData);
    updateTerritoryPaint(map, loadedData, layerSettings, min, max);
  } else {
    addTerritoryLayers(map, loadedData, layerSettings.colorMode, layerSettings.indicator);
  }

  if (shouldFitMap) {
    fitMapToData(map, loadedData);
  }

  applyViewMode(map, layerSettings.viewMode);
}

export function MapView({ colorMode, indicator, onDataError, territoryIds, territoryLevel, viewMode, year }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedTerritoryDataRef = useRef<LoadedTerritoryData | null>(null);
  const loadedIndicatorValuesRef = useRef<LoadedIndicatorValues | null>(null);
  const renderedDataRef = useRef<LoadedMapData | null>(null);
  const latestLayerSettingsRef = useRef<LayerSettings>({ colorMode, indicator, territoryIds, territoryLevel, viewMode });
  const lastFitKeyRef = useRef<string | null>(null);
  const [legend, setLegend] = useState<LegendState | null>(null);
  const territoryKey = useMemo(() => getTerritoryFilterKey(territoryIds), [territoryIds]);

  latestLayerSettingsRef.current = { colorMode, indicator, territoryIds, territoryLevel, viewMode };

  function renderCurrentData(map: maplibregl.Map, shouldFitMap: boolean) {
    const territoryData = loadedTerritoryDataRef.current;
    const indicatorValues = loadedIndicatorValuesRef.current;

    if (
      !territoryData ||
      !indicatorValues ||
      territoryData.territoryKey !== territoryKey ||
      territoryData.territoryLevel !== territoryLevel ||
      indicatorValues.indicator !== indicator ||
      indicatorValues.territoryKey !== territoryKey ||
      indicatorValues.territoryLevel !== territoryLevel ||
      indicatorValues.year !== year
    ) {
      return false;
    }

    const layerSettings = latestLayerSettingsRef.current;
    const data = composeMapData(territoryData.data, indicatorValues.valueByTerritoryId, indicator, year);

    renderedDataRef.current = {
      ...indicatorValues,
      data,
    };
    renderTerritoryData(map, data, layerSettings, shouldFitMap);
    setLegend(getLegend(data, layerSettings));
    onDataError?.(null);

    return true;
  }

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm",
          },
        ],
      },
      center: [-64, -40],
      zoom: 3.6,
      pitch: 0,
      bearing: 0,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    const mapInstance = map;
    let isCancelled = false;

    async function loadTerritoryGeometry() {
      try {
        const data = await fetchTerritories(territoryLevel, territoryIds);

        if (isCancelled) {
          return;
        }

        loadedTerritoryDataRef.current = { data, territoryKey, territoryLevel };

        const applyData = () => {
          const fitKey = `${territoryLevel}:${territoryKey}`;
          const didRender = renderCurrentData(mapInstance, lastFitKeyRef.current !== fitKey);

          if (didRender) {
            lastFitKeyRef.current = fitKey;
          }
        };

        if (mapInstance.loaded()) {
          applyData();
        } else {
          mapInstance.once("load", applyData);
        }
      } catch (caughtError) {
        if (!isCancelled) {
          setLegend(null);
          onDataError?.(
            caughtError instanceof Error ? caughtError.message : "No se pudieron cargar las geometrías territoriales.",
          );
        }
      }
    }

    loadTerritoryGeometry();

    return () => {
      isCancelled = true;
    };
  }, [onDataError, territoryIds, territoryKey, territoryLevel]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !indicator) {
      return;
    }

    const mapInstance = map;
    let isCancelled = false;

    async function loadIndicatorValues() {
      try {
        const data = await fetchIndicatorValues(indicator, year, territoryLevel, territoryIds);

        if (isCancelled) {
          return;
        }

        loadedIndicatorValuesRef.current = {
          valueByTerritoryId: getValueByTerritoryId(data.values),
          indicator,
          territoryKey,
          territoryLevel,
          year,
        };

        const applyData = () => {
          const fitKey = `${territoryLevel}:${territoryKey}`;
          const didRender = renderCurrentData(mapInstance, lastFitKeyRef.current !== fitKey);

          if (didRender) {
            lastFitKeyRef.current = fitKey;
          }
        };

        if (mapInstance.loaded()) {
          applyData();
        } else {
          mapInstance.once("load", applyData);
        }
      } catch (caughtError) {
        if (!isCancelled) {
          setLegend(null);
          onDataError?.(
            caughtError instanceof Error ? caughtError.message : "No se pudieron cargar los valores del indicador.",
          );
        }
      }
    }

    loadIndicatorValues();

    return () => {
      isCancelled = true;
    };
  }, [indicator, onDataError, territoryIds, territoryKey, territoryLevel, year]);

  useEffect(() => {
    const map = mapRef.current;
    const loadedData = renderedDataRef.current;

    if (
      !map ||
      !loadedData ||
      loadedData.indicator !== indicator ||
      loadedData.territoryKey !== territoryKey ||
      loadedData.territoryLevel !== territoryLevel ||
      loadedData.year !== year
    ) {
      return;
    }

    const layerSettings = { colorMode, indicator, territoryIds, territoryLevel, viewMode };
    renderTerritoryData(map, loadedData.data, layerSettings, false);
    setLegend(getLegend(loadedData.data, layerSettings));
  }, [colorMode, indicator, territoryIds, territoryKey, territoryLevel, viewMode, year]);

  return (
    <main className="map-shell" aria-label="Mapa de indicadores territoriales">
      <div id="map" ref={containerRef} />
      {legend && (
        <aside className="map-legend" aria-label="Leyenda del mapa">
          <span>{legend.label}</span>
          {legend.colorMode === "indicator" ? (
            <>
              <div className="legend-gradient" />
              <div className="legend-scale">
                <small>{legend.minLabel}</small>
                <small>{legend.maxLabel}</small>
              </div>
            </>
          ) : (
            <div className="legend-swatches">
              {TERRITORY_COLORS.slice(0, 8).map((territoryColor) => (
                <i key={territoryColor} style={{ backgroundColor: territoryColor }} />
              ))}
            </div>
          )}
        </aside>
      )}
    </main>
  );
}
