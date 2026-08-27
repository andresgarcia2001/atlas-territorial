import type {
  IndicatorValuesResponse,
  IndicatorResponse,
  MapData,
  TerritoryData,
  TerritoryLevelId,
  TerritoryLevelsResponse,
  TerritoryOptionsResponse,
  TransportRouteData,
  TransportRouteLinesResponse,
} from "./types";

const DEFAULT_API_URL = import.meta.env.PROD ? "/api" : "http://localhost:8000";
const API_URL = import.meta.env.VITE_API_URL ?? DEFAULT_API_URL;

type RequestOptions = {
  signal?: AbortSignal;
};

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

function buildTerritorySearchParams(
  level: TerritoryLevelId,
  territoryIds: string[] = [],
  parentId?: string | null,
) {
  const searchParams = new URLSearchParams({ level });

  if (parentId) {
    searchParams.set("parent_id", parentId);
  }

  for (const territoryId of territoryIds) {
    searchParams.append("territory_ids", territoryId);
  }

  return searchParams;
}

export async function fetchTerritories(
  level: TerritoryLevelId,
  territoryIds: string[] = [],
  parentId?: string | null,
  options: RequestOptions = {},
) {
  const searchParams = buildTerritorySearchParams(level, territoryIds, parentId);
  const response = await fetch(`${API_URL}/territories?${searchParams.toString()}`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error("No se pudieron cargar las geometrías territoriales.");
  }

  return (await response.json()) as TerritoryData;
}

export async function fetchIndicatorValues(
  indicator: string,
  year: number,
  level: TerritoryLevelId,
  territoryIds: string[] = [],
  parentId?: string | null,
  options: RequestOptions = {},
) {
  const searchParams = buildTerritorySearchParams(level, territoryIds, parentId);
  searchParams.set("indicator", indicator);
  searchParams.set("year", year.toString());

  const response = await fetch(`${API_URL}/indicator-values?${searchParams.toString()}`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error("No se pudieron cargar los valores del indicador.");
  }

  return (await response.json()) as IndicatorValuesResponse;
}

export async function fetchMapData(
  indicator: string,
  year: number,
  level: TerritoryLevelId,
  territoryIds: string[] = [],
  parentId?: string | null,
  options: RequestOptions = {},
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

  const response = await fetch(`${API_URL}/map-data?${searchParams.toString()}`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error("No se pudieron cargar los datos del mapa.");
  }

  return (await response.json()) as MapData;
}

export async function fetchTransportRoutes(source?: string, lines: string[] = [], options: RequestOptions = {}) {
  const searchParams = new URLSearchParams();

  if (source) {
    searchParams.set("source", source);
  }

  for (const line of lines) {
    searchParams.append("lines", line);
  }

  const query = searchParams.toString();
  const response = await fetch(`${API_URL}/transport-routes${query ? `?${query}` : ""}`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error("No se pudieron cargar los recorridos de transporte.");
  }

  return (await response.json()) as TransportRouteData;
}

export async function fetchTransportRouteLines(source?: string) {
  const searchParams = new URLSearchParams();

  if (source) {
    searchParams.set("source", source);
  }

  const query = searchParams.toString();
  const response = await fetch(`${API_URL}/transport-route-lines${query ? `?${query}` : ""}`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar las líneas de transporte.");
  }

  const data = (await response.json()) as TransportRouteLinesResponse;
  return data.lines;
}
