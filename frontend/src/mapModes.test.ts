import { describe, expect, it } from "vitest";

import { getCameraPreset, getEffectiveGeometryMode, getLayerVisibility } from "./mapModes";

describe("mapModes", () => {
  it("keeps camera concerns separate from geometry style", () => {
    expect(getCameraPreset("flat")).toMatchObject({ pitch: 0, bearing: 0 });
    expect(getCameraPreset("extruded")).toMatchObject({ pitch: 45, bearing: -18 });
  });

  it("falls back to surface extrusion when bar geometry is not available", () => {
    expect(getEffectiveGeometryMode("extruded", "bars", false)).toBe("surface");
    expect(getLayerVisibility("extruded", "bars", false)).toEqual({
      fill: "none",
      outline: "visible",
      surfaceExtrusion: "visible",
      barFill: "none",
      barExtrusion: "none",
      barOutline: "none",
    });
  });

  it("shows only the requested 3D geometry layer when data supports bars", () => {
    expect(getLayerVisibility("extruded", "bars", true)).toEqual({
      fill: "none",
      outline: "none",
      surfaceExtrusion: "none",
      barFill: "visible",
      barExtrusion: "visible",
      barOutline: "visible",
    });
    expect(getLayerVisibility("flat", "bars", true)).toEqual({
      fill: "visible",
      outline: "visible",
      surfaceExtrusion: "none",
      barFill: "none",
      barExtrusion: "none",
      barOutline: "none",
    });
  });
});
