import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { fetchIndicatorValues, fetchTerritories, fetchTransportRoutes } from "../api";
import { getIndicatorLabel } from "../indicatorCatalog";
import {
  getCameraPreset,
  getLayerVisibility,
  getTransportCameraPreset,
  getTransportVisualMode,
  type TransportVisualMode,
} from "../mapModes";
import type {
  ColorMode,
  GeometryMode,
  IndicatorValue,
  LayerSettings,
  MapData,
  MapFeature,
  TerritoryData,
  TransportRouteGeometry,
  TransportRouteData,
  TransportRouteFeature,
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
const TERRITORY_SOURCE_ID = "territories";
const TERRITORY_BARS_SOURCE_ID = "territory-bars";
const TRANSPORT_NIGHT_MASK_SOURCE_ID = "transport-night-mask";
const TRANSPORT_NIGHT_MASK_LAYER_ID = "transport-night-mask";
const TRANSPORT_ROUTES_SOURCE_ID = "transport-routes";
const BA_BUS_ROUTES_SOURCE = "BA DATA colectivos recorridos";
const INTERACTIVE_TERRITORY_LAYER_IDS = [
  "territories-fill",
  "territories-extrusion",
  "territory-bars-fill",
  "territory-bars-extrusion",
];
const TRANSPORT_NEON_LAYER_IDS = ["transport-routes-neon-aura", "transport-routes-neon-glow"];
const TRANSPORT_ROUTE_LAYER_IDS = [
  ...TRANSPORT_NEON_LAYER_IDS,
  "transport-routes-casing",
  "transport-routes-line",
];

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

const TRANSPORT_ROUTE_COLORS = [
  "#00e5ff",
  "#ff2bd6",
  "#7cff00",
  "#ffb000",
  "#8b5cf6",
  "#00ffa3",
  "#ff3864",
  "#2d7dff",
  "#faff00",
  "#ff7a00",
  "#39ff14",
  "#ff4d6d",
];

const TRANSPORT_NIGHT_MASK_DATA = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-180, -85],
            [180, -85],
            [180, 85],
            [-180, 85],
            [-180, -85],
          ],
        ],
      },
    },
  ],
} satisfies GeoJSON.FeatureCollection<GeoJSON.Polygon>;

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

  if (min === max) {
    return {
      min: Math.min(0, min),
      max: Math.max(min, 1),
    };
  }

  return { min, max };
}

function getTerritoryColor(territoryId: string) {
  let hash = 0;

  for (let index = 0; index < territoryId.length; index += 1) {
    hash = (hash * 31 + territoryId.charCodeAt(index)) >>> 0;
  }

  return TERRITORY_COLORS[hash % TERRITORY_COLORS.length];
}

