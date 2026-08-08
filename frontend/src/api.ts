import type { IndicatorResponse, MapData, TerritoryOptionsResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchIndicators() {
  const response = await fetch(`${API_URL}/indicators`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los indicadores.");
  }

  const data = (await response.json()) as IndicatorResponse;
  return data.indicators;
}

export async function fetchTerritoryOptions() {
  const response = await fetch(`${API_URL}/territory-options`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar las provincias.");
  }

  const data = (await response.json()) as TerritoryOptionsResponse;
  return data.territories;
}

export async function fetchMapData(indicator: string, year: number, provinceIds: string[] = []) {
  const searchParams = new URLSearchParams({
    indicator,
    year: year.toString(),
  });

  for (const provinceId of provinceIds) {
    searchParams.append("province_ids", provinceId);
  }

  const response = await fetch(`${API_URL}/map-data?${searchParams.toString()}`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los datos del mapa.");
  }

  return (await response.json()) as MapData;
}
