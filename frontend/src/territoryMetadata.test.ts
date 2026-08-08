import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LAYER_SETTINGS,
  FALLBACK_TERRITORY_LEVELS,
  areLayerSettingsEqual,
  getDefaultIndicator,
  getInitialLayerSettings,
  getInitialTerritoryLevel,
  getTerritoryLevelsOrFallback,
  getTerritorySelectionLabel,
} from "./territoryMetadata";
import type { TerritoryLevel } from "./types";


describe("territoryMetadata", () => {
  it("falls back to default territory levels when metadata loading fails", async () => {
    const loadTerritoryLevels = vi.fn<() => Promise<TerritoryLevel[]>>().mockRejectedValue(new Error("boom"));

    await expect(getTerritoryLevelsOrFallback(loadTerritoryLevels)).resolves.toEqual(FALLBACK_TERRITORY_LEVELS);
  });

  it("selects the first valid indicator when the default is not available for a level", () => {
    expect(getDefaultIndicator(["densidad_poblacional"])).toBe("densidad_poblacional");
    expect(getInitialLayerSettings(["densidad_poblacional"], "municipality")).toEqual({
      ...DEFAULT_LAYER_SETTINGS,
      territoryLevel: "municipality",
      indicator: "densidad_poblacional",
    });
  });

  it("prefers the default territory level only when it has data", () => {
    expect(
      getInitialTerritoryLevel([
        { id: "province", label: "Provincias", territory_count: 0 },
        { id: "municipality", label: "Municipios", territory_count: 12 },
        { id: "census_radius", label: "Radios censales", territory_count: 0 },
      ]),
    ).toBe("municipality");
  });

  it("compares layer settings and formats selected territories", () => {
    expect(areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, { ...DEFAULT_LAYER_SETTINGS })).toBe(true);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        territoryIds: ["provincia_02"],
      }),
    ).toBe(false);
    expect(getTerritorySelectionLabel([], [])).toBe("Todos");
    expect(
      getTerritorySelectionLabel(
        ["provincia_02"],
        [{ id: "provincia_02", name: "Buenos Aires", level: "province", parent_id: null }],
      ),
    ).toBe("Buenos Aires");
  });
});
