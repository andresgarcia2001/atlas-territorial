import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchIndicatorValues,
  fetchMapData,
  fetchTerritories,
  fetchTerritoryOptions,
  fetchTransportRouteLines,
  fetchTransportRoutes,
} from "./api";


function mockJsonResponse(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}


function getRequestedUrl(fetchMock: ReturnType<typeof vi.fn<typeof fetch>>) {
  const [requestedInput] = fetchMock.mock.calls.at(0) ?? [];

  if (typeof requestedInput !== "string") {
    throw new Error("Expected fetch to be called with a URL string.");
  }

  return new URL(requestedInput);
}


describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds map-data requests with level, year, parent and repeated territory ids", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => mockJsonResponse({ type: "FeatureCollection", features: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchMapData(
      "poblacion_total",
      2022,
      "municipality",
      ["municipio_001", "municipio_002"],
      "provincia_02",
    );

    const requestedUrl = getRequestedUrl(fetchMock);
    expect(requestedUrl.pathname).toBe("/map-data");
    expect(requestedUrl.searchParams.get("indicator")).toBe("poblacion_total");
    expect(requestedUrl.searchParams.get("year")).toBe("2022");
    expect(requestedUrl.searchParams.get("level")).toBe("municipality");
    expect(requestedUrl.searchParams.get("parent_id")).toBe("provincia_02");
    expect(requestedUrl.searchParams.getAll("territory_ids")).toEqual(["municipio_001", "municipio_002"]);
  });

  it("builds territory option requests for a child level", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => mockJsonResponse({ territories: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTerritoryOptions("census_radius", "municipio_001");

    const requestedUrl = getRequestedUrl(fetchMock);
    expect(requestedUrl.pathname).toBe("/territory-options");
    expect(requestedUrl.searchParams.get("level")).toBe("census_radius");
    expect(requestedUrl.searchParams.get("parent_id")).toBe("municipio_001");
  });

  it("builds territory geometry requests with repeated territory ids", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => mockJsonResponse({ type: "FeatureCollection", features: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTerritories("municipality", ["municipio_001", "municipio_002"], "provincia_02");

    const requestedUrl = getRequestedUrl(fetchMock);
    expect(requestedUrl.pathname).toBe("/territories");
    expect(requestedUrl.searchParams.get("level")).toBe("municipality");
    expect(requestedUrl.searchParams.get("parent_id")).toBe("provincia_02");
    expect(requestedUrl.searchParams.getAll("territory_ids")).toEqual(["municipio_001", "municipio_002"]);
  });

  it("builds indicator value requests with level, year and repeated territory ids", async () => {
    const fetchMock = vi.fn<typeof fetch>(() =>
      mockJsonResponse({ indicator: "poblacion_total", year: 2022, level: "municipality", values: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchIndicatorValues(
      "poblacion_total",
      2022,
      "municipality",
      ["municipio_001", "municipio_002"],
      "provincia_02",
    );

    const requestedUrl = getRequestedUrl(fetchMock);
    expect(requestedUrl.pathname).toBe("/indicator-values");
    expect(requestedUrl.searchParams.get("indicator")).toBe("poblacion_total");
    expect(requestedUrl.searchParams.get("year")).toBe("2022");
    expect(requestedUrl.searchParams.get("level")).toBe("municipality");
    expect(requestedUrl.searchParams.get("parent_id")).toBe("provincia_02");
    expect(requestedUrl.searchParams.getAll("territory_ids")).toEqual(["municipio_001", "municipio_002"]);
  });

  it("builds transport route requests with source and repeated lines", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => mockJsonResponse({ type: "FeatureCollection", features: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTransportRoutes("BA DATA colectivos recorridos", ["10", "152"]);

    const requestedUrl = getRequestedUrl(fetchMock);
    expect(requestedUrl.pathname).toBe("/transport-routes");
    expect(requestedUrl.searchParams.get("source")).toBe("BA DATA colectivos recorridos");
    expect(requestedUrl.searchParams.getAll("lines")).toEqual(["10", "152"]);
  });

  it("builds transport route line metadata requests with source", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => mockJsonResponse({ lines: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTransportRouteLines("BA DATA colectivos recorridos");

    const requestedUrl = getRequestedUrl(fetchMock);
    expect(requestedUrl.pathname).toBe("/transport-route-lines");
    expect(requestedUrl.searchParams.get("source")).toBe("BA DATA colectivos recorridos");
  });
});
