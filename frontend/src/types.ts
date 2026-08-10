export type IndicatorResponse = {
  indicators: string[];
};

export type TerritoryLevelId = "province" | "municipality" | "census_radius";

export type TerritoryLevel = {
  id: TerritoryLevelId;
  label: string;
  territory_count: number;
};

export type TerritoryLevelsResponse = {
  levels: TerritoryLevel[];
};

export type TerritoryOption = {
  id: string;
  name: string;
  level: TerritoryLevelId;
  parent_id: string | null;
};

export type TerritoryOptionsResponse = {
  territories: TerritoryOption[];
};

export type MultiPolygonGeometry = {
  type: "MultiPolygon";
  coordinates: number[][][][];
};

export type MultiLineStringGeometry = {
  type: "MultiLineString";
  coordinates: number[][][];
};

export type PointGeometry = {
  type: "Point";
  coordinates: [number, number];
};

export type TerritoryProperties = {
  id: string;
  name: string;
  level: TerritoryLevelId;
  source: string;
  external_id: string;
  parent_id: string | null;
  bar_center?: PointGeometry | null;
  bar_geometry?: MultiPolygonGeometry | null;
};

export type TerritoryFeature = {
  type: "Feature";
  properties: TerritoryProperties;
  geometry: MultiPolygonGeometry;
};

export type TerritoryData = {
  type: "FeatureCollection";
  features: TerritoryFeature[];
};

export type IndicatorValue = {
  territory_id: string;
  value: number | null;
};

export type IndicatorValuesResponse = {
  indicator: string;
  year: number;
  level: TerritoryLevelId;
  values: IndicatorValue[];
};

export type MapProperties = TerritoryProperties & {
  indicator: string;
  value: number | null;
  year: number;
  territory_color?: string;
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

export type TransportRouteProperties = {
  id: string;
  source: string;
  route_id: string;
  line: string | null;
  branch: string | null;
  direction: string | null;
  service_type: string | null;
  jurisdiction: string | null;
  from_name: string | null;
  to_name: string | null;
  route_color?: string;
};

export type TransportRouteFeature = {
  type: "Feature";
  properties: TransportRouteProperties;
  geometry: MultiLineStringGeometry;
};

export type TransportRouteData = {
  type: "FeatureCollection";
  features: TransportRouteFeature[];
};

export type ColorMode = "indicator" | "territory";

export type ViewMode = "flat" | "extruded";

export type GeometryMode = "surface" | "bars";

export type TransportOverlayMode = "none" | "ba_bus_routes";

export type LayerSettings = {
  indicator: string;
  colorMode: ColorMode;
  viewMode: ViewMode;
  geometryMode: GeometryMode;
  transportOverlay: TransportOverlayMode;
  territoryLevel: TerritoryLevelId;
  territoryIds: string[];
};
