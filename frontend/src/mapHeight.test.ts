import { describe, expect, it } from "vitest";

import {
  getHeightRatio,
  getHeightScale,
  getIndicatorRatio,
  getStableHeightRatio,
  getStableIndicatorRatio,
  getValueStats,
} from "./mapHeight";
import type { IndicatorScale } from "./types";

describe("mapHeight", () => {
  const populationScale: IndicatorScale = {
    indicator: "poblacion_total",
    level: "municipality",
    year: 2022,
    value_min: 10,
    value_max: 1000,
    value_p02: 10,
    value_p98: 1000,
    domain_min: 0,
    domain_max: 1000,
    transform: "sqrt",
    method: "global_min_max",
  };

  it("keeps analytical height stable for the same value", () => {
    expect(getStableHeightRatio(100, populationScale, "municipality", "poblacion_total")).toBe(
      getStableHeightRatio(100, populationScale, "municipality", "poblacion_total"),
    );
    expect(getStableIndicatorRatio(100, populationScale)).toBeCloseTo(Math.sqrt(0.1));
  });

  it("uses a fixed zero-to-one-hundred domain for percentages", () => {
    const percentageScale: IndicatorScale = {
      ...populationScale,
      indicator: "porcentaje_mujeres",
      domain_min: 0,
      domain_max: 100,
      transform: "linear",
      method: "fixed_percentage",
    };

    expect(getStableIndicatorRatio(50, percentageScale)).toBe(0.5);
  });

  it("does not assign analytical height to missing values", () => {
    expect(getStableIndicatorRatio(null, populationScale)).toBe(0);
    expect(getStableHeightRatio(null, populationScale, "municipality", "poblacion_total")).toBeGreaterThan(0);
  });

  it("keeps percentage indicators linear", () => {
    const stats = getValueStats([0, 20, 40, 100]);
    const low = getHeightRatio("provincia_a", 20, stats, "indicator", "province", "porcentaje_varones");
    const high = getHeightRatio("provincia_b", 40, stats, "indicator", "province", "porcentaje_varones");

    expect(high - low).toBeCloseTo(0.164, 3);
  });

  it("spreads province population values more than a straight linear ratio", () => {
    const stats = getValueStats([0, 200, 400, 1000]);
    const low = getHeightRatio("chubut", 200, stats, "indicator", "province", "poblacion_total");
    const high = getHeightRatio("santa_cruz", 400, stats, "indicator", "province", "poblacion_total");

    expect(high - low).toBeGreaterThan(0.164);
    expect(high).toBeGreaterThan(low);
  });

  it("uses the same eased province population ratio for indicator color", () => {
    const stats = getValueStats([0, 200, 400, 1000]);
    const low = getIndicatorRatio(200, stats, "province", "poblacion_total");
    const high = getIndicatorRatio(400, stats, "province", "poblacion_total");

    expect(low).toBeGreaterThan(0.2);
    expect(high).toBeGreaterThan(0.4);
    expect(high).toBeGreaterThan(low);
  });

  it("keeps municipal surface relief low enough to avoid slab-like map faces", () => {
    expect(getHeightScale("municipality", "densidad_poblacional")).toMatchObject({
      barMax: 118000,
      barMin: 9000,
      surfaceMax: 3200,
      surfaceMin: 160,
    });
  });
});