function getTransportRouteColor(line: string | null, routeId: string) {
  const routeKey = line ?? routeId;
  let hash = 0;

  for (let index = 0; index < routeKey.length; index += 1) {
    hash = (hash * 31 + routeKey.charCodeAt(index)) >>> 0;
  }

  return TRANSPORT_ROUTE_COLORS[hash % TRANSPORT_ROUTE_COLORS.length];
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

function composeTransportRouteData(data: TransportRouteData): TransportRouteData {
  return {
    ...data,
    features: data.features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        route_color: getTransportRouteColor(feature.properties.line, feature.properties.route_id),
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

function getSurfaceHeightExpression(indicator: string, min: number, max: number): StyleExpression {
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

function getBarHeightExpression(indicator: string, min: number, max: number): StyleExpression {
  const maxHeight = indicator.startsWith("porcentaje_") ? 70000 : 120000;

  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "value"], 0],
    min,
    8000,
    max,
    maxHeight,
  ];
}

function getFillOpacity(colorMode: ColorMode) {
  return colorMode === "territory" ? 0.58 : 0.5;
}

function getLegend(data: MapData, layerSettings: LayerSettings): LegendState | null {
  if (layerSettings.territoryLayerMode === "hidden") {
    return null;
  }

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

function hasBarGeometry(data: MapData) {
  return data.features.some((feature) => Boolean(feature.properties.bar_geometry));
}

function composeBarMapData(data: MapData): MapData {
  return {
    ...data,
    features: data.features.flatMap((feature) => {
      const barGeometry = feature.properties.bar_geometry;

      return barGeometry
        ? [
            {
              ...feature,
              geometry: barGeometry,
            },
          ]
        : [];
    }),
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

function forEachTransportRoutePosition(
  geometry: TransportRouteGeometry,
  callback: (position: [number, number]) => void,
) {
  const lines = geometry.type === "LineString" ? [geometry.coordinates] : geometry.coordinates;

  for (const line of lines) {
    for (const position of line) {
      callback([position[0], position[1]]);
    }
  }
}

function fitMapToTransportRoutes(
  map: maplibregl.Map,
  data: TransportRouteData,
  transportVisualMode: TransportVisualMode,
) {
  if (data.features.length === 0) {
    return;
  }

  const bounds = new maplibregl.LngLatBounds();

  for (const feature of data.features) {
    forEachTransportRoutePosition(feature.geometry, (position) => bounds.extend(position));
  }

  if (!bounds.isEmpty()) {
    const cameraPreset =
      transportVisualMode === "neon" ? getTransportCameraPreset("extruded") : getTransportCameraPreset("flat");

    map.fitBounds(bounds, {
      ...cameraPreset,
      linear: transportVisualMode === "neon",
      maxZoom: transportVisualMode === "neon" ? 12.2 : 13,
      padding: 72,
    });
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
  if (map.getLayer("territories-extrusion")) {
    map.setPaintProperty("territories-extrusion", "fill-extrusion-color", getColorExpression(colorMode, min, max));
    map.setPaintProperty(
      "territories-extrusion",
      "fill-extrusion-height",
      getSurfaceHeightExpression(indicator, min, max),
    );
  }

  if (map.getLayer("territory-bars-extrusion")) {
    map.setPaintProperty("territory-bars-extrusion", "fill-extrusion-color", getColorExpression(colorMode, min, max));
    map.setPaintProperty(
      "territory-bars-extrusion",
      "fill-extrusion-height",
      getBarHeightExpression(indicator, min, max),
    );
  }

  if (map.getLayer("territory-bars-fill")) {
    map.setPaintProperty("territory-bars-fill", "fill-color", getColorExpression(colorMode, min, max));
  }
}

function applyViewMode(
  map: maplibregl.Map,
  viewMode: ViewMode,
  geometryMode: GeometryMode,
  hasAvailableBarGeometry: boolean,
  isTerritoryLayerVisible: boolean,
) {
  if (
    !map.getLayer("territories-fill") ||
    !map.getLayer("territories-outline") ||
    !map.getLayer("territories-extrusion") ||
    !map.getLayer("territory-bars-fill") ||
    !map.getLayer("territory-bars-extrusion") ||
    !map.getLayer("territory-bars-outline")
  ) {
    return;
  }

  if (!isTerritoryLayerVisible) {
    for (const layerId of [
      "territories-fill",
      "territories-outline",
      "territories-extrusion",
      "territory-bars-fill",
      "territory-bars-extrusion",
      "territory-bars-outline",
    ]) {
      map.setLayoutProperty(layerId, "visibility", "none");
    }
    return;
  }

  const visibility = getLayerVisibility(viewMode, geometryMode, hasAvailableBarGeometry);

  map.setLayoutProperty("territories-fill", "visibility", visibility.fill);
  map.setLayoutProperty("territories-outline", "visibility", visibility.outline);
  map.setLayoutProperty("territories-extrusion", "visibility", visibility.surfaceExtrusion);
  map.setLayoutProperty("territory-bars-fill", "visibility", visibility.barFill);
  map.setLayoutProperty("territory-bars-extrusion", "visibility", visibility.barExtrusion);
  map.setLayoutProperty("territory-bars-outline", "visibility", visibility.barOutline);
  map.easeTo(getCameraPreset(viewMode));
}

function addTerritoryLayers(
  map: maplibregl.Map,
  data: MapData,
  colorMode: ColorMode,
  indicator: string,
) {
  const { min, max } = getValueRange(data);
  const barData = composeBarMapData(data);

  map.addSource(TERRITORY_SOURCE_ID, {
    type: "geojson",
    data,
  });

  map.addSource(TERRITORY_BARS_SOURCE_ID, {
    type: "geojson",
    data: barData,
  });

  map.addLayer({
    id: "territories-fill",
    type: "fill",
    source: TERRITORY_SOURCE_ID,
    paint: {
      "fill-color": getColorExpression(colorMode, min, max) as never,
      "fill-opacity": getFillOpacity(colorMode),
    },
  });

  map.addLayer({
    id: "territories-extrusion",
    type: "fill-extrusion",
    source: TERRITORY_SOURCE_ID,
    layout: {
      visibility: "none",
    },
    paint: {
      "fill-extrusion-color": getColorExpression(colorMode, min, max) as never,
      "fill-extrusion-height": getSurfaceHeightExpression(indicator, min, max) as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.58,
    },
  });

  map.addLayer({
    id: "territory-bars-fill",
    type: "fill",
    source: TERRITORY_BARS_SOURCE_ID,
    layout: {
      visibility: "none",
    },
    paint: {
      "fill-color": getColorExpression(colorMode, min, max) as never,
      "fill-opacity": 0.86,
    },
  });

  map.addLayer({
    id: "territory-bars-extrusion",
    type: "fill-extrusion",
    source: TERRITORY_BARS_SOURCE_ID,
    layout: {
      visibility: "none",
    },
    paint: {
      "fill-extrusion-color": getColorExpression(colorMode, min, max) as never,
      "fill-extrusion-height": getBarHeightExpression(indicator, min, max) as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.94,
    },
  });

  map.addLayer({
    id: "territory-bars-outline",
    type: "line",
    source: TERRITORY_BARS_SOURCE_ID,
    layout: {
      visibility: "none",
    },
    paint: {
      "line-color": "#111816",
      "line-opacity": 0.28,
      "line-width": 1,
    },
  });

  map.addLayer({
    id: "territories-outline",
    type: "line",
    source: TERRITORY_SOURCE_ID,
    paint: {
      "line-color": "#f9fafb",
      "line-width": 1.2,
    },
  });

  for (const layerId of INTERACTIVE_TERRITORY_LAYER_IDS) {
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

function getTransportRoutePopupHtml(feature: TransportRouteFeature) {
  const lineLabel = feature.properties.line ? `Línea ${feature.properties.line}` : "Recorrido";
  const branchLabel = feature.properties.branch ? ` - ${feature.properties.branch}` : "";
  const directionLabel = feature.properties.direction ? ` (${feature.properties.direction})` : "";
  const fromToLabel =
    feature.properties.from_name || feature.properties.to_name
      ? `<br />${escapeHtml(feature.properties.from_name ?? "Origen sin dato")} - ${escapeHtml(
          feature.properties.to_name ?? "Destino sin dato",
        )}`
      : "";

  return `
    <strong>${escapeHtml(lineLabel + branchLabel + directionLabel)}</strong>
    ${fromToLabel}<br />
    Fuente: ${escapeHtml(feature.properties.source)}
  `;
}

function ensureTransportNightMaskLayer(map: maplibregl.Map) {
  if (!map.getSource(TRANSPORT_NIGHT_MASK_SOURCE_ID)) {
    map.addSource(TRANSPORT_NIGHT_MASK_SOURCE_ID, {
      type: "geojson",
      data: TRANSPORT_NIGHT_MASK_DATA,
    });
  }

  if (map.getLayer(TRANSPORT_NIGHT_MASK_LAYER_ID)) {
    return;
  }

  map.addLayer({
    id: TRANSPORT_NIGHT_MASK_LAYER_ID,
    type: "fill",
    source: TRANSPORT_NIGHT_MASK_SOURCE_ID,
    layout: {
      visibility: "none",
    },
    paint: {
      "fill-color": "#06111e",
      "fill-opacity": 0.58,
    },
  });
}

function setTransportNightMaskVisibility(map: maplibregl.Map, isVisible: boolean) {
  if (map.getLayer(TRANSPORT_NIGHT_MASK_LAYER_ID)) {
    map.setLayoutProperty(TRANSPORT_NIGHT_MASK_LAYER_ID, "visibility", isVisible ? "visible" : "none");
  }
}

function updateTransportRoutePaint(map: maplibregl.Map, transportVisualMode: TransportVisualMode) {
  const isNeon = transportVisualMode === "neon";

  if (map.getLayer("transport-routes-neon-aura")) {
    map.setPaintProperty("transport-routes-neon-aura", "line-opacity", isNeon ? 0.2 : 0);
    map.setPaintProperty("transport-routes-neon-aura", "line-blur", isNeon ? 14 : 0);
    map.setPaintProperty(
      "transport-routes-neon-aura",
      "line-width",
      ["interpolate", ["linear"], ["zoom"], 5, isNeon ? 9 : 0, 10, isNeon ? 24 : 0, 14, isNeon ? 40 : 0] as never,
    );
  }

  if (map.getLayer("transport-routes-neon-glow")) {
    map.setPaintProperty("transport-routes-neon-glow", "line-opacity", isNeon ? 0.58 : 0);
    map.setPaintProperty("transport-routes-neon-glow", "line-blur", isNeon ? 5 : 0);
    map.setPaintProperty(
      "transport-routes-neon-glow",
      "line-width",
      ["interpolate", ["linear"], ["zoom"], 5, isNeon ? 4.5 : 0, 10, isNeon ? 12 : 0, 14, isNeon ? 22 : 0] as never,
    );
  }

  if (map.getLayer("transport-routes-casing")) {
    map.setPaintProperty("transport-routes-casing", "line-color", isNeon ? "#020817" : "#111816");
    map.setPaintProperty("transport-routes-casing", "line-opacity", isNeon ? 0.78 : 0.62);
    map.setPaintProperty(
      "transport-routes-casing",
      "line-width",
      ["interpolate", ["linear"], ["zoom"], 5, isNeon ? 2 : 1.5, 10, isNeon ? 5 : 4, 14, isNeon ? 10 : 9] as never,
    );
  }

  if (map.getLayer("transport-routes-line")) {
    map.setPaintProperty("transport-routes-line", "line-opacity", isNeon ? 0.98 : 0.92);
    map.setPaintProperty(
      "transport-routes-line",
      "line-width",
      ["interpolate", ["linear"], ["zoom"], 5, isNeon ? 1.8 : 1, 10, isNeon ? 4.2 : 2.5, 14, isNeon ? 8 : 6] as never,
    );
  }
}

function setTransportRouteVisibility(
  map: maplibregl.Map,
  isVisible: boolean,
  transportVisualMode: TransportVisualMode,
) {
  const isNeon = transportVisualMode === "neon";

  setTransportNightMaskVisibility(map, isVisible && isNeon);

  for (const layerId of TRANSPORT_ROUTE_LAYER_IDS) {
    if (map.getLayer(layerId)) {
      const shouldShowLayer = isVisible && (isNeon || !TRANSPORT_NEON_LAYER_IDS.includes(layerId));

      map.setLayoutProperty(layerId, "visibility", shouldShowLayer ? "visible" : "none");
    }
  }
}

function moveTransportVisualLayersToTop(map: maplibregl.Map) {
  if (map.getLayer(TRANSPORT_NIGHT_MASK_LAYER_ID)) {
    map.moveLayer(TRANSPORT_NIGHT_MASK_LAYER_ID);
  }

  for (const layerId of TRANSPORT_ROUTE_LAYER_IDS) {
    if (map.getLayer(layerId)) {
      map.moveLayer(layerId);
    }
  }
}

function addTransportRouteLayers(map: maplibregl.Map, data: TransportRouteData) {
  ensureTransportNightMaskLayer(map);

  map.addSource(TRANSPORT_ROUTES_SOURCE_ID, {
    type: "geojson",
    data,
  });

  map.addLayer({
    id: "transport-routes-neon-aura",
    type: "line",
    source: TRANSPORT_ROUTES_SOURCE_ID,
    layout: {
      "line-cap": "round",
      "line-join": "round",
      visibility: "none",
    },
    paint: {
      "line-blur": 14,
      "line-color": ["coalesce", ["get", "route_color"], "#00e5ff"] as never,
      "line-opacity": 0.2,
      "line-width": ["interpolate", ["linear"], ["zoom"], 5, 9, 10, 24, 14, 40] as never,
    },
  });

  map.addLayer({
    id: "transport-routes-neon-glow",
    type: "line",
    source: TRANSPORT_ROUTES_SOURCE_ID,
    layout: {
      "line-cap": "round",
      "line-join": "round",
      visibility: "none",
    },
    paint: {
      "line-blur": 5,
      "line-color": ["coalesce", ["get", "route_color"], "#00e5ff"] as never,
      "line-opacity": 0.58,
      "line-width": ["interpolate", ["linear"], ["zoom"], 5, 4.5, 10, 12, 14, 22] as never,
    },
  });

  map.addLayer({
    id: "transport-routes-casing",
    type: "line",
    source: TRANSPORT_ROUTES_SOURCE_ID,
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "line-color": "#111816",
      "line-opacity": 0.62,
      "line-width": ["interpolate", ["linear"], ["zoom"], 5, 1.5, 10, 4, 14, 9] as never,
    },
  });

  map.addLayer({
    id: "transport-routes-line",
    type: "line",
    source: TRANSPORT_ROUTES_SOURCE_ID,
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "line-color": ["coalesce", ["get", "route_color"], "#00e5ff"] as never,
      "line-opacity": 0.92,
      "line-width": ["interpolate", ["linear"], ["zoom"], 5, 1, 10, 2.5, 14, 6] as never,
    },
  });

  for (const layerId of TRANSPORT_ROUTE_LAYER_IDS) {
    map.on("click", layerId, (event) => {
      const feature = event.features?.[0] as unknown as TransportRouteFeature | undefined;

      if (!feature || !event.lngLat) {
        return;
      }

      new maplibregl.Popup().setLngLat(event.lngLat).setHTML(getTransportRoutePopupHtml(feature)).addTo(map);
    });

    map.on("mouseenter", layerId, () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", layerId, () => {
      map.getCanvas().style.cursor = "";
    });
  }
}

function renderTransportRouteData(
  map: maplibregl.Map,
  data: TransportRouteData,
  isVisible: boolean,
  shouldFitMap: boolean,
  transportVisualMode: TransportVisualMode,
) {
  const source = map.getSource(TRANSPORT_ROUTES_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;

  if (source) {
    source.setData(data);
  } else {
    addTransportRouteLayers(map, data);
  }

  updateTransportRoutePaint(map, transportVisualMode);
  setTransportRouteVisibility(map, isVisible, transportVisualMode);
  moveTransportVisualLayersToTop(map);

  if (isVisible && shouldFitMap) {
    fitMapToTransportRoutes(map, data, transportVisualMode);
  } else if (isVisible) {
    map.easeTo(getTransportCameraPreset(transportVisualMode === "neon" ? "extruded" : "flat"));
  }
}

function renderTerritoryData(
  map: maplibregl.Map,
  loadedData: MapData,
  layerSettings: LayerSettings,
  shouldFitMap: boolean,
) {
  const source = map.getSource(TERRITORY_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  const barSource = map.getSource(TERRITORY_BARS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  const { min, max } = getValueRange(loadedData);
  const barData = composeBarMapData(loadedData);

  if (source) {
    source.setData(loadedData);
    barSource?.setData(barData);
    updateTerritoryPaint(map, loadedData, layerSettings, min, max);
  } else {
    addTerritoryLayers(map, loadedData, layerSettings.colorMode, layerSettings.indicator);
  }

  if (shouldFitMap) {
    fitMapToData(map, loadedData);
  }

  applyViewMode(
    map,
    layerSettings.viewMode,
    layerSettings.geometryMode,
    hasBarGeometry(loadedData),
    layerSettings.territoryLayerMode === "visible",
  );
  moveTransportVisualLayersToTop(map);
}

export function MapView({
  colorMode,
  geometryMode,
  indicator,
  onDataError,
  territoryLayerMode,
  transportOverlay,
  territoryIds,
  territoryLevel,
  viewMode,
  year,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedTerritoryDataRef = useRef<LoadedTerritoryData | null>(null);
  const loadedIndicatorValuesRef = useRef<LoadedIndicatorValues | null>(null);
  const loadedTransportRouteDataRef = useRef<TransportRouteData | null>(null);
  const renderedDataRef = useRef<LoadedMapData | null>(null);
  const latestLayerSettingsRef = useRef<LayerSettings>({
    colorMode,
    geometryMode,
    indicator,
    territoryLayerMode,
    transportOverlay,
    territoryIds,
    territoryLevel,
    viewMode,
  });
  const lastFitKeyRef = useRef<string | null>(null);
  const [legend, setLegend] = useState<LegendState | null>(null);
  const territoryKey = useMemo(() => getTerritoryFilterKey(territoryIds), [territoryIds]);
  const transportVisualMode = useMemo(() => getTransportVisualMode(viewMode), [viewMode]);

  latestLayerSettingsRef.current = {
    colorMode,
    geometryMode,
    indicator,
    territoryLayerMode,
    transportOverlay,
    territoryIds,
    territoryLevel,
    viewMode,
  };

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

    if (!map) {
      return;
    }

    const mapInstance = map;
    let isCancelled = false;

    if (transportOverlay !== "ba_bus_routes") {
      setTransportRouteVisibility(mapInstance, false, transportVisualMode);
      return () => {
        isCancelled = true;
      };
    }

    function applyTransportData(data: TransportRouteData, shouldFitMap: boolean) {
      const applyData = () => {
        if (!isCancelled) {
          renderTransportRouteData(mapInstance, data, true, shouldFitMap, transportVisualMode);
        }
      };

      if (mapInstance.loaded()) {
        applyData();
      } else {
        mapInstance.once("load", applyData);
      }
    }

    if (loadedTransportRouteDataRef.current) {
      applyTransportData(loadedTransportRouteDataRef.current, false);
      return () => {
        isCancelled = true;
      };
    }

    async function loadTransportRoutes() {
      try {
        const data = composeTransportRouteData(await fetchTransportRoutes(BA_BUS_ROUTES_SOURCE));

        if (isCancelled) {
          return;
        }

        loadedTransportRouteDataRef.current = data;
        applyTransportData(data, true);
      } catch (caughtError) {
        if (!isCancelled) {
          onDataError?.(
            caughtError instanceof Error ? caughtError.message : "No se pudieron cargar los recorridos de transporte.",
          );
        }
      }
    }

    loadTransportRoutes();

    return () => {
      isCancelled = true;
    };
  }, [onDataError, transportOverlay, transportVisualMode]);

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

    const layerSettings = {
      colorMode,
      geometryMode,
      indicator,
      territoryLayerMode,
      transportOverlay,
      territoryIds,
      territoryLevel,
      viewMode,
    };
    renderTerritoryData(map, loadedData.data, layerSettings, false);
    setLegend(getLegend(loadedData.data, layerSettings));
  }, [
    colorMode,
    geometryMode,
    indicator,
    territoryIds,
    territoryKey,
    territoryLayerMode,
    territoryLevel,
    transportOverlay,
    viewMode,
    year,
  ]);

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
