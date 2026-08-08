import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchMapData, fetchTerritoryOptions } from "./api";


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
});
