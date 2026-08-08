import { DEFAULT_INDICATOR, getAvailableIndicatorGroups } from "./indicatorCatalog";
import type { LayerSettings, TerritoryLevel, TerritoryLevelId, TerritoryOption } from "./types";

export const DEFAULT_TERRITORY_LEVEL: TerritoryLevelId = "province";

export const FALLBACK_TERRITORY_LEVELS: TerritoryLevel[] = [
  { id: "province", label: "Provincias", territory_count: 1 },
  { id: "municipality", label: "Municipios", territory_count: 0 },
  { id: "census_radius", label: "Radios censales", territory_count: 0 },
];

export const DEFAULT_LAYER_SETTINGS: LayerSettings = {
  indicator: DEFAULT_INDICATOR,
  colorMode: "indicator",
  viewMode: "flat",
  territoryLevel: DEFAULT_TERRITORY_LEVEL,
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
    first.territoryLevel === second.territoryLevel &&
    areArraysEqual(first.territoryIds, second.territoryIds)
  );
}

export function getDefaultIndicator(loadedIndicators: string[]) {
  const loadedGroups = getAvailableIndicatorGroups(loadedIndicators);
  const firstIndicator = loadedGroups[0]?.indicators[0];

  return loadedIndicators.includes(DEFAULT_INDICATOR) ? DEFAULT_INDICATOR : firstIndicator?.id ?? DEFAULT_INDICATOR;
}

export function getInitialLayerSettings(loadedIndicators: string[], territoryLevel: TerritoryLevelId): LayerSettings {
  return {
    ...DEFAULT_LAYER_SETTINGS,
    territoryLevel,
    indicator: getDefaultIndicator(loadedIndicators),
  };
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

export async function getTerritoryLevelsOrFallback(loadTerritoryLevels: () => Promise<TerritoryLevel[]>) {
  try {
    const loadedLevels = await loadTerritoryLevels();
    return loadedLevels.length > 0 ? loadedLevels : FALLBACK_TERRITORY_LEVELS;
  } catch {
    return FALLBACK_TERRITORY_LEVELS;
  }
}
