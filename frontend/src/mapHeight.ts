import type { HeightMode, TerritoryLevelId } from "./types";

export type ValueStats = {
  hasValues: boolean;
  min: number;
  max: number;
};

export type HeightScale = {
  barMax: number;
  barMin: number;
  surfaceMax: number;
  surfaceMin: number;
};

const HEIGHT_RATIO_BASE = 0.18;
const HEIGHT_RATIO_SPAN = 0.82;
const HEIGHT_RATIO_MISSING = 0.08;
const HEIGHT_RATIO_SINGLE_VALUE = 0.62;
const HEIGHT_RATIO_UNIFORM = 0.5;
const HEIGHT_RATIO_VISUAL_SPAN = 0.5;
const PROVINCE_POPULATION_RATIO_BASE = 0.12;
const PROVINCE_POPULATION_RATIO_SPAN = 0.88;

const COUNT_HEIGHT_EXPONENT = 0.82;
const PROVINCE_POPULATION_HEIGHT_EXPONENT = 0.56;

export function getTerritoryHash(territoryId: string) {
  let hash = 0;

  for (let index = 0; index < territoryId.length; index += 1) {
    hash = (hash * 31 + territoryId.charCodeAt(index)) >>> 0;
  }

  return hash;
}

export function getValueStats(values: Array<number | null>): ValueStats {
  let hasValues = false;
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;

  for (const value of values) {
    if (value === null) {
      continue;
    }

    hasValues = true;
    min = Math.min(min, value);
    max = Math.max(max, value);
  }

  return hasValues ? { hasValues, min, max } : { hasValues: false, min: 0, max: 1 };
}

export function getHeightScale(territoryLevel: TerritoryLevelId, indicator: string): HeightScale {
  if (indicator.startsWith("porcentaje_")) {
    return {
      barMax: 56000,
      barMin: 7000,
      surfaceMax: 950,
      surfaceMin: 140,
    };
  }

  if (territoryLevel === "province" && indicator === "poblacion_total") {
    return {
      barMax: 190000,
      barMin: 16000,
      surfaceMax: 28000,
      surfaceMin: 3600,
    };
  }

  if (territoryLevel === "municipality") {
    return {
      barMax: 118000,
      barMin: 9000,
      surfaceMax: 3200,
      surfaceMin: 160,
    };
  }

  if (territoryLevel === "census_radius" || territoryLevel === "electoral_circuit") {
    return {
      barMax: 46000,
      barMin: 4000,
      surfaceMax: 900,
      surfaceMin: 80,
    };
  }

  return {
    barMax: 160000,
    barMin: 12000,
    surfaceMax: 3600,
    surfaceMin: 180,
  };
}

export function interpolateHeight(min: number, max: number, ratio: number) {
  return Math.round(min + (max - min) * ratio);
}

function getFallbackHeightRatio(territoryId: string) {
  return 0.32 + ((getTerritoryHash(territoryId) % 1000) / 1000) * HEIGHT_RATIO_VISUAL_SPAN;
}

function getHeightExponent(territoryLevel: TerritoryLevelId, indicator: string) {
  if (indicator.startsWith("porcentaje_")) {
    return 1;
  }

  if (territoryLevel === "province" && indicator === "poblacion_total") {
    return PROVINCE_POPULATION_HEIGHT_EXPONENT;
  }

  return COUNT_HEIGHT_EXPONENT;
}

export function getHeightRatio(
  territoryId: string,
  value: number | null,
  stats: ValueStats,
  heightMode: HeightMode,
  territoryLevel: TerritoryLevelId,
  indicator: string,
) {
  if (heightMode === "uniform") {
    return HEIGHT_RATIO_UNIFORM;
  }

  if (heightMode === "visual") {
    return getFallbackHeightRatio(territoryId);
  }

  if (!stats.hasValues || value === null) {
    return HEIGHT_RATIO_MISSING;
  }

  if (stats.min === stats.max) {
    return HEIGHT_RATIO_SINGLE_VALUE;
  }

  const rawRatio = (value - stats.min) / (stats.max - stats.min);
  const clampedRatio = Math.max(0, Math.min(1, rawRatio));
  const heightExponent = getHeightExponent(territoryLevel, indicator);
  const easedRatio = heightExponent === 1 ? clampedRatio : Math.pow(clampedRatio, heightExponent);
  const ratioBase =
    territoryLevel === "province" && indicator === "poblacion_total"
      ? PROVINCE_POPULATION_RATIO_BASE
      : HEIGHT_RATIO_BASE;
  const ratioSpan =
    territoryLevel === "province" && indicator === "poblacion_total"
      ? PROVINCE_POPULATION_RATIO_SPAN
      : HEIGHT_RATIO_SPAN;

  return ratioBase + easedRatio * ratioSpan;
}

export function getIndicatorRatio(
  value: number | null,
  stats: ValueStats,
  territoryLevel: TerritoryLevelId,
  indicator: string,
) {
  if (!stats.hasValues || value === null) {
    return 0;
  }

  if (stats.min === stats.max) {
    return HEIGHT_RATIO_SINGLE_VALUE;
  }

  const rawRatio = (value - stats.min) / (stats.max - stats.min);
  const clampedRatio = Math.max(0, Math.min(1, rawRatio));
  const heightExponent = getHeightExponent(territoryLevel, indicator);

  return heightExponent === 1 ? clampedRatio : Math.pow(clampedRatio, heightExponent);
}
