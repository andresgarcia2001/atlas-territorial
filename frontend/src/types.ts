export type IndicatorResponse = {
  indicators: string[];
};

export type MultiPolygonGeometry = {
  type: "MultiPolygon";
  coordinates: number[][][][];
};

export type MapProperties = {
  id: string;
  name: string;
  indicator: string;
  value: number | null;
  year: number;
};

export type MapFeature = {
  type: "Feature";
  properties: MapProperties;
  geometry: MultiPolygonGeometry;
};

export type MapData = {
  type: "FeatureCollection";
  features: MapFeature[];
};

export type ColorMode = "indicator" | "province";

export type ViewMode = "flat" | "extruded";

export type LayerSettings = {
  indicator: string;
  colorMode: ColorMode;
  viewMode: ViewMode;
};
