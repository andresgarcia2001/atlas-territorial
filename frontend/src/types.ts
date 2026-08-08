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

export type MapProperties = {
  id: string;
  name: string;
  level: TerritoryLevelId;
  source: string;
  external_id: string;
  parent_id: string | null;
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

export type ColorMode = "indicator" | "territory";

export type ViewMode = "flat" | "extruded";

export type LayerSettings = {
  indicator: string;
  colorMode: ColorMode;
  viewMode: ViewMode;
  territoryLevel: TerritoryLevelId;
  territoryIds: string[];
};
