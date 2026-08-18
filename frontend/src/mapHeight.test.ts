import { describe, expect, it } from "vitest";

import { getHeightRatio, getValueStats } from "./mapHeight";

describe("mapHeight", () => {
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
});
