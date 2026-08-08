import type {
  IndicatorResponse,
  MapData,
  TerritoryLevelId,
  TerritoryLevelsResponse,
  TerritoryOptionsResponse,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchTerritoryLevels() {
  const response = await fetch(`${API_URL}/territory-levels`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los niveles territoriales.");
  }

  const data = (await response.json()) as TerritoryLevelsResponse;
  return data.levels;
}

export async function fetchIndicators(level?: TerritoryLevelId) {
  const searchParams = new URLSearchParams();

  if (level) {
    searchParams.set("level", level);
  }

  const query = searchParams.toString();
  const response = await fetch(`${API_URL}/indicators${query ? `?${query}` : ""}`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los indicadores.");
  }

  const data = (await response.json()) as IndicatorResponse;
  return data.indicators;
}

export async function fetchTerritoryOptions(level: TerritoryLevelId, parentId?: string | null) {
  const searchParams = new URLSearchParams({ level });

  if (parentId) {
    searchParams.set("parent_id", parentId);
  }

  const response = await fetch(`${API_URL}/territory-options?${searchParams.toString()}`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los territorios.");
  }

  const data = (await response.json()) as TerritoryOptionsResponse;
  return data.territories;
}

export async function fetchMapData(
  indicator: string,
  year: number,
  level: TerritoryLevelId,
  territoryIds: string[] = [],
  parentId?: string | null,
) {
  const searchParams = new URLSearchParams({
    indicator,
    level,
    year: year.toString(),
  });

  if (parentId) {
    searchParams.set("parent_id", parentId);
  }

  for (const territoryId of territoryIds) {
    searchParams.append("territory_ids", territoryId);
  }

  const response = await fetch(`${API_URL}/map-data?${searchParams.toString()}`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los datos del mapa.");
  }

  return (await response.json()) as MapData;
}
