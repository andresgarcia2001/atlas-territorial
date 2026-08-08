import type { IndicatorResponse, MapData } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchIndicators() {
  const response = await fetch(`${API_URL}/indicators`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los indicadores.");
  }

  const data = (await response.json()) as IndicatorResponse;
  return data.indicators;
}

export async function fetchMapData(indicator: string, year: number) {
  const searchParams = new URLSearchParams({
    indicator,
    year: year.toString(),
  });

  const response = await fetch(`${API_URL}/map-data?${searchParams.toString()}`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los datos del mapa.");
  }

  return (await response.json()) as MapData;
}
