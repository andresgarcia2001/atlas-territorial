import { DEFAULT_INDICATOR, getAvailableIndicatorGroups } from "./indicatorCatalog";
import type { LayerSettings, TerritoryLevel, TerritoryLevelId, TerritoryOption } from "./types";

export const DEFAULT_TERRITORY_LEVEL: TerritoryLevelId = "province";

export const FALLBACK_TERRITORY_LEVELS: TerritoryLevel[] = [
  { id: "province", label: "Provincias", territory_count: 1 },
  { id: "municipality", label: "Municipios", territory_count: 0 },
  { id: "census_radius", label: "Radios censales", territory_count: 0 },
  { id: "electoral_circuit", label: "Circuitos electorales", territory_count: 0 },
];

export const DEFAULT_LAYER_SETTINGS: LayerSettings = {
  indicator: DEFAULT_INDICATOR,
  colorMode: "indicator",
  viewMode: "flat",
  geometryMode: "surface",
  territoryLayerMode: "hidden",
  transportOverlay: "none",
  transportRouteLines: [],
  territoryLevel: DEFAULT_TERRITORY_LEVEL,
  territoryParentId: null,
  territoryIds: [],
};

export function areArraysEqual(first: string[], second: string[]) {
  return first.length === second.length && first.every((value, index) => value === second[index]);
}

export function areLayerSettingsEqual(first: LayerSettings, second: LayerSettings) {
  return (
    first.indicator === second.indicator &&
    first.colorMode === second.colorMode &&
    first.viewMode === second.viewMode &&
    first.geometryMode === second.geometryMode &&
    first.territoryLayerMode === second.territoryLayerMode &&
    first.transportOverlay === second.transportOverlay &&
    areArraysEqual(first.transportRouteLines, second.transportRouteLines) &&
    first.territoryLevel === second.territoryLevel &&
    first.territoryParentId === second.territoryParentId &&
    areArraysEqual(first.territoryIds, second.territoryIds)
  );
}

export function getDefaultIndicator(loadedIndicators: string[]) {
  const loadedGroups = getAvailableIndicatorGroups(loadedIndicators);
  const firstIndicator = loadedGroups[0]?.indicators[0];

  return loadedIndicators.includes(DEFAULT_INDICATOR) ? DEFAULT_INDICATOR : firstIndicator?.id ?? DEFAULT_INDICATOR;
}

export function getDefaultColorMode(loadedIndicators: string[]) {
  return loadedIndicators.length === 0 ? "territory" : DEFAULT_LAYER_SETTINGS.colorMode;
}

export function getInitialLayerSettings(loadedIndicators: string[], territoryLevel: TerritoryLevelId): LayerSettings {
  return {
    ...DEFAULT_LAYER_SETTINGS,
    territoryLevel,
    indicator: getDefaultIndicator(loadedIndicators),
    colorMode: getDefaultColorMode(loadedIndicators),
  };
}

export function shouldUseParentTerritoryFilter(territoryLevel: TerritoryLevelId) {
  return territoryLevel === "electoral_circuit";
}

export function getTerritoryOptionsKey(territoryLevel: TerritoryLevelId, parentId: string | null = null) {
  return `${territoryLevel}:${parentId ?? "all"}`;
}

export function getDefaultTerritoryParentId(territoryLevel: TerritoryLevelId, parentOptions: TerritoryOption[]) {
  return shouldUseParentTerritoryFilter(territoryLevel) ? parentOptions[0]?.id ?? null : null;
}

export function getInitialTerritoryLevel(levels: TerritoryLevel[]) {
  const defaultLevel = levels.find((level) => level.id === DEFAULT_TERRITORY_LEVEL && level.territory_count > 0);
  const firstLoadedLevel = levels.find((level) => level.territory_count > 0);

  return defaultLevel?.id ?? firstLoadedLevel?.id ?? DEFAULT_TERRITORY_LEVEL;
}

export function getTerritorySelectionLabel(territoryIds: string[], territoryOptions: TerritoryOption[]) {
  if (territoryIds.length === 0) {
    return "Todos";
  }

  if (territoryIds.length === 1) {
    return territoryOptions.find((territory) => territory.id === territoryIds[0])?.name ?? "1 territorio";
  }

  return `${territoryIds.length} territorios`;
}

export function getTransportRouteLineSelectionLabel(transportRouteLines: string[]) {
  if (transportRouteLines.length === 0) {
    return "Todas";
  }

  if (transportRouteLines.length === 1) {
    return `Línea ${transportRouteLines[0]}`;
  }

  return `${transportRouteLines.length} líneas`;
}

export async function getTerritoryLevelsOrFallback(loadTerritoryLevels: () => Promise<TerritoryLevel[]>) {
  try {
    const loadedLevels = await loadTerritoryLevels();
    return loadedLevels.length > 0 ? loadedLevels : FALLBACK_TERRITORY_LEVELS;
  } catch {
    return FALLBACK_TERRITORY_LEVELS;
  }
}
