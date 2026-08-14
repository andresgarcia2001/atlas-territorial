import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LAYER_SETTINGS,
  FALLBACK_TERRITORY_LEVELS,
  areLayerSettingsEqual,
  getDefaultColorMode,
  getDefaultHeightMode,
  getDefaultIndicator,
  getDefaultTerritoryParentId,
  getDefaultTerritoryProvinceId,
  getInitialLayerSettings,
  getInitialTerritoryLevel,
  getTerritoryOptionsKey,
  getTerritoryLevelsOrFallback,
  getTerritorySelectionLabel,
  getTransportRouteLineSelectionLabel,
  shouldUseParentTerritoryFilter,
  shouldUseProvinceTerritoryFilter,
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
    expect(getDefaultColorMode([])).toBe("territory");
    expect(getDefaultHeightMode(["densidad_poblacional"])).toBe("indicator");
    expect(getDefaultHeightMode([])).toBe("visual");
    expect(getInitialLayerSettings([], "electoral_circuit")).toEqual({
      ...DEFAULT_LAYER_SETTINGS,
      territoryLevel: "electoral_circuit",
      indicator: "poblacion_total",
      colorMode: "territory",
      heightMode: "visual",
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
        geometryMode: "bars",
      }),
    ).toBe(false);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        heightMode: "visual",
      }),
    ).toBe(false);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        territoryLayerMode: "visible",
      }),
    ).toBe(false);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        transportOverlay: "ba_bus_routes",
      }),
    ).toBe(false);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        transportRouteLines: ["010"],
      }),
    ).toBe(false);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        territoryProvinceId: "provincia_02",
      }),
    ).toBe(false);
    expect(
      areLayerSettingsEqual(DEFAULT_LAYER_SETTINGS, {
        ...DEFAULT_LAYER_SETTINGS,
        territoryParentId: "provincia_02",
      }),
    ).toBe(false);
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
    expect(getTransportRouteLineSelectionLabel([])).toBe("Todas");
    expect(getTransportRouteLineSelectionLabel(["010"])).toBe("Linea 010");
    expect(getTransportRouteLineSelectionLabel(["010", "152"])).toBe("2 lineas");
  });

  it("uses province filters for municipalities and province plus municipality filters for electoral circuits", () => {
    const provinceOptions = [{ id: "provincia_06", name: "Buenos Aires", level: "province", parent_id: null }] as const;
    const municipalityOptions = [
      { id: "municipio_060007", name: "Adolfo Alsina", level: "municipality", parent_id: "provincia_06" },
    ] as const;

    expect(shouldUseParentTerritoryFilter("electoral_circuit")).toBe(true);
    expect(shouldUseParentTerritoryFilter("municipality")).toBe(false);
    expect(shouldUseProvinceTerritoryFilter("electoral_circuit")).toBe(true);
    expect(shouldUseProvinceTerritoryFilter("municipality")).toBe(true);
    expect(getTerritoryOptionsKey("electoral_circuit", "municipio_060007")).toBe(
      "electoral_circuit:municipio_060007",
    );
    expect(getTerritoryOptionsKey("province")).toBe("province:all");
    expect(getDefaultTerritoryParentId("electoral_circuit", [...municipalityOptions])).toBe("municipio_060007");
    expect(getDefaultTerritoryParentId("municipality", [...municipalityOptions])).toBeNull();
    expect(getDefaultTerritoryProvinceId("electoral_circuit", [...provinceOptions])).toBe("provincia_06");
    expect(getDefaultTerritoryProvinceId("municipality", [...provinceOptions])).toBe("provincia_06");
  });
});
