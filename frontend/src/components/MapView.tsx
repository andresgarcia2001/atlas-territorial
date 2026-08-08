import { useEffect, useMemo, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { fetchMapData } from "../api";
import { getIndicatorLabel } from "../indicatorCatalog";
import type { ColorMode, LayerSettings, MapData, MapFeature, ViewMode } from "../types";

type MapViewProps = LayerSettings & {
  onDataError?: (message: string | null) => void;
  year: number;
};

type StyleExpression = unknown[];

type LoadedMapData = {
  data: MapData;
  indicator: string;
  provinceKey: string;
  year: number;
};

const MIN_LATITUDE = -90;
const MAX_LATITUDE = 90;

const PROVINCE_COLORS = [
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

function getProvinceFilterKey(provinceIds: string[]) {
  return provinceIds.length === 0 ? "all" : provinceIds.join("|");
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
  const values = data.features
    .map((feature) => feature.properties.value)
    .filter((value): value is number => value !== null);

  if (values.length === 0) {
    return { min: 0, max: 1 };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);

  return {
    min,
    max: min === max ? min + 1 : max,
  };
}

function getProvinceColorExpression(data: MapData): StyleExpression {
  const expression: StyleExpression = ["match", ["get", "id"]];

  data.features.forEach((feature, index) => {
    expression.push(feature.properties.id, PROVINCE_COLORS[index % PROVINCE_COLORS.length]);
  });

  expression.push("#94a3b8");
  return expression;
}

function getColorExpression(
  data: MapData,
  colorMode: ColorMode,
  indicator: string,
  min: number,
  max: number,
): StyleExpression {
  if (colorMode === "province") {
    return getProvinceColorExpression(data);
  }

  if (indicator === "porcentaje_mujeres" || indicator === "porcentaje_varones") {
    return [
      "interpolate",
      ["linear"],
      ["coalesce", ["get", "value"], 50],
      48,
      "#38bdf8",
      50,
      "#e5e7eb",
      52,
      "#ef4444",
    ];
  }

  if (indicator === "porcentaje_otro_x") {
    return [
      "interpolate",
      ["linear"],
      ["coalesce", ["get", "value"], 0],
      0,
      "#e5e7eb",
      max,
      "#f59e0b",
    ];
  }

  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "value"], 0],
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
  return colorMode === "province" ? 0.58 : 0.5;
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

  map.setPaintProperty("territories-fill", "fill-color", getColorExpression(data, colorMode, indicator, min, max));
  map.setPaintProperty("territories-fill", "fill-opacity", getFillOpacity(colorMode));
  map.setPaintProperty(
    "territories-extrusion",
    "fill-extrusion-color",
    getColorExpression(data, colorMode, indicator, min, max),
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
      "fill-color": getColorExpression(data, colorMode, indicator, min, max) as never,
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
      "fill-extrusion-color": getColorExpression(data, colorMode, indicator, min, max) as never,
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
          Ano: ${feature.properties.year}
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

export function MapView({ colorMode, indicator, onDataError, provinceIds, viewMode, year }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedDataRef = useRef<LoadedMapData | null>(null);
  const latestLayerSettingsRef = useRef<LayerSettings>({ colorMode, indicator, provinceIds, viewMode });
  const lastFitKeyRef = useRef<string | null>(null);
  const provinceKey = useMemo(() => getProvinceFilterKey(provinceIds), [provinceIds]);

  latestLayerSettingsRef.current = { colorMode, indicator, provinceIds, viewMode };

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

    if (!map || !indicator) {
      return;
    }

    const mapInstance = map;
    let isCancelled = false;

    async function loadData() {
      try {
        const data = await fetchMapData(indicator, year, provinceIds);

        if (isCancelled) {
          return;
        }

        const applyData = () => {
          const shouldFitMap = lastFitKeyRef.current !== provinceKey;

          loadedDataRef.current = { data, indicator, provinceKey, year };
          renderTerritoryData(mapInstance, data, latestLayerSettingsRef.current, shouldFitMap);
          lastFitKeyRef.current = provinceKey;
          onDataError?.(null);
        };

        const safeApplyData = () => {
          if (!isCancelled) {
            applyData();
          }
        };

        if (mapInstance.loaded()) {
          safeApplyData();
        } else {
          mapInstance.once("load", safeApplyData);
        }
      } catch (caughtError) {
        if (!isCancelled) {
          onDataError?.(caughtError instanceof Error ? caughtError.message : "No se pudieron cargar los datos.");
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [indicator, onDataError, provinceIds, provinceKey, year]);

  useEffect(() => {
    const map = mapRef.current;
    const loadedData = loadedDataRef.current;

    if (
      !map ||
      !loadedData ||
      loadedData.indicator !== indicator ||
      loadedData.provinceKey !== provinceKey ||
      loadedData.year !== year
    ) {
      return;
    }

    renderTerritoryData(map, loadedData.data, { colorMode, indicator, provinceIds, viewMode }, false);
  }, [colorMode, indicator, provinceIds, provinceKey, viewMode, year]);

  return <main id="map" ref={containerRef} aria-label="Mapa de indicadores provinciales" />;
}
