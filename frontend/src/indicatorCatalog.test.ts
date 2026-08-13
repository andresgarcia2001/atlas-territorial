import { describe, expect, it } from "vitest";

import { getAvailableIndicatorGroups, getIndicatorLabel, getIndicatorOption } from "./indicatorCatalog";


describe("indicatorCatalog", () => {
  it("filters catalog groups to the indicators loaded by the API", () => {
    const groups = getAvailableIndicatorGroups(["poblacion_total", "densidad_poblacional"]);

    expect(groups).toEqual([
      {
        id: "population",
        label: "Población",
        indicators: [{ id: "poblacion_total", label: "Población total" }],
      },
      {
        id: "territory",
        label: "Territorio",
        indicators: [{ id: "densidad_poblacional", label: "Densidad poblacional" }],
      },
    ]);
  });

  it("keeps unknown indicators readable instead of failing", () => {
    expect(getIndicatorOption("superficie_km2")).toBeUndefined();
    expect(getIndicatorLabel("superficie_km2")).toBe("superficie km2");
  });
});
