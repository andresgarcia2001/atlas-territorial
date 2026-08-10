import { describe, expect, it } from "vitest";

import {
  compareTransportRouteLines,
  createTransportLineColorMap,
  getFallbackTransportRouteColor,
  getStableTransportColorScope,
} from "./transportColors";

describe("transportColors", () => {
  it("orders line labels numerically when possible", () => {
    expect(["152", "047", "10", "A"].sort(compareTransportRouteLines)).toEqual(["10", "047", "152", "A"]);
  });

  it("assigns distinct colors to the selected lines before reusing any color", () => {
    const selectedLines = ["049", "057", "062", "063", "065", "067"];
    const colorByLine = createTransportLineColorMap(selectedLines);
    const colors = selectedLines.map((line) => colorByLine.get(line));

    expect(new Set(colors).size).toBe(selectedLines.length);
  });

  it("keeps many line colors unique by generating extra colors beyond the base palette", () => {
    const lines = Array.from({ length: 160 }, (_, index) => String(index + 1).padStart(3, "0"));
    const colorByLine = createTransportLineColorMap(lines);
    const colors = lines.map((line) => colorByLine.get(line));

    expect(new Set(colors).size).toBe(lines.length);
  });

  it("keeps a selected line color stable when the full line catalog is available", () => {
    const availableLines = ["055", "056", "057", "060", "061", "062", "064", "065"];
    const singleLineColors = createTransportLineColorMap(getStableTransportColorScope(availableLines, ["060"]));
    const manyLineColors = createTransportLineColorMap(
      getStableTransportColorScope(availableLines, ["055", "056", "060", "061", "062", "064", "065"]),
    );

    expect(manyLineColors.get("060")).toBe(singleLineColors.get("060"));
  });

  it("uses deterministic fallback colors for routes without a line label", () => {
    expect(getFallbackTransportRouteColor("ramal-sin-linea")).toBe(getFallbackTransportRouteColor("ramal-sin-linea"));
  });
});
