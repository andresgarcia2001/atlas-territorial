export type IndicatorOption = {
  id: string;
  label: string;
};

export type IndicatorGroup = {
  id: string;
  label: string;
  indicators: IndicatorOption[];
};

export const DEFAULT_INDICATOR = "poblacion_total";

export const INDICATOR_GROUPS: IndicatorGroup[] = [
  {
    id: "population",
    label: "Población",
    indicators: [
      { id: "poblacion_total", label: "Población total" },
      { id: "poblacion_viviendas_particulares", label: "Población en viviendas particulares" },
      { id: "poblacion_viviendas_colectivas", label: "Población en viviendas colectivas" },
      { id: "poblacion_situacion_calle", label: "Población en situación de calle" },
      { id: "mujeres", label: "Mujeres" },
      { id: "varones", label: "Varones" },
      { id: "otro_x", label: "Otro / X" },
      { id: "porcentaje_mujeres", label: "% mujeres" },
      { id: "porcentaje_varones", label: "% varones" },
      { id: "porcentaje_otro_x", label: "% otro / X" },
    ],
  },
  {
    id: "territory",
    label: "Territorio",
    indicators: [{ id: "densidad_poblacional", label: "Densidad poblacional" }],
  },
  {
    id: "housing",
    label: "Viviendas",
    indicators: [
      { id: "viviendas_total", label: "Viviendas totales" },
      { id: "viviendas_particulares", label: "Viviendas particulares" },
      { id: "viviendas_colectivas", label: "Viviendas colectivas" },
    ],
  },
];

export function getAvailableIndicatorGroups(indicators: string[]) {
  return INDICATOR_GROUPS.map((group) => ({
    ...group,
    indicators: group.indicators.filter((option) => indicators.includes(option.id)),
  })).filter((group) => group.indicators.length > 0);
}

export function getIndicatorOption(indicator: string, groups = INDICATOR_GROUPS) {
  return groups.flatMap((group) => group.indicators).find((option) => option.id === indicator);
}

export function getIndicatorLabel(indicator: string) {
  return getIndicatorOption(indicator)?.label ?? indicator.replaceAll("_", " ");
}
